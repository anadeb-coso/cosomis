"""Import des niveaux administratifs depuis un fichier : envoi du fichier -> aperçu -> confirmation.

Les lignes lues sont gardées en session entre l'aperçu et la confirmation ; le traitement est relancé à la
confirmation (sur l'état actuel de la base) puis enregistré. À la confirmation, les niveaux du fichier (créés et
existants) peuvent être liés au projet courant, comme la sélection des niveaux administratifs d'un projet dans
l'admin Django.
"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from administrativelevels.functions_import_admin_levels import (
    FRONTALIER_COLUMN, LEVEL_COLUMNS, RURAL_COLUMN, ImportFileError, link_levels_to_project, process_rows,
    project_link_counts, read_import_file, rows_from_columns,
)
from cosomis.mixins import PageMixin
from subprojects.models import Project
from usermanager.permissions import AdminPermissionRequiredMixin

SESSION_KEY = 'administrative_levels_import'


class AdministrativeLevelImportView(PageMixin, LoginRequiredMixin, AdminPermissionRequiredMixin, TemplateView):
    template_name = 'administrativelevel_import.html'
    title = _('Import administrative levels')
    active_level1 = 'administrative_levels'
    breadcrumb = [
        {'url': reverse_lazy('administrativelevels:list'), 'title': _('Administrative levels')},
        {'url': '', 'title': title},
    ]

    def get_project(self):
        project_id = self.request.session.get('project_id')
        return Project.objects.filter(id=project_id).first() if project_id else None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['level_columns'] = [column for column, _type in LEVEL_COLUMNS]
        context['frontalier_column'] = FRONTALIER_COLUMN
        context['rural_column'] = RURAL_COLUMN
        return context

    def get(self, request, *args, **kwargs):
        stored = request.session.get(SESSION_KEY)
        if request.GET.get('action') == 'preview' and stored:
            result = process_rows(stored['rows'])
            project = self.get_project()
            return self.render_to_response(self.get_context_data(
                result=result, counts=result['counts'], stored=stored, project=project,
                link_counts=project_link_counts(result, project),
            ))
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        url = reverse_lazy('administrativelevels:administrative_levels_import')
        action = request.POST.get('action')
        if action == 'cancel':
            request.session.pop(SESSION_KEY, None)
            messages.info(request, _('Import cancelled: nothing has been saved.'))
            return redirect(url)

        if action == 'confirm':
            stored = request.session.get(SESSION_KEY)
            if not stored:
                messages.warning(request, _('No file to import: load the file again.'))
                return redirect(url)
            result = process_rows(stored['rows'], apply=True)
            request.session.pop(SESSION_KEY, None)

            linked = 0
            project = self.get_project()
            if project is not None and request.POST.get('link_to_project'):
                linked = link_levels_to_project(project, result['created_ids'] | result['existing_ids'])

            counts = result['counts']
            messages.success(request, _(
                'Import done: %(new)s administrative level(s) created, %(existing)s already existing, '
                '%(villages)s village(s) updated.') % {
                    'new': counts['new'], 'existing': counts['existing'], 'villages': counts['villages_updated']})
            if project is not None and request.POST.get('link_to_project'):
                messages.success(request, _('%(linked)s administrative level(s) linked to the project %(project)s.') % {
                    'linked': linked, 'project': project.name})
            if result['errors']:
                messages.warning(request, _('%(n)s line(s) not saved:') % {'n': len(result['errors'])}
                                 + "\n" + "\n".join(result['errors']))
            return redirect('administrativelevels:list')

        uploaded = request.FILES.get('file')
        if not uploaded:
            messages.warning(request, _('Choose a file to import.'))
            return redirect(url)
        try:
            rows = rows_from_columns(read_import_file(uploaded, request.POST.get('sheet_name') or None))
        except ImportFileError as exc:
            messages.error(request, str(exc))
            return redirect(url)
        if not rows:
            messages.warning(request, _('The file is empty.'))
            return redirect(url)
        request.session[SESSION_KEY] = {
            'file_name': uploaded.name, 'sheet_name': request.POST.get('sheet_name') or '', 'rows': rows,
        }
        return redirect(f"{url}?action=preview")
