"""Files of a locality (region ... village, CVD or geographical unit) for the galleries and the profile headers.

Two sources, the same as the "Gallery" menu of the DCC web platform:
- "Investment cycle": attachments of the DCC tasks (PV, attendance lists, meeting photos...). They live in the
  `task` documents of the facilitators' CouchDB databases (`attachments` field, one entry = {name, type,
  attachment: {uri}}): no SQL model, a file is identified by its S3 URL. The databases read are those of the
  facilitators assigned to the villages (MIS assignments) or stabilized in them (CDD), one query per database,
  in parallel; the result is cached a few minutes.
- "Infrastructures": files of the subprojects and their structures (`SubprojectFile`, SQL), structures that will
  no longer be built left out.
Files stored on the phone only (`file:` URLs) are never shown."""
import hashlib
from concurrent.futures import ThreadPoolExecutor

from django.core.cache import cache
from django.db import connections
from django.db.models import Q
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from administrativelevels.functions_profile import TYPE_ICONS, TYPE_LABELS, descendants, level_url, subprojects_queryset
from administrativelevels.models import CVD, AdministrativeLevel, GeographicalUnit

CYCLE = 'cycle'
WORKS = 'works'
SOURCES = {CYCLE: _("Investment cycle"), WORKS: _("Infrastructures")}
PHOTO, DOCUMENT = 'Photo', 'Document'

IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'heic', 'heif'}
WORD_EXTENSIONS = {'doc', 'docx'}
OFFICE_EXTENSIONS = {'xls', 'xlsx', 'ppt', 'pptx'}
KOBO_PREFIX = 'https://kf.kobotoolbox.org/'
# Hosts the file view may read or redirect to (never an arbitrary URL).
ALLOWED_FILE_PREFIXES = ('https://cddfiles.s3.amazonaws.com/', KOBO_PREFIX)

CYCLE_CACHE_SECONDS = 600
COUCHDB_WORKERS = 16
TASK_FIELDS = ['_id', 'sql_id', 'name', 'administrative_level_id', 'administrative_level_name', 'phase_name',
               'activity_name', 'attachments', 'completed_date', 'last_updated', 'project_id']


# -- Files -------------------------------------------------------------------------------------------------------
def raw_url(url):
    return str(url or '').split('?')[0]


def extension(url):
    name = raw_url(url).rsplit('/', 1)[-1]
    return name.rsplit('.', 1)[-1].lower() if '.' in name else ''


def file_kind(url, declared_type=None):
    """'image', 'pdf', 'word', 'office' or 'other', from the extension (the declared MIME type is not reliable),
    else from the declared type (Kobo links have no extension)."""
    ext = extension(url)
    if ext in IMAGE_EXTENSIONS:
        return 'image'
    if ext == 'pdf':
        return 'pdf'
    if ext in WORD_EXTENSIONS:
        return 'word'
    if ext in OFFICE_EXTENSIONS:
        return 'office'
    declared = str(declared_type or '').lower()
    if not ext and declared.startswith('image'):
        return 'image'
    if not ext and 'pdf' in declared:
        return 'pdf'
    return 'other'


def is_allowed_url(url):
    return raw_url(url).startswith(ALLOWED_FILE_PREFIXES)


def file_view_url(url, download=False, name=None):
    """Link to the file through the MIS (Kobo files need the API token; downloads get a readable file name)."""
    from urllib.parse import urlencode
    params = {'url': raw_url(url)}
    if download:
        params['download'] = '1'
        if name:
            params['name'] = name
    return f"{reverse('administrativelevels:gallery_file')}?{urlencode(params)}"


def display_url(url):
    """URL an <img> or a viewer can load: S3 directly, Kobo through the MIS."""
    return file_view_url(url) if raw_url(url).startswith(KOBO_PREFIX) else raw_url(url)


def format_date(value):
    """dd/mm/yyyy from a date or a CouchDB date text ("2026-8-16 8:56:49"); '' if unknown."""
    if not value:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime('%d/%m/%Y')
    parts = str(value).split(' ')[0].split('-')
    if len(parts) == 3 and all(x.isdigit() for x in parts):
        return f"{int(parts[2]):02d}/{int(parts[1]):02d}/{parts[0]}"
    return str(value)[:10]


# -- Scope (the object whose files are shown) -------------------------------------------------------------------
class Scope:
    """A locality: its villages, cantons and CVDs, and how to name it and link back to its profile."""

    def __init__(self, kind, obj, name, type_label, icon, profile_url, villages, cantons=(), cvd_ids=()):
        self.kind, self.obj, self.name, self.type_label, self.icon = kind, obj, name, type_label, icon
        self.profile_url, self.villages = profile_url, villages
        self.cantons, self.cvd_ids = list(cantons), list(cvd_ids)

    @property
    def params(self):
        return {self.kind: self.obj.pk}

    @property
    def label(self):
        return f"{self.type_label} {self.name}"

    @property
    def cache_key(self):
        return f"{self.kind}-{self.obj.pk}"


def level_scope(level):
    if level.type == AdministrativeLevel.VILLAGE:
        villages, cantons = {level.pk: level.name}, []
        cvd_ids = [level.cvd_id] if level.cvd_id else []
    else:
        rows, _children, _child_of = descendants(level)
        villages = {i: r['name'] for i, r in rows.items() if r['type'] == AdministrativeLevel.VILLAGE}
        cantons = [i for i, r in rows.items() if r['type'] == AdministrativeLevel.CANTON]
        cvd_ids = sorted({rows[i]['cvd_id'] for i in villages if rows[i]['cvd_id']})
    if level.type == AdministrativeLevel.CANTON:
        cantons = [level.pk]
    return Scope('level', level, level.name, TYPE_LABELS.get(level.type, level.type),
                 TYPE_ICONS.get(level.type, 'fa-map-marker-alt'), level_url(level), villages, cantons, cvd_ids)


def cvd_scope(cvd):
    villages = dict(cvd.get_villages().values_list('pk', 'name'))
    return Scope('cvd', cvd, cvd.get_name(), _("CVD"), TYPE_ICONS['CVD'],
                 reverse('administrativelevels:cvd_detail', args=[cvd.pk]), villages, (), [cvd.pk])


def unit_scope(unit):
    villages = dict(unit.get_villages().values_list('pk', 'name'))
    return Scope('unit', unit, unit.get_name(), _("Geographical unit"), TYPE_ICONS['GeographicalUnit'],
                 reverse('administrativelevels:geographical_unit_detail', args=[unit.pk]), villages, (),
                 list(unit.get_cvds().values_list('pk', flat=True)))


def scope_from_params(params):
    """Scope chosen in the URL: `level`, `cvd` or `unit` (an id), or the finest level of the cascade
    region > prefecture > commune > canton > village of the filter form. None = everywhere."""
    def as_int(value):
        return int(value) if str(value or '').isdigit() else None
    if as_int(params.get('cvd')):
        obj = CVD.objects.filter(pk=as_int(params.get('cvd'))).first()
        if obj:
            return cvd_scope(obj)
    if as_int(params.get('unit')):
        obj = GeographicalUnit.objects.filter(pk=as_int(params.get('unit'))).first()
        if obj:
            return unit_scope(obj)
    for key in ('level', 'village', 'canton', 'commune', 'prefecture', 'region'):
        if as_int(params.get(key)):
            obj = AdministrativeLevel.objects.filter(pk=as_int(params.get(key))).first()
            if obj:
                return level_scope(obj)
    return None


# -- Infrastructures (SubprojectFile) ------------------------------------------------------------------------------
def works_files(scope, project_ids, search=''):
    """Files of the subprojects and structures of the scope (everywhere if None), newest first."""
    from subprojects.models import Subproject, SubprojectFile
    if scope is not None:
        subprojects = subprojects_queryset(project_ids, list(scope.villages), scope.cantons, scope.cvd_ids)
    else:
        subprojects = Subproject.objects.exclude(infrastructure_deleted=True)
        if project_ids:
            subprojects = subprojects.filter(pk__in=Subproject.objects.filter(projects__in=project_ids).values('pk'))
    queryset = (SubprojectFile.objects.filter(subproject__in=subprojects.values('pk'))
                .exclude(url__isnull=True).exclude(url='').exclude(url__startswith='file:'))
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(subproject__full_title_of_approved_subproject__icontains=search)
                                   | Q(subproject_step__wording__icontains=search))
    rows = queryset.order_by('-principal', '-date_taken', '-id').values(
        'id', 'name', 'url', 'file_type', 'date_taken', 'principal', 'subproject_id', 'subproject__number',
        'subproject__full_title_of_approved_subproject', 'subproject__location_subproject_realized__name',
        'subproject__canton__name', 'subproject_step__wording')
    files = []
    for r in rows:
        place = r['subproject__location_subproject_realized__name'] or r['subproject__canton__name'] or ''
        files.append({
            'source': WORKS, 'id': r['id'], 'url': raw_url(r['url']), 'kind': file_kind(r['url'], r['file_type']),
            'ext': extension(r['url']).upper(), 'name': r['subproject_step__wording'] or r['name'] or '',
            'date': format_date(r['date_taken']), 'sort_date': r['date_taken'], 'place': place,
            'context': ' - '.join(str(x) for x in (r['subproject__number'], r['subproject__full_title_of_approved_subproject']) if x),
            'context_url': reverse('subprojects:detail', args=[r['subproject_id']]) if r['subproject_id'] else '',
        })
    return files


# -- Investment cycle (CouchDB task attachments) ------------------------------------------------------------------
def couch_project_ids(project_ids):
    """CouchDB ids of the DCC projects with the same names as the MIS projects."""
    from subprojects.models import Project
    names = list(Project.objects.filter(pk__in=project_ids).values_list('name', flat=True))
    if not names:
        return []
    with connections['cdd'].cursor() as cursor:
        cursor.execute("SELECT couch_id FROM process_manager_project WHERE name = ANY(%s) AND couch_id IS NOT NULL", [names])
        return [row[0] for row in cursor.fetchall()]


def facilitator_databases(village_ids, project_ids):
    """CouchDB databases of the facilitators assigned to the villages for the projects, or stabilized in them."""
    from assignments.models import AssignAdministrativeLevelToFacilitator
    from authentication.models import Facilitator
    ids = {int(v) for v in AssignAdministrativeLevelToFacilitator.objects.filter(
        administrative_level_id__in=village_ids, project_id__in=project_ids).values_list('facilitator_id', flat=True)
        if str(v).isdigit()}
    villages = set(village_ids)
    for pk, stabilized in Facilitator.objects.using('cdd').values_list('pk', 'stabilization_administrative_ids'):
        if villages & {int(v) for v in stabilized or [] if str(v).isdigit()}:
            ids.add(pk)
    return sorted(set(Facilitator.objects.using('cdd').filter(pk__in=ids, develop_mode=False, training_mode=False)
                      .exclude(no_sql_db_name__isnull=True).exclude(no_sql_db_name='')
                      .values_list('no_sql_db_name', flat=True)))


def _read_tasks(db_name, selector):
    """Run in a worker thread, with its own CouchDB connection. A database that fails is skipped."""
    try:
        from no_sql_client import NoSQLClient
        database = NoSQLClient().get_db(db_name)
        return database.get_query_result(selector, fields=TASK_FIELDS, raw_result=True, limit=100000).get('docs', [])
    except Exception as exc:  # noqa: BLE001 - one unreachable database must not break the page
        print(f"[gallery] CouchDB database {db_name} skipped: {exc}")
        return []


def cycle_files(scope, project_ids):
    """Attachments of the DCC tasks of the villages of the scope, for the projects, one entry per file."""
    if scope is None or not scope.villages:
        return []
    key = 'gallery-cycle:' + hashlib.md5(f"{scope.cache_key}:{sorted(project_ids)}".encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached

    village_ids = list(scope.villages)
    databases = facilitator_databases(village_ids, project_ids)
    selector = {
        'type': 'task',
        'administrative_level_id': {'$in': [str(v) for v in village_ids] + village_ids},
        'attachments': {'$elemMatch': {'attachment.uri': {'$exists': True}}},
    }
    couch_ids = couch_project_ids(project_ids)
    if couch_ids:
        selector['project_id'] = {'$in': couch_ids}
    docs = []
    if databases:
        with ThreadPoolExecutor(max_workers=min(COUCHDB_WORKERS, len(databases))) as pool:
            for result in pool.map(lambda name: _read_tasks(name, selector), databases):
                docs += result

    files, seen = [], set()
    for doc in docs:
        village_id = int(doc['administrative_level_id']) if str(doc.get('administrative_level_id') or '').isdigit() else None
        place = scope.villages.get(village_id) or doc.get('administrative_level_name') or ''
        for attachment in doc.get('attachments') or []:
            uri = (attachment.get('attachment') or {}).get('uri') if isinstance(attachment, dict) else None
            if not uri or str(uri).startswith('file:') or raw_url(uri) in seen:
                continue
            seen.add(raw_url(uri))
            files.append({
                'source': CYCLE, 'id': None, 'url': raw_url(uri), 'kind': file_kind(uri, attachment.get('type')),
                'ext': extension(uri).upper(), 'name': attachment.get('name') or '',
                'date': format_date(doc.get('completed_date') or doc.get('last_updated')),
                'sort_date': str(doc.get('completed_date') or doc.get('last_updated') or ''),
                'place': place, 'village_id': village_id,
                'context': doc.get('name') or '',
                'phase': doc.get('phase_name') or '', 'activity': doc.get('activity_name') or '',
                'context_url': reverse('administrativelevels:village_detail', args=[village_id]) if village_id else '',
            })
    files.sort(key=lambda f: (f['place'].lower(), f['phase'], f['activity'], f['context'], f['name']))
    cache.set(key, files, CYCLE_CACHE_SECONDS)
    return files


def gallery_url(source, scope=None, **params):
    from urllib.parse import urlencode
    query = dict(scope.params if scope else {}, **{k: v for k, v in params.items() if v})
    url = reverse('administrativelevels:gallery_cycle' if source == CYCLE else 'administrativelevels:gallery_works')
    return f"{url}?{urlencode(query)}" if query else url


def preview_photos(scope, project_ids, limit=5, with_cycle=True):
    """Up to `limit` photos of the scope for the profile header: subproject photos (main ones first) and photos
    of the investment cycle, alternated."""
    works = [f for f in works_files(scope, project_ids) if f['kind'] == 'image']
    cycle = [f for f in cycle_files(scope, project_ids) if f['kind'] == 'image'] if with_cycle else []
    cycle.sort(key=lambda f: tuple(int(x) if x.isdigit() else 0 for x in f['sort_date'].replace(' ', '-').replace(':', '-').split('-')), reverse=True)
    photos = []
    for index in range(limit):
        for group in (works, cycle):
            if index < len(group) and len(photos) < limit:
                photos.append(group[index])
    return photos
