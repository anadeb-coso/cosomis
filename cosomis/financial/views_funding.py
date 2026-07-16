from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import generic

from cosomis.mixins import PageMixin
from usermanager.permissions import AccountantPermissionRequiredMixin, FinancialPermissionRequiredMixin

from financial.models.funding import Funding
from financial.models.financial import DisbursementRequest, Disbursement
from financial.models.supporting_document import SupportingDocument
from financial.forms import FundingForm
from subprojects.models import Component
from financial.models.planning import Activity
from financial.exports import export_funding
from financial.list_filters import apply_entity_filters, build_filter_context


def _filtered_fundings(get):
    qs = Funding.objects.all()
    search = get.get('search', None)
    if search:
        qs = qs.filter(
            Q(label__icontains=search) |
            Q(identification_number__icontains=search) |
            Q(project__name__icontains=search)
        )
    return apply_entity_filters(qs, get, project='project_id')


class FundingListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = Funding
    queryset = []
    template_name = 'funding_list.html'
    context_object_name = 'fundings'
    title = _('Credits & Grants')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_queryset(self):
        page_number = self.request.GET.get('page', None)
        return Paginator(_filtered_fundings(self.request.GET), 100).get_page(page_number)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(build_filter_context(self.request, projects=True))
        return ctx


class FundingCreateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.CreateView):
    model = Funding
    template_name = 'funding_add.html'
    context_object_name = 'funding'
    title = _('Register a funding')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]
    form_class = FundingForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form_mixin if getattr(self, 'form_mixin', None) else FundingForm()
        return context

    def post(self, request, *args, **kwargs):
        form = FundingForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('financial:funding_list')
        self.form_mixin = form
        return super().get(request, *args, **kwargs)


class FundingUpdateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.UpdateView):
    model = Funding
    template_name = 'funding_add.html'
    context_object_name = 'funding'
    title = _('Update funding')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]
    form_class = FundingForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form_mixin if getattr(self, 'form_mixin', None) else FundingForm(instance=self.get_object())
        return context

    def post(self, request, *args, **kwargs):
        form = FundingForm(request.POST, instance=self.get_object())
        if form.is_valid():
            form.save()
            return redirect('financial:funding_list')
        self.form_mixin = form
        return super().get(request, *args, **kwargs)


class FundingDeleteView(PageMixin, LoginRequiredMixin, FinancialPermissionRequiredMixin, generic.DeleteView):
    """Only the Financial group and superusers may delete a funding."""

    model = Funding
    template_name = 'components/confirm_delete.html'
    title = _('Delete funding')
    active_level1 = 'financial'
    success_url = reverse_lazy('financial:funding_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = reverse_lazy('financial:funding_list')
        return context


class FundingDetailView(PageMixin, LoginRequiredMixin, generic.DetailView):
    model = Funding
    template_name = 'funding_detail.html'
    context_object_name = 'funding'
    title = _('Funding')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        funding = self.object

        components = Component.objects.filter(funding=funding)
        ctx['components'] = [c for c in components if c.parent_id is None]
        ctx['sub_components'] = [c for c in components if c.parent_id is not None]
        ctx['activities'] = Activity.objects.filter(component__funding=funding)

        requests_qs = DisbursementRequest.objects.filter(funding=funding)
        ctx['disbursement_requests'] = requests_qs
        ctx['disbursements'] = Disbursement.objects.filter(disbursement_request__funding=funding)
        ctx['supporting_documents'] = SupportingDocument.objects.filter(
            Q(disbursement__disbursement_request__funding=funding) | Q(disbursement_request__funding=funding)
        ).distinct()
        return ctx


class FundingExportView(PageMixin, LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        return export_funding(_filtered_fundings(request.GET))
