from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import generic
from cosomis.mixins import PageMixin, SoftDeleteViewMixin
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q


from financial.models.financial import BankTransfer, Disbursement
from financial.models.supporting_document import SupportingDocument
from usermanager.permissions import (
    AccountantPermissionRequiredMixin,
    FinancialPermissionRequiredMixin,
    )
from financial.forms import DisbursementForm
from financial.list_filters import apply_entity_filters, build_filter_context
from financial.exports import export_disbursement
# Create your views here.


def _filtered_disbursements(get):
    qs = Disbursement.objects.all().order_by('-disbursement_date')
    search = get.get('search', None)
    if search and search != 'All':
        search_upper = search.upper()
        qs = qs.filter(
            Q(disbursement_request__project__name__icontains=search_upper) |
            Q(disbursement_date__icontains=search_upper) |
            Q(description__icontains=search_upper) |
            Q(amount_disbursed__icontains=search_upper)
        )
    return apply_entity_filters(
        qs, get,
        project='disbursement_request__project_id',
        funding='disbursement_request__funding_id',
        category='disbursement_request__funding__component__category_id',
        component='disbursement_request__funding__component_id',
        disbursement_request='disbursement_request_id',
    )




class DisbursementCreateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.CreateView):
    model = Disbursement
    template_name = 'disbursement_add.html'
    context_object_name = 'disbursement'
    title = _('Register a disbursement')
    active_level1 = 'financial'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    form_class = DisbursementForm # specify the class form to be displayed
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.form_mixin:
            context['form'] = self.form_mixin
        else:
            context['form'] = DisbursementForm()
        return context
    
    def post(self, request, *args, **kwargs):
        form = DisbursementForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.save(user=request.user)
            return redirect('financial:financials')
        self.form_mixin = form
        return super(DisbursementCreateView, self).get(request, *args, **kwargs)


class DisbursementUpdateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.UpdateView):
    model = Disbursement
    template_name = 'disbursement_add.html'
    context_object_name = 'disbursement'
    title = _('Update disbursement')
    active_level1 = 'financial'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    form_class = DisbursementForm # specify the class form to be displayed
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.form_mixin:
            context['form'] = self.form_mixin
        else:
            context['form'] = DisbursementForm(instance=self.get_object())
        return context
    
    
    def post(self, request, *args, **kwargs):
        form = DisbursementForm(request.POST, instance=self.get_object())
        if form.is_valid():
            obj = form.save(commit=False)
            obj.save(user=request.user)
            return redirect('financial:financials')
        self.form_mixin = form
        return super(DisbursementUpdateView, self).get(request, *args, **kwargs)
    


class DisbursementsListView(PageMixin, LoginRequiredMixin, generic.ListView):
    """Display bank Disbursements list"""

    model = Disbursement
    queryset = []
    template_name = 'disbursement_list.html'
    context_object_name = 'disbursements'
    title = _('Disbursements')
    active_level1 = 'financial'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get_queryset(self):
        page_number = self.request.GET.get("page", None)
        return Paginator(_filtered_disbursements(self.request.GET), 100).get_page(page_number)

    def get_context_data(self, **kwargs):
        ctx = super(DisbursementsListView, self).get_context_data(**kwargs)
        ctx['search'] = self.request.GET.get("search", None)
        ctx['type'] = self.request.GET.get("type", "cvd")
        ctx.update(build_filter_context(
            self.request, projects=True, fundings=True, categories=True,
            components=True, disbursement_requests=True,
        ))
        return ctx


class DisbursementExportView(PageMixin, LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        return export_disbursement(_filtered_disbursements(request.GET))


class DisbursementDeleteView(PageMixin, LoginRequiredMixin, FinancialPermissionRequiredMixin, SoftDeleteViewMixin, generic.DeleteView):
    """Only the Financial group and superusers may delete a disbursement."""

    model = Disbursement
    template_name = 'components/confirm_delete.html'
    title = _('Delete disbursement')
    active_level1 = 'financial'
    success_url = reverse_lazy('financial:disbursements_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = reverse_lazy('financial:disbursements_list')
        return context


class DisbursementDetailView(PageMixin, LoginRequiredMixin, generic.DetailView):
    """Class to present the detail page of one Disbursement"""

    model = Disbursement
    template_name = 'disbursement_detail.html'
    context_object_name = 'disbursement'
    title = _('Disbursement')
    active_level1 = 'financial'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['supporting_documents'] = SupportingDocument.objects.filter(disbursement=self.object)
        ctx['bank_transfers'] = BankTransfer.objects.filter(disbursement=self.object).order_by('-transfer_date')
        return ctx
