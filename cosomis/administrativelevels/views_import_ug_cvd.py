"""Import des Unités géographiques et des CVD depuis un fichier : envoi du fichier -> aperçu -> confirmation.

Les lignes lues sont gardées en session entre l'aperçu et la confirmation ; le plan est recalculé à la
confirmation (sur l'état actuel de la base) puis enregistré.
"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from administrativelevels.functions_import_ug_cvd import (
    ImportFileError, apply_import_plan, build_import_plan, missing_villages_csv, read_import_file, rows_to_session,
    template_workbook,
)
from cosomis.mixins import PageMixin
from usermanager.permissions import AdminPermissionRequiredMixin

SESSION_KEY = 'geographical_unit_cvd_import'


class GeographicalUnitCvdImportView(PageMixin, LoginRequiredMixin, AdminPermissionRequiredMixin, TemplateView):
    template_name = 'geographical_unit_cvd_import.html'
    title = _('Import geographical units and CVD')
    active_level1 = 'administrative_levels'
    breadcrumb = [
        {'url': reverse_lazy('administrativelevels:geographical_units_list'), 'title': _('Geographical units')},
        {'url': '', 'title': title},
    ]

    def get(self, request, *args, **kwargs):
        stored = request.session.get(SESSION_KEY)
        action = request.GET.get('action')
        if action == 'template':
            response = HttpResponse(template_workbook(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename="canevas_ug_cvd.xlsx"'
            return response
        if action == 'missing_villages' and stored:
            plan = build_import_plan(stored['rows'])
            response = HttpResponse(missing_villages_csv(plan), content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = 'attachment; filename="villages_introuvables.csv"'
            return response
        if action == 'preview' and stored:
            plan = build_import_plan(stored['rows'])
            return self.render_to_response(self.get_context_data(plan=plan, counts=plan.counts(), stored=stored))
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        if action == 'cancel':
            request.session.pop(SESSION_KEY, None)
            messages.info(request, _('Import cancelled: nothing has been saved.'))
            return redirect('administrativelevels:geographical_unit_cvd_import')

        if action == 'confirm':
            stored = request.session.get(SESSION_KEY)
            if not stored:
                messages.warning(request, _('No file to import: load the file again.'))
                return redirect('administrativelevels:geographical_unit_cvd_import')
            plan = build_import_plan(stored['rows'])
            if not plan.can_be_applied:
                messages.warning(request, _('Nothing can be imported from this file.'))
                return redirect(f"{reverse_lazy('administrativelevels:geographical_unit_cvd_import')}?action=preview")
            done = apply_import_plan(plan, user=request.user)
            request.session.pop(SESSION_KEY, None)
            messages.success(request, _(
                'Import done: %(units_created)s geographical unit(s) created, %(units_updated)s updated; '
                '%(cvds_created)s CVD created, %(cvds_updated)s updated; %(villages)s village(s) attached.') % done)
            return redirect('administrativelevels:geographical_units_list')

        uploaded = request.FILES.get('file')
        if not uploaded:
            messages.warning(request, _('Choose a file to import.'))
            return redirect('administrativelevels:geographical_unit_cvd_import')
        try:
            rows = read_import_file(uploaded, request.POST.get('sheet_name') or None)
        except ImportFileError as exc:
            messages.error(request, str(exc))
            return redirect('administrativelevels:geographical_unit_cvd_import')
        request.session[SESSION_KEY] = {
            'file_name': uploaded.name, 'sheet_name': request.POST.get('sheet_name') or '', 'rows': rows_to_session(rows),
        }
        return redirect(f"{reverse_lazy('administrativelevels:geographical_unit_cvd_import')}?action=preview")
