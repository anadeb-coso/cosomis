"""Files of a subproject or a structure (/subprojects/files/files/<id>): gallery of its photos and documents (same
presentation as the "Gallery" menu), with the review actions: validate / invalidate (with a comment), main file,
special file, comments history; download of one file or of all the files shown (ZIP).

The files of a subproject (kit) include those of its structures."""
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from urllib.parse import urlencode

import requests
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.translation import gettext, gettext_lazy as _
from django.views.generic import TemplateView
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from administrativelevels.functions_gallery import (
    KOBO_PREFIX, display_url, extension, file_kind, file_view_url, format_date, is_allowed_url, raw_url,
)
from cosomis.mixins import PageMixin
from subprojects.models import FileComment, Subproject, SubprojectFile
from subprojects.serializers import FileCommentsSerializer, SubprojectFileSerializer

PAGE_SIZE = 36
ZIP_MAX_FILES = 300
STATUSES = {
    'validated': (_("Validated"), Q(validated=True)),
    'invalidated': (_("Invalidated"), Q(validated=False)),
    'pending': (_("Not reviewed"), Q(validated__isnull=True)),
}
# Old values of the `validated_status` parameter (links already shared).
LEGACY_STATUSES = {'Validated': 'validated', 'Invalidated': 'invalidated', 'not_seen': 'pending', 'Not_seen': 'pending'}


def can_review(user):
    """Validation, main / special file: users of a group (as before) and super administrators."""
    return user.is_authenticated and (user.is_superuser or user.groups.exists())


def subproject_files(subproject):
    """Files of the subproject and, for a kit, of its structures."""
    ids = [subproject.pk] + list(subproject.linked_subprojects.values_list('pk', flat=True))
    return (SubprojectFile.objects.filter(subproject_id__in=ids)
            .exclude(url__isnull=True).exclude(url='')
            .select_related('subproject', 'subproject__location_subproject_realized', 'subproject_step', 'subproject_level__subproject_step', 'user')
            .annotate(comments_count=Count('filecomment')))


def file_label(file):
    if file.subproject_level_id:
        level = file.subproject_level
        return f"{level.wording} ({level.percent} %)" if getattr(level, 'percent', None) is not None else level.wording
    if file.subproject_step_id:
        return file.subproject_step.wording
    return file.name or file.description or ''


def file_date(file):
    """Date of a file for file names (no slash)."""
    return file.date_taken.strftime('%d-%m-%Y') if file.date_taken else ''


def person(data):
    """Name of the author recorded in create_by_user / update_by_user (JSON), '' if unknown."""
    if not isinstance(data, dict) or data.get('type') is None:
        return ''
    if data.get('last_name') or data.get('first_name'):
        return f"{data.get('last_name') or ''} {data.get('first_name') or ''}".strip()
    return data.get('name') or ''


def decorate(file, subproject):
    """Display fields of a file for the card and the viewer."""
    file.kind = file_kind(file.url, file.file_type)
    file.ext = extension(file.url).upper()
    file.raw_url = raw_url(file.url)
    file.src = display_url(file.url)
    file.label = file_label(file)
    file.open_url = file_view_url(file.url)
    file.download_url = file_view_url(file.url, download=True,
                                      name=f"{file.label or file.name} ({file_date(file)})")
    file.date = format_date(file.date_taken)
    file.taken_by = person(file.create_by_user)
    file.updated_by = person(file.update_by_user)
    file.is_structure = file.subproject_id != subproject.pk
    file.status = 'validated' if file.validated else ('invalidated' if file.validated is False else 'pending')
    return file


def filtered_files(subproject, params):
    """Files shown for the GET parameters: type (Photo / Document), status, step, structure; main file first, then
    the files to review, then the newest."""
    files = subproject_files(subproject)
    status_key = params.get('status') or LEGACY_STATUSES.get(params.get('validated_status') or '', '')
    if status_key in STATUSES:
        files = files.filter(STATUSES[status_key][1])
    step = params.get('step')
    if str(step or '').isdigit():
        files = files.filter(Q(subproject_step_id=int(step)) | Q(subproject_level__subproject_step_id=int(step)))
    structure = params.get('structure')
    if str(structure or '').isdigit():
        files = files.filter(subproject_id=int(structure))
    files = [decorate(f, subproject) for f in files.order_by('-principal', '-date_taken', '-id')]
    kind = params.get('type')
    if kind == 'Photo':
        files = [f for f in files if f.kind == 'image']
    elif kind == 'Document':
        files = [f for f in files if f.kind != 'image']
    return files


class FilesListView(PageMixin, LoginRequiredMixin, TemplateView):
    template_name = 'subproject_files/files.html'
    grid_template_name = 'subproject_files/_grid.html'
    active_level1 = 'infrastructures'

    def dispatch(self, request, *args, **kwargs):
        self.subproject = get_object_or_404(Subproject, pk=kwargs['subproject_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return [self.grid_template_name if self.request.headers.get('HX-Request') == 'true' else self.template_name]

    def url_with(self, *drop, **values):
        query = self.request.GET.copy()
        for key in ('page', 'validated_status') + drop:
            query.pop(key, None)
        for key, value in values.items():
            query[key] = value
        return f"{self.request.path}?{query.urlencode()}" if query else self.request.path

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET
        files = filtered_files(self.subproject, params)
        paginator = Paginator(files, PAGE_SIZE)
        page_number = int(params['page']) if str(params.get('page') or '').isdigit() else 1
        items = []
        if not (self.request.headers.get('HX-Request') == 'true' and page_number > paginator.num_pages):
            page = paginator.get_page(page_number)
            items = list(page.object_list)
            if page.has_next():
                context['next_page_url'] = self.url_with(page=page.next_page_number())

        all_files = [decorate(f, self.subproject) for f in subproject_files(self.subproject)]
        status_key = params.get('status') or LEGACY_STATUSES.get(params.get('validated_status') or '', '')
        type_key = params.get('type') or 'all'
        steps = {}
        for f in all_files:
            step = f.subproject_level.subproject_step if f.subproject_level_id else f.subproject_step
            if step is not None:
                steps[step.pk] = step.wording
        structures = list(self.subproject.linked_subprojects.order_by('full_title_of_approved_subproject')
                          .values_list('pk', 'full_title_of_approved_subproject'))
        zip_query = params.copy()
        zip_query.pop('page', None)
        zip_query['subproject_id'] = self.subproject.pk

        context.update({
            'title': gettext("Files"), 'hide_content_header': True, 'subproject': self.subproject,
            'attachments': items, 'total_count': paginator.count, 'no_results': paginator.count == 0,
            'can_review': can_review(self.request.user),
            'stats': {
                'total': len(all_files), 'photos': sum(f.kind == 'image' for f in all_files),
                'validated': sum(f.status == 'validated' for f in all_files),
                'invalidated': sum(f.status == 'invalidated' for f in all_files),
                'pending': sum(f.status == 'pending' for f in all_files),
            },
            'type_links': [{'key': key, 'label': label, 'icon': icon, 'active': type_key == key,
                            'url': self.url_with('type', **({'type': key} if key != 'all' else {}))}
                           for key, label, icon in (('all', _("All"), ''), ('Photo', _("Photos"), 'fa-image'),
                                                    ('Document', _("Documents"), 'fa-file-alt'))],
            'status_links': [{'key': '', 'label': _("All statuses"), 'active': status_key not in STATUSES,
                              'url': self.url_with('status')}] + [
                {'key': key, 'label': label, 'active': status_key == key, 'url': self.url_with('status', status=key)}
                for key, (label, _q) in STATUSES.items()],
            'steps': sorted(steps.items(), key=lambda item: item[1]), 'selected_step': params.get('step') or '',
            'structures': structures, 'selected_structure': params.get('structure') or '',
            'zip_url': f"{reverse('subprojects:files:files_download_zip')}?{zip_query.urlencode()}",
            'zip_max_files': ZIP_MAX_FILES,
        })
        return context


@login_required
def file_card(request, file_id):
    """One card, rendered again after an action (validation, main file...)."""
    file = get_object_or_404(subproject_files(get_object_or_404(SubprojectFile, pk=file_id).subproject), pk=file_id)
    subproject = Subproject.objects.get(pk=request.GET['subproject']) if str(request.GET.get('subproject') or '').isdigit() else file.subproject
    return render(request, 'subproject_files/_card.html', {
        'attachment': decorate(file, subproject), 'can_review': can_review(request.user)})


class ReviewPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return can_review(request.user)


class ToggleValidationFileView(APIView):
    """Validate (action=validated) or invalidate (action=invalidated, comment required unless no_comment=true) a
    file; the action is recorded in its comments history. An invalidated file is no longer the main file."""
    permission_classes = (permissions.IsAuthenticated, ReviewPermission)

    def post(self, request, *args, **kwargs):
        file = SubprojectFile.objects.filter(pk=request.GET.get('file_id')).first()
        action = request.GET.get('action')
        if file is None or action not in ('validated', 'invalidated'):
            return Response({'error': gettext('Review your request')}, status.HTTP_400_BAD_REQUEST)
        comment = (request.POST.get('invalidation_comment') or '').strip()
        no_comment = request.POST.get('no_comment') in ('true', 'True', '1', 'on')
        if action == 'invalidated' and not comment and not no_comment:
            return Response({'error': gettext('Add a comment or tick “Invalidate without comment”.')},
                            status.HTTP_400_BAD_REQUEST)
        file.validated = action == 'validated'
        file.review = True
        fields = ['validated', 'review']
        if not file.validated and file.principal:
            file.principal = False
            fields.append('principal')
        SubprojectFile.objects.bulk_update([file], fields=fields)
        FileComment.objects.create(
            file=file, user=request.user,
            type='comment_validated' if file.validated else 'comment_invalidated',
            comment=comment or gettext("No comment"))
        return Response(SubprojectFileSerializer(file).data, status.HTTP_200_OK)


class FileCommentsListView(APIView):
    """Comments and review actions of a file, oldest first."""
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        file_id = request.GET.get('file_id')
        if not str(file_id or '').isdigit():
            return Response({'error': gettext('Review your request')}, status.HTTP_400_BAD_REQUEST)
        comments = FileComment.objects.filter(file_id=int(file_id)).select_related('user', 'file').order_by('created_date')
        return Response(FileCommentsSerializer(comments, many=True).data, status.HTTP_200_OK)


class TogglePrincipalFileView(APIView):
    """Make a file the main file of its subproject (the others lose the status), or remove the status.
    An invalidated file cannot be the main file."""
    permission_classes = (permissions.IsAuthenticated, ReviewPermission)

    def post(self, request, *args, **kwargs):
        file = SubprojectFile.objects.filter(pk=request.GET.get('file_id')).first()
        if file is None:
            return Response({'error': gettext('Review your request')}, status.HTTP_400_BAD_REQUEST)
        principal = request.POST.get('principal') in ('true', 'True', '1', 'on')
        if principal and file.validated is False:
            return Response({'error': gettext("You can't put this file invalidated principal")}, status.HTTP_400_BAD_REQUEST)
        if principal:
            SubprojectFile.objects.filter(subproject_id=file.subproject_id).exclude(pk=file.pk).update(principal=False)
        file.principal = principal
        SubprojectFile.objects.bulk_update([file], fields=['principal'])
        return Response(SubprojectFileSerializer(file).data, status.HTTP_200_OK)


class ToggleSpecialFileView(APIView):
    """Mark a file as special (used in the important documents), or remove the mark."""
    permission_classes = (permissions.IsAuthenticated, ReviewPermission)

    def post(self, request, *args, **kwargs):
        file = SubprojectFile.objects.filter(pk=request.GET.get('file_id')).first()
        if file is None:
            return Response({'error': gettext('Review your request')}, status.HTTP_400_BAD_REQUEST)
        file.special = request.POST.get('special') in ('true', 'True', '1', 'on')
        SubprojectFile.objects.bulk_update([file], fields=['special'])
        return Response(SubprojectFileSerializer(file).data, status.HTTP_200_OK)


def _fetch(url):
    """Content and type of a file of the platform (S3 bucket or Kobo, with the API token)."""
    from reports.subprojects.views_docx import KOBO_HEADERS
    url = raw_url(url)
    if not is_allowed_url(url):
        return None, None
    try:
        response = requests.get(url, headers=KOBO_HEADERS if url.startswith(KOBO_PREFIX) else None, timeout=60)
        response.raise_for_status()
    except requests.RequestException:
        return None, None
    return response.content, response.headers.get('Content-Type') or 'application/octet-stream'


def _safe_name(name):
    return re.sub(r'[\\/:*?"<>|\r\n]+', ' ', str(name or '')).strip()[:120] or 'fichier'


@login_required
def file_download(request, url):
    """Old download link (/subprojects/files/detail/files/<url>/download/): only the files of the platform."""
    content, content_type = _fetch(url)
    if content is None:
        return HttpResponseBadRequest(gettext("Failed to download the file."))
    from django.utils.http import content_disposition_header
    name = raw_url(url).rstrip('/').rsplit('/', 1)[-1] or 'fichier'
    if '.' not in name:
        name = f"{name}.{content_type.split('/')[-1].split(';')[0]}"
    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = content_disposition_header(True, name)
    return response


@login_required
def files_download_zip(request):
    """ZIP of the files shown on the files page (same filters, `subproject_id`), or of the files `ids` (old links).
    Each file is named "<label> (<date>)<extension>"; files that cannot be read are listed in _errors.txt."""
    if str(request.GET.get('subproject_id') or '').isdigit():
        subproject = get_object_or_404(Subproject, pk=int(request.GET['subproject_id']))
        files = filtered_files(subproject, request.GET)
        archive_name = _safe_name(f"{subproject.number or subproject.pk} - {subproject.full_title_of_approved_subproject}")[:80]
    else:
        ids = [int(i) for i in (request.GET.get('ids') or '').split(',') if i.strip().isdigit()]
        files = list(SubprojectFile.objects.filter(pk__in=ids).select_related('subproject_step', 'subproject_level'))
        for f in files:
            f.label = file_label(f)
        archive_name = 'fichiers'
    if not files:
        raise Http404
    # Files are read in parallel (network I/O), then written in the order of the page.
    files = files[:ZIP_MAX_FILES]
    with ThreadPoolExecutor(max_workers=8) as pool:
        contents = list(pool.map(lambda f: _fetch(f.url), files))
    buffer, used, errors = BytesIO(), set(), []
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for f, (content, content_type) in zip(files, contents):
            label = _safe_name(f"{f.label or f.name} ({file_date(f)})")
            if content is None:
                errors.append(f"{label} : {raw_url(f.url)}")
                continue
            ext = extension(f.url) or (content_type or '').split('/')[-1].split(';')[0] or 'bin'
            name, counter = f"{label}.{ext}", 2
            while name in used:
                name, counter = f"{label} ({counter}).{ext}", counter + 1
            used.add(name)
            archive.writestr(name, content)
        if errors:
            archive.writestr('_errors.txt', gettext("Files that could not be downloaded:") + "\n" + "\n".join(errors))
    from django.utils.http import content_disposition_header
    response = HttpResponse(buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = content_disposition_header(True, f"{archive_name}.zip")
    return response
