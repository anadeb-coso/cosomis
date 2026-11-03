"""“Animateurs” section: list of community and technical facilitators, and their profile page.

Facilitators live in the CDD table `authentication_facilitator` (read-only here). Their villages
come from the JSON fields of that table and from the village assignments made in the MIS;
their projects from the DCC link table `process_manager_project_facilitators`."""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Q
from django.shortcuts import render
from django.http import Http404
from django.urls import reverse
from django.utils.translation import gettext, gettext_lazy as _

from administrativelevels.models import AdministrativeLevel
from assignments.models import AssignAdministrativeLevelToFacilitator
from authentication.models import Facilitator
from cosomis.project_scope import ProjectScope, project_required
from subprojects.models import Project

FACILITATOR_TYPES = {
    'community_facilitator': _("Community facilitator"),
    'technical_facilitator': _("Technical facilitator"),
}
PER_PAGE_CHOICES = (10, 20, 30, 50, 100)
DEFAULT_PER_PAGE = 50
SEXES = {'M': _("Male"), 'H': _("Male"), 'F': _("Female")}


def _facilitators():
    return Facilitator.objects.using('cdd')


def _type_label(facilitator):
    return FACILITATOR_TYPES.get(facilitator.facilitator_type, facilitator.facilitator_type or '-')


def _village_ids(facilitator):
    """Ids of every village the facilitator covers, from all of the CDD JSON fields."""
    ids = set()
    for item in facilitator.administrative_levels or []:
        value = item.get('id') if isinstance(item, dict) else item
        if str(value or '').isdigit():
            ids.add(int(value))
    for field in ('administrative_levels_ids', 'stabilization_administrative_ids', 'additional_administrative_ids'):
        for value in getattr(facilitator, field) or []:
            if str(value or '').isdigit():
                ids.add(int(value))
    return ids


def facilitator_ids_in_scope(project_ids):
    """Facilitators linked to one of the projects (DCC link table) or assigned to a village for one of them."""
    if not project_ids:
        return set()
    with connection.cursor() as cursor:
        cursor.execute("SELECT DISTINCT facilitator_id FROM process_manager_project_facilitators "
                       "WHERE project_id = ANY(%s)", [list(project_ids)])
        ids = {row[0] for row in cursor.fetchall()}
    assigned = (AssignAdministrativeLevelToFacilitator.objects.filter(project_id__in=project_ids)
                .values_list('facilitator_id', flat=True).distinct())
    ids |= {int(value) for value in assigned if str(value).isdigit()}
    return ids


def _project_ids_by_facilitator(facilitator_ids):
    if not facilitator_ids:
        return {}
    with connection.cursor() as cursor:
        cursor.execute("SELECT facilitator_id, project_id FROM process_manager_project_facilitators "
                       "WHERE facilitator_id = ANY(%s)", [list(facilitator_ids)])
        rows = cursor.fetchall()
    result = {}
    for facilitator_id, project_id in rows:
        result.setdefault(facilitator_id, set()).add(project_id)
    return result


def _ancestors(level):
    """{'Canton': ..., 'Commune': ..., 'Prefecture': ..., 'Region': ...} for a village."""
    chain, parent = {}, level.parent
    while parent is not None:
        chain[parent.type] = parent
        parent = parent.parent
    return chain


@login_required
@project_required
def facilitator_list(request):
    scope = ProjectScope(request)
    selected_type = request.GET.get('type', '')
    search = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')

    queryset = _facilitators().filter(develop_mode=False, training_mode=False,
                                      pk__in=facilitator_ids_in_scope(scope.ids))
    totals = {
        'all': queryset.count(),
        'community_facilitator': queryset.filter(facilitator_type='community_facilitator').count(),
        'technical_facilitator': queryset.filter(facilitator_type='technical_facilitator').count(),
    }
    if selected_type in FACILITATOR_TYPES:
        queryset = queryset.filter(facilitator_type=selected_type)
    if status == 'active':
        queryset = queryset.filter(active=True)
    elif status == 'inactive':
        queryset = queryset.filter(active=False)
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(email__icontains=search) | Q(phone__icontains=search)
                                   | Q(code__icontains=search) | Q(username__icontains=search))

    # Rows per page chosen above the table ("all" = a single page).
    per_page = request.GET.get('per_page', str(DEFAULT_PER_PAGE))
    if per_page != 'all' and (not per_page.isdigit() or int(per_page) not in PER_PAGE_CHOICES):
        per_page = str(DEFAULT_PER_PAGE)
    ordered = queryset.order_by('name', 'username')
    size = max(ordered.count(), 1) if per_page == 'all' else int(per_page)
    page = Paginator(ordered, size).get_page(request.GET.get('page'))
    facilitators = list(page.object_list)
    projects_by_facilitator = _project_ids_by_facilitator([f.pk for f in facilitators])
    # Only the projects of the page (selection + linked projects the user works on) are listed.
    project_names = dict(Project.objects.filter(
        pk__in={pid for ids in projects_by_facilitator.values() for pid in ids} & set(scope.available_ids))
        .values_list('pk', 'name'))
    rows = [{
        'facilitator': f,
        'type_label': _type_label(f),
        'sex_label': SEXES.get((f.sex or '').upper()[:1], f.sex or '-'),
        'village_count': len(_village_ids(f)),
        'projects': sorted(project_names[pid] for pid in projects_by_facilitator.get(f.pk, ()) if pid in project_names),
    } for f in facilitators]

    query = request.GET.copy()
    query.pop('page', None)
    query['per_page'] = per_page
    # Same filters, without the page size: used by the "Show" selector to build its links.
    base_query = query.copy()
    base_query.pop('per_page', None)
    return render(request, 'assignments/facilitator_list.html', {
        'per_page': per_page, 'per_page_choices': PER_PAGE_CHOICES, 'base_query': base_query.urlencode(),
        'title': gettext("Facilitators"),
        'active_level1': 'facilitators',
        'breadcrumb': [{'url': '', 'title': gettext("Facilitators")}],
        'rows': rows, 'page': page, 'totals': totals, 'types': FACILITATOR_TYPES,
        'selected_type': selected_type, 'search': search, 'status': status, 'query': query.urlencode(),
        **scope.context(),
    })


@login_required
@project_required
def facilitator_profile(request, pk):
    scope = ProjectScope(request)
    facilitator = _facilitators().filter(pk=pk).first()
    if facilitator is None or facilitator.pk not in facilitator_ids_in_scope(scope.available_ids):
        raise Http404

    stabilized = {int(v) for v in facilitator.stabilization_administrative_ids or [] if str(v).isdigit()}
    additional = {int(v) for v in facilitator.additional_administrative_ids or [] if str(v).isdigit()}
    villages = []
    levels = (AdministrativeLevel.objects.filter(pk__in=_village_ids(facilitator))
              .select_related('parent__parent__parent__parent', 'cvd').order_by('name'))
    for level in levels:
        chain = _ancestors(level)
        villages.append({
            'level': level,
            'canton': chain.get('Canton'), 'commune': chain.get('Commune'), 'region': chain.get('Region'),
            'stabilized': level.pk in stabilized, 'additional': level.pk in additional,
        })

    assignments = (AssignAdministrativeLevelToFacilitator.objects.filter(facilitator_id=str(facilitator.pk),
                                                                        project_id__in=scope.available_ids)
                   .select_related('administrative_level', 'project').order_by('-activated', '-assign_date'))
    project_ids = _project_ids_by_facilitator([facilitator.pk]).get(facilitator.pk, set()) & set(scope.available_ids)
    projects = Project.objects.filter(pk__in=project_ids).order_by('name')

    regions = sorted({v['region'].name for v in villages if v['region']})
    communes = sorted({v['commune'].name for v in villages if v['commune']})
    return render(request, 'assignments/facilitator_profile.html', {
        'title': facilitator.name or facilitator.username,
        'active_level1': 'facilitators',
        'breadcrumb': [{'url': reverse('animateurs:list'), 'title': gettext("Facilitators")},
                       {'url': '', 'title': facilitator.name or facilitator.username}],
        'facilitator': facilitator,
        'type_label': _type_label(facilitator),
        'sex_label': SEXES.get((facilitator.sex or '').upper()[:1], facilitator.sex or '-'),
        'villages': villages, 'assignments': assignments, 'projects': projects,
        'regions': regions, 'communes': communes,
        'stats': {
            'villages': len(villages),
            'stabilized': sum(v['stabilized'] for v in villages),
            'active_assignments': sum(1 for a in assignments if a.activated),
            'projects': len(project_ids),
        },
    })
