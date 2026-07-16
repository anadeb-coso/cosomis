from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import generic

from cosomis.mixins import PageMixin
from usermanager.permissions import AccountantPermissionRequiredMixin, FinancialPermissionRequiredMixin

from financial.models.supporting_document import SupportingDocument
from financial.models.financial import Disbursement, DisbursementRequest
from financial.forms import SupportingDocumentForm, SupportingDocumentActivityFormSet
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
            form.save()
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
            form.save()
            formset.save()
            return redirect('financial:supporting_document_detail', pk=instance.pk)
        self.form_mixin = form
        self.formset_mixin = formset
        return self.get(request, *args, **kwargs)


class SupportingDocumentDeleteView(PageMixin, LoginRequiredMixin, FinancialPermissionRequiredMixin, generic.DeleteView):
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


class SupportingDocumentDetailView(PageMixin, LoginRequiredMixin, generic.DetailView):
    model = SupportingDocument
    template_name = 'supporting_document_detail.html'
    context_object_name = 'supporting_document'
    title = _('Supporting document')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['lines'] = self.object.supportingdocumentactivity_set.all()
        return ctx


class SupportingDocumentExportView(PageMixin, LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        return export_supporting_document(_filtered_supporting_documents(request.GET))
