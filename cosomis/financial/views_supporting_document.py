import os

import requests
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import generic

from cosomis.mixins import PageMixin, SoftDeleteViewMixin
from usermanager.permissions import AccountantPermissionRequiredMixin, FinancialPermissionRequiredMixin

from financial.models.supporting_document import SupportingDocument, SupportingDocumentActivity, SupportingDocumentActivityFile
from financial.models.financial import Disbursement, DisbursementRequest
from financial.forms import SupportingDocumentForm, SupportingDocumentActivityFormSet, SupportingDocumentActivityFileEditFormSet
from financial.exports import export_supporting_document
from financial.list_filters import build_filter_context


def _filtered_supporting_documents(get):
    qs = SupportingDocument.objects.all().order_by('-document_date')
    search = get.get('search', None)
    if search:
        qs = qs.filter(Q(reference__icontains=search))

    project_id = get.get('project')
    if project_id:
        qs = qs.filter(
            Q(disbursement__disbursement_request__project_id=project_id) |
            Q(disbursement_request__project_id=project_id)
        )
    funding_id = get.get('funding')
    if funding_id:
        qs = qs.filter(
            Q(disbursement__disbursement_request__funding_id=funding_id) |
            Q(disbursement_request__funding_id=funding_id)
        )
    category_id = get.get('category')
    if category_id:
        qs = qs.filter(supportingdocumentactivity__activity__component__category_id=category_id)
    component_id = get.get('component')
    if component_id:
        qs = qs.filter(supportingdocumentactivity__activity__component_id=component_id)
    disbursement_request_id = get.get('disbursement_request')
    if disbursement_request_id:
        qs = qs.filter(
            Q(disbursement__disbursement_request_id=disbursement_request_id) |
            Q(disbursement_request_id=disbursement_request_id)
        )
    disbursement_id = get.get('disbursement')
    if disbursement_id:
        qs = qs.filter(disbursement_id=disbursement_id)

    return qs.distinct()


class SupportingDocumentListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = SupportingDocument
    queryset = []
    template_name = 'supporting_document_list.html'
    context_object_name = 'supporting_documents'
    title = _('Supporting documents')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_queryset(self):
        page_number = self.request.GET.get('page', None)
        return Paginator(_filtered_supporting_documents(self.request.GET), 100).get_page(page_number)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(build_filter_context(
            self.request, projects=True, fundings=True, categories=True,
            components=True, disbursement_requests=True, disbursements=True,
        ))
        return ctx


class SupportingDocumentFormMixin:
    def _resolve_context(self, request):
        mode = request.GET.get('mode') or request.POST.get('mode') or 'disbursement'
        disbursement_id = request.GET.get('disbursement_id') or request.POST.get('disbursement_id')
        disbursement_request_id = request.GET.get('disbursement_request_id') or request.POST.get('disbursement_request_id')
        project = None
        if mode == 'disbursement_request':
            if disbursement_request_id:
                req = DisbursementRequest.objects.filter(pk=disbursement_request_id).first()
                project = req.project if req else None
        else:
            if disbursement_id:
                disb = Disbursement.objects.filter(pk=disbursement_id).select_related('disbursement_request').first()
                project = disb.project if disb else None
        return mode, disbursement_id, disbursement_request_id, project


class SupportingDocumentCreateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, SupportingDocumentFormMixin, generic.CreateView):
    model = SupportingDocument
    template_name = 'supporting_document_add.html'
    context_object_name = 'supporting_document'
    title = _('Register a supporting document')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]
    form_class = SupportingDocumentForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        mode, disbursement_id, disbursement_request_id, project = self._resolve_context(self.request)
        context['mode'] = mode
        if getattr(self, 'form_mixin', None):
            context['form'] = self.form_mixin
            context['formset'] = self.formset_mixin
        else:
            form = SupportingDocumentForm(mode=mode)
            if mode == 'disbursement_request' and disbursement_request_id:
                form.fields['disbursement_request'].initial = disbursement_request_id
            elif mode == 'disbursement' and disbursement_id:
                form.fields['disbursement'].initial = disbursement_id
            context['form'] = form
            context['formset'] = SupportingDocumentActivityFormSet(instance=SupportingDocument(), form_kwargs={'project': project})
        return context

    def post(self, request, *args, **kwargs):
        mode, disbursement_id, disbursement_request_id, project = self._resolve_context(request)
        form = SupportingDocumentForm(mode=mode, data=request.POST, files=request.FILES)
        document = form.instance
        if mode == 'disbursement_request' and disbursement_request_id and not form.data.get('disbursement_request'):
            document.disbursement_request_id = disbursement_request_id
        elif mode == 'disbursement' and disbursement_id and not form.data.get('disbursement'):
            document.disbursement_id = disbursement_id
        formset = SupportingDocumentActivityFormSet(request.POST, instance=document, form_kwargs={'project': project})
        if form.is_valid() and formset.is_valid():
            form.save(commit=False)
            document.save(user=request.user)
            formset.save()
            return redirect('financial:supporting_document_detail', pk=document.pk)
        self.form_mixin = form
        self.formset_mixin = formset
        return self.get(request, *args, **kwargs)


class SupportingDocumentUpdateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, SupportingDocumentFormMixin, generic.UpdateView):
    model = SupportingDocument
    template_name = 'supporting_document_add.html'
    context_object_name = 'supporting_document'
    title = _('Update supporting document')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]
    form_class = SupportingDocumentForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        instance = self.get_object()
        mode = 'disbursement_request' if instance.disbursement_request_id else 'disbursement'
        project = instance.project
        context['mode'] = mode
        if getattr(self, 'form_mixin', None):
            context['form'] = self.form_mixin
            context['formset'] = self.formset_mixin
        else:
            context['form'] = SupportingDocumentForm(mode=mode, instance=instance)
            context['formset'] = SupportingDocumentActivityFormSet(instance=instance, form_kwargs={'project': project})
        return context

    def post(self, request, *args, **kwargs):
        instance = self.get_object()
        mode = 'disbursement_request' if instance.disbursement_request_id else 'disbursement'
        project = instance.project
        form = SupportingDocumentForm(mode=mode, data=request.POST, files=request.FILES, instance=instance)
        formset = SupportingDocumentActivityFormSet(request.POST, instance=instance, form_kwargs={'project': project})
        if form.is_valid() and formset.is_valid():
            form.save(commit=False)
            instance.save(user=request.user)
            formset.save()
            return redirect('financial:supporting_document_detail', pk=instance.pk)
        self.form_mixin = form
        self.formset_mixin = formset
        return self.get(request, *args, **kwargs)


class SupportingDocumentDeleteView(PageMixin, LoginRequiredMixin, FinancialPermissionRequiredMixin, SoftDeleteViewMixin, generic.DeleteView):
    """Only the Financial group and superusers may delete a supporting document."""

    model = SupportingDocument
    template_name = 'components/confirm_delete.html'
    title = _('Delete supporting document')
    active_level1 = 'financial'
    success_url = reverse_lazy('financial:supporting_document_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = reverse_lazy('financial:supporting_document_list')
        return context


def _save_document_activity_formset(document, post_data, user):
    """Validates + saves the SupportingDocumentActivityFormSet for `document` -
    shared by the detail page's embedded table and the dedicated activities
    sheet page (mirrors views_ptba._save_activity_formset) so the two can
    never drift. Returns (formset, success)."""
    formset = SupportingDocumentActivityFormSet(post_data, instance=document, form_kwargs={'project': document.project})
    if not formset.is_valid():
        return formset, False
    lines = formset.save(commit=False)
    for line in lines:
        line.save(user=user)
    for obj in formset.deleted_objects:
        obj.delete()
    return formset, True


class SupportingDocumentDetailView(PageMixin, LoginRequiredMixin, generic.DetailView):
    """The 'Justified activities' table is an inline formset directly on this
    page (rows can be added, edited and deleted, then saved together in one
    submit) - see also SupportingDocumentActivitySheetView for the dedicated
    full-page spreadsheet-style editor."""

    model = SupportingDocument
    template_name = 'supporting_document_detail.html'
    context_object_name = 'supporting_document'
    title = _('Supporting document')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        document = self.object
        if getattr(self, 'formset_mixin', None):
            ctx['formset'] = self.formset_mixin
        else:
            ctx['formset'] = SupportingDocumentActivityFormSet(instance=document, form_kwargs={'project': document.project})
        for form in ctx['formset'].forms:
            if form.instance.pk:
                form.instance.files = form.instance.supportingdocumentactivityfile_set.all()
        # Read-only fallback for users without edit rights (template picks
        # between `formset` and `lines` the same way annual_work_plan_detail
        # picks between `formset` and `activities`).
        lines = list(document.supportingdocumentactivity_set.all())
        for line in lines:
            line.files = line.supportingdocumentactivityfile_set.all()
        ctx['lines'] = lines
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = document = self.get_object()
        formset, success = _save_document_activity_formset(document, request.POST, request.user)
        if success:
            return redirect('financial:supporting_document_detail', pk=document.pk)
        self.formset_mixin = formset
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


class SupportingDocumentActivitySheetView(PageMixin, LoginRequiredMixin, generic.DetailView):
    """Dedicated, spreadsheet-style page for a Justificatif's activity lines
    (one row per SupportingDocumentActivity - add/edit/delete rows, save them
    all at once) - reuses the exact same SupportingDocumentActivityFormSet as
    the embedded table on the detail page, so the two never drift."""

    model = SupportingDocument
    template_name = 'supporting_document_activity_sheet.html'
    context_object_name = 'supporting_document'
    title = _('Justified activities sheet')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        document = self.object
        if getattr(self, 'formset_mixin', None):
            ctx['formset'] = self.formset_mixin
        else:
            ctx['formset'] = SupportingDocumentActivityFormSet(instance=document, form_kwargs={'project': document.project})
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = document = self.get_object()
        formset, success = _save_document_activity_formset(document, request.POST, request.user)
        if success:
            messages.success(request, _("Justified activities saved."))
            return redirect('financial:supporting_document_activity_sheet', pk=document.pk)
        self.formset_mixin = formset
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


class SupportingDocumentExportView(PageMixin, LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        return export_supporting_document(_filtered_supporting_documents(request.GET))


class SupportingDocumentActivityFileCreateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.TemplateView):
    """Attach one or more files at once to a Justificatif-Activité line (§
    Fichiers justif. Activités) - a line can carry several files, so this is
    always reached from the parent SupportingDocument's detail page, never a
    standalone list. Each file gets its OWN document type and display name
    (the latter defaulted client-side to the file's own name, minus its
    extension) - submitted as `document_type_<index>` / `file_name_<index>`,
    matching the order of the `files` input - read directly from
    request.POST/request.FILES rather than through a Django Form, since a
    ModelForm can't cleanly validate a variable-length batch under one field."""

    template_name = 'supporting_document_activity_file_add.html'
    title = _('Add files')
    active_level1 = 'financial'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        line = get_object_or_404(SupportingDocumentActivity, pk=self.kwargs['supporting_document_activity_pk'])
        context['line'] = line
        context['document_type_choices'] = SupportingDocumentActivityFile.DocumentType.choices
        return context

    def post(self, request, *args, **kwargs):
        line = get_object_or_404(SupportingDocumentActivity, pk=self.kwargs['supporting_document_activity_pk'])
        files = request.FILES.getlist('files')
        valid_document_types = dict(SupportingDocumentActivityFile.DocumentType.choices)

        if not files:
            messages.error(request, _("Select at least one file."))
            return self.get(request, *args, **kwargs)

        for index in range(len(files)):
            if request.POST.get(f'document_type_{index}') not in valid_document_types:
                messages.error(request, _("Choose a document type for each file."))
                return self.get(request, *args, **kwargs)

        for index, uploaded_file in enumerate(files):
            display_name = (request.POST.get(f'file_name_{index}') or '').strip()
            if not display_name:
                display_name = os.path.splitext(uploaded_file.name)[0]
            SupportingDocumentActivityFile(
                supporting_document_activity=line,
                document_type=request.POST.get(f'document_type_{index}'),
                file=uploaded_file, file_name=display_name,
            ).save(user=request.user)
        return redirect('financial:supporting_document_detail', pk=line.supporting_document_id)


class SupportingDocumentActivityFilesUpdateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.TemplateView):
    """Edit the document type / display name of every file already attached to
    a Justificatif-Activité line at once (§ "bouton modifier fichiers"), and
    delete one or more of them from the same list - the attached file itself
    isn't replaceable here, only its metadata and its presence."""

    template_name = 'supporting_document_activity_files_edit.html'
    title = _('Edit files')
    active_level1 = 'financial'

    def _queryset(self, line):
        return SupportingDocumentActivityFile.objects.filter(supporting_document_activity=line).order_by('pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        line = get_object_or_404(SupportingDocumentActivity, pk=self.kwargs['supporting_document_activity_pk'])
        context['line'] = line
        context['formset'] = self.formset_mixin if getattr(self, 'formset_mixin', None) else SupportingDocumentActivityFileEditFormSet(queryset=self._queryset(line))
        return context

    def post(self, request, *args, **kwargs):
        line = get_object_or_404(SupportingDocumentActivity, pk=self.kwargs['supporting_document_activity_pk'])
        formset = SupportingDocumentActivityFileEditFormSet(request.POST, queryset=self._queryset(line))
        if formset.is_valid():
            for file_obj in formset.save(commit=False):
                file_obj.save(user=request.user)
            for file_obj in formset.deleted_objects:
                file_obj.delete()
            messages.success(request, _("Files updated."))
            return redirect('financial:supporting_document_detail', pk=line.supporting_document_id)
        self.formset_mixin = formset
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)


class SupportingDocumentActivityFileDeleteView(PageMixin, LoginRequiredMixin, FinancialPermissionRequiredMixin, SoftDeleteViewMixin, generic.DeleteView):
    """Only the Financial group and superusers may delete a supporting document activity file."""

    model = SupportingDocumentActivityFile
    template_name = 'components/confirm_delete.html'
    title = _('Delete file')
    active_level1 = 'financial'

    def get_success_url(self):
        return reverse_lazy('financial:supporting_document_detail', kwargs={'pk': self.object.supporting_document_activity.supporting_document_id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = self.get_success_url()
        return context


def _download_file_response(file_field, display_name):
    """Proxies an S3-stored FileField back through Django with a real
    `Content-Disposition: attachment` header (mirrors
    attachments.views.attachment_download_by_id) - the plain HTML `download`
    attribute on a link to the S3 URL directly does NOT force a download for
    a cross-origin file: the browser just opens whatever it knows how to
    render inline (image, PDF...) instead, which is why "Télécharger" in the
    file-preview modal wasn't doing anything. The query string on the S3 URL
    carries request keys, not something to keep - stripped the same way as
    everywhere else this app reads a file URL."""
    if not file_field:
        raise Http404
    url = file_field.url.split('?')[0]
    response = requests.get(url)
    if response.status_code != 200:
        return HttpResponse(_("Failed to download the file."), status=502)

    _root, ext = os.path.splitext(url)
    filename = display_name or os.path.basename(url)
    if ext and not filename.lower().endswith(ext.lower()):
        filename += ext

    out = HttpResponse(response.content, content_type=response.headers.get('content-type'))
    out['Content-Disposition'] = f'attachment; filename="{filename}"'
    return out


class SupportingDocumentFileDownloadView(LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        document = get_object_or_404(SupportingDocument, pk=kwargs['pk'])
        return _download_file_response(document.file, document.file_name)


class SupportingDocumentActivityFileDownloadView(LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        file_obj = get_object_or_404(SupportingDocumentActivityFile, pk=kwargs['pk'])
        return _download_file_response(file_obj.file, file_obj.file_name)
