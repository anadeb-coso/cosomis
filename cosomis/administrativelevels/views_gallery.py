""""Gallery" menu: "Investment cycle" (DCC task attachments) and "Infrastructures" (subproject files) galleries,
for one locality (village, CVD, geographical unit, canton... region) or everywhere; and the photos of the
profile headers. Same presentation as the DCC web galleries (/administrative-levels/documents/ and /works/):
type buttons, active filter chips, card grid with infinite scroll (htmx), viewer with previous / next."""
import re

import requests
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext, gettext_lazy as _
from django.views.generic import TemplateView

from administrativelevels.functions_gallery import (
    CYCLE, DOCUMENT, KOBO_PREFIX, PHOTO, SOURCES, WORKS, cycle_files, display_url, extension, file_view_url,
    gallery_url, is_allowed_url, preview_photos, raw_url, scope_from_params, works_files,
)
from administrativelevels.functions_profile import scope_project_ids
from administrativelevels.models import AdministrativeLevel
from cosomis.mixins import PageMixin

PAGE_SIZE = 36
GEO_LEVELS = [('region', 'Region', _("Region")), ('prefecture', 'Prefecture', _("Prefecture")),
              ('commune', 'Commune', _("Commune")), ('canton', 'Canton', _("Canton")), ('village', 'Village', _("Village"))]
# Above this number of villages, the profile header shows only the infrastructure photos (reading the
# CouchDB databases of a whole region would delay the header too much).
PREVIEW_CYCLE_MAX_VILLAGES = 300


def _kobo_headers():
    from reports.subprojects.views_docx import KOBO_HEADERS
    return KOBO_HEADERS


class GalleryView(PageMixin, LoginRequiredMixin, TemplateView):
    template_name = 'gallery/gallery.html'
    grid_template_name = 'gallery/_grid.html'
    active_level1 = 'gallery'
    source = CYCLE

    def get_template_names(self):
        return [self.grid_template_name if self.is_htmx() else self.template_name]

    def is_htmx(self):
        return self.request.headers.get('HX-Request') == 'true'

    def url_without(self, *keys, **extra):
        query = self.request.GET.copy()
        for key in ('page',) + keys:
            query.pop(key, None)
        for key, value in extra.items():
            query[key] = value
        return f"{self.request.path}?{query.urlencode()}" if query else self.request.path

    def files(self, scope, project_ids):
        search = (self.request.GET.get('q') or '').strip()
        if self.source == WORKS:
            files = works_files(scope, project_ids, search)
        else:
            files = cycle_files(scope, project_ids)
            if search:
                needle = search.lower()
                files = [f for f in files if needle in ' '.join([f['name'], f['context'], f['place'], f['phase'],
                                                                 f['activity']]).lower()]
        kind = self.request.GET.get('type')
        if kind == PHOTO:
            files = [f for f in files if f['kind'] == 'image']
        elif kind == DOCUMENT:
            files = [f for f in files if f['kind'] != 'image']
        return files

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        scope_projects, project_ids = scope_project_ids(self.request)
        scope = scope_from_params(self.request.GET)
        needs_scope = self.source == CYCLE and scope is None
        files = [] if needs_scope else self.files(scope, project_ids)

        paginator = Paginator(files, PAGE_SIZE)
        page_number = int(self.request.GET.get('page')) if str(self.request.GET.get('page') or '').isdigit() else 1
        items = []
        if not (self.is_htmx() and page_number > paginator.num_pages):
            page = paginator.get_page(page_number)
            items = list(page.object_list)
            if page.has_next():
                context['next_page_url'] = self.url_without(page=page.next_page_number())
        for item in items:
            item['src'] = display_url(item['url'])
            item['open_url'] = file_view_url(item['url'])
            item['download_url'] = file_view_url(item['url'], download=True, name=item['name'])

        title = str(SOURCES[self.source])
        context.update({
            'title': title, 'source': self.source, 'sources': [
                {'key': key, 'label': label, 'active': key == self.source, 'url': gallery_url(key, scope)}
                for key, label in SOURCES.items()],
            'active_level2': self.source, 'scope': scope, 'needs_scope': needs_scope,
            'attachments': items, 'total_count': paginator.count, 'no_results': paginator.count == 0 and not needs_scope,
            'type_links': {'active': self.request.GET.get('type') or 'all', 'all': self.url_without('type'),
                           'Photo': self.url_without('type', type=PHOTO), 'Document': self.url_without('type', type=DOCUMENT)},
            'chips': self.chips(scope, scope_projects), 'geo_selects': self.geo_selects(scope),
            'search': self.request.GET.get('q') or '',
            'breadcrumb': [{'url': '', 'title': gettext("Gallery")}, {'url': '', 'title': title}],
            **scope_projects.context(),
        })
        return context

    def chips(self, scope, scope_projects):
        chips = []
        if scope is not None:
            chips.append({'label': scope.label, 'url': scope.profile_url,
                          'remove_url': self.url_without('level', 'cvd', 'unit', *[k for k, _t, _l in GEO_LEVELS])})
        if scope_projects.selected_id:
            name = next((p.name for p in scope_projects.projects if p.pk == scope_projects.selected_id), '')
            chips.append({'label': f"{gettext('Project')} : {name}", 'remove_url': self.url_without('project')})
        if self.request.GET.get('q'):
            chips.append({'label': f"« {self.request.GET['q']} »", 'remove_url': self.url_without('q')})
        return chips

    def geo_selects(self, scope):
        """Region > ... > Village lists of the filter form, preset with the scope when it is a level."""
        chain = {}
        level = scope.obj if scope is not None and scope.kind == 'level' else None
        if scope is not None and scope.kind in ('cvd', 'unit'):
            village = AdministrativeLevel.objects.filter(pk__in=list(scope.villages)[:1]).first()
            level = village.parent if village else None
        while level is not None:
            chain[level.type] = level
            level = level.parent
        selects, parent = [], None
        for key, level_type, label in GEO_LEVELS:
            if key == 'region':
                options = AdministrativeLevel.objects.filter(type=level_type)
            elif parent is not None:
                options = AdministrativeLevel.objects.filter(parent=parent, type=level_type)
            else:
                options = AdministrativeLevel.objects.none()
            selected = chain.get(level_type)
            selects.append({'key': key, 'label': label, 'selected': selected.pk if selected else None,
                            'options': list(options.order_by('name').values_list('pk', 'name')),
                            'disabled': key != 'region' and parent is None})
            parent = selected
        return selects


class CycleGalleryView(GalleryView):
    source = CYCLE


class WorksGalleryView(GalleryView):
    source = WORKS


@login_required
def gallery_children(request):
    """Sub-levels of a level, for the Region > ... > Village lists of the filter form."""
    parent = request.GET.get('parent')
    if not str(parent or '').isdigit():
        return JsonResponse({'values': []})
    values = list(AdministrativeLevel.objects.filter(parent_id=int(parent)).order_by('name').values('id', 'name'))
    return JsonResponse({'values': values})


@login_required
def gallery_file(request):
    """A file of the galleries: S3 files are opened directly; Kobo files are read with the API token; with
    `download=1` the file is sent as an attachment named "<label><extension>". Only the S3 bucket of the
    platform and Kobo are accepted."""
    url = raw_url(request.GET.get('url'))
    if not url or not is_allowed_url(url):
        return HttpResponseBadRequest("URL not allowed")
    is_kobo = url.startswith(KOBO_PREFIX)
    download = request.GET.get('download') == '1'
    if not is_kobo and not download:
        return HttpResponseRedirect(url)
    try:
        upstream = requests.get(url, headers=_kobo_headers() if is_kobo else None, timeout=60)
        upstream.raise_for_status()
    except requests.RequestException:
        raise Http404
    response = HttpResponse(upstream.content, content_type=upstream.headers.get('Content-Type') or 'application/octet-stream')
    if download:
        ext = extension(url) or (upstream.headers.get('Content-Type', '').split('/')[-1].split(';')[0] if is_kobo else '')
        name = re.sub(r'[\\/:*?"<>|\r\n]+', ' ', request.GET.get('name') or 'fichier').strip()[:150] or 'fichier'
        filename = f"{name}.{ext}" if ext and not name.lower().endswith('.' + ext.lower()) else name
        from django.utils.http import content_disposition_header
        response['Content-Disposition'] = content_disposition_header(True, filename)
    else:
        response['Cache-Control'] = 'private, max-age=86400'
    return response


@login_required
def gallery_preview(request):
    """Photos of the header of a profile page (up to 5), as an HTML fragment loaded after the page."""
    scope = scope_from_params(request.GET)
    if scope is None:
        raise Http404
    _scope, project_ids = scope_project_ids(request)
    with_cycle = len(scope.villages) <= PREVIEW_CYCLE_MAX_VILLAGES
    photos = preview_photos(scope, project_ids, with_cycle=with_cycle)
    project = request.GET.get('project')
    for photo in photos:
        photo['src'] = display_url(photo['url'])
        photo['gallery_url'] = gallery_url(photo['source'], scope, type=PHOTO, project=project)
    return render(request, 'gallery/_hero_photos.html', {'photos': photos, 'scope': scope})
