from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import generic
from cosomis.mixins import PageMixin, SoftDeleteViewMixin
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q


from financial.models.financial import BankTransfer
from usermanager.permissions import (
    AccountantPermissionRequiredMixin,
    FinancialPermissionRequiredMixin,
    )
from financial.forms import BankTransferForm
from financial.list_filters import apply_entity_filters, build_filter_context
from financial.exports import export_bank_transfer
from financial.aggregations import bank_transfer_cascade_meta, allocation_cascade_meta
# Create your views here.


def _filtered_bank_transfers(get):
    qs = BankTransfer.objects.all().order_by('-transfer_date')
    search = get.get('search', None)
    if search and search != 'All':
        search_upper = search.upper()
        qs = qs.filter(
            Q(sender__name__icontains=search_upper) |
            Q(recipient__name__icontains=search_upper) |
            Q(project__name__icontains=search_upper) |
            Q(transfer_date__icontains=search_upper) |
            Q(description__icontains=search_upper) |
            Q(motif__icontains=search_upper) |
            Q(amount_transferred__icontains=search_upper)
        )
    qs = apply_entity_filters(qs, get, project='project_id')
    sender_id = get.get('sender')
    if sender_id:
        qs = qs.filter(sender_id=sender_id)
    recipient_id = get.get('recipient')
    if recipient_id:
        qs = qs.filter(recipient_id=recipient_id)
    level = get.get('level')
    if level:
        qs = qs.filter(level=level)
    status = get.get('status')
    if status:
        qs = qs.filter(status=status)
    direction = get.get('direction')
    if direction:
        qs = qs.filter(direction=direction)
    payment_method = get.get('payment_method')
    if payment_method:
        qs = qs.filter(payment_method=payment_method)
    year = get.get('year')
    if year:
        qs = qs.filter(transfer_date__year=year)
    return qs


class BankTransferCreateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.CreateView):
    model = BankTransfer
    template_name = 'bank_transfer_add.html'
    context_object_name = 'bank_transfer'
    title = _('Register a bank transfer')
    active_level1 = 'financial'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    form_class = BankTransferForm # specify the class form to be displayed
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.form_mixin:
            context['form'] = self.form_mixin
        else:
            context['form'] = BankTransferForm()
        context['disbursement_meta'], context['funding_meta'] = bank_transfer_cascade_meta()
        context['allocation_meta'] = allocation_cascade_meta()
        return context

    def post(self, request, *args, **kwargs):
        form = BankTransferForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.save(user=request.user)
            return redirect('financial:bank_transfers_list')
        self.form_mixin = form
        return super(BankTransferCreateView, self).get(request, *args, **kwargs)


class BankTransferUpdateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.UpdateView):
    model = BankTransfer
    template_name = 'bank_transfer_add.html'
    context_object_name = 'bank_transfer'
    title = _('Update Transfer')
    active_level1 = 'financial'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    form_class = BankTransferForm # specify the class form to be displayed
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.form_mixin:
            context['form'] = self.form_mixin
        else:
            context['form'] = BankTransferForm(instance=self.get_object())
        context['disbursement_meta'], context['funding_meta'] = bank_transfer_cascade_meta()
        context['allocation_meta'] = allocation_cascade_meta()
        return context


    def post(self, request, *args, **kwargs):
        form = BankTransferForm(request.POST, instance=self.get_object())
        if form.is_valid():
            obj = form.save(commit=False)
            obj.save(user=request.user)
            return redirect('financial:bank_transfers_list')
        self.form_mixin = form
        return super(BankTransferUpdateView, self).get(request, *args, **kwargs)



class BankTransfersListView(PageMixin, LoginRequiredMixin, generic.ListView):
    """Display bank transfers list"""

    model = BankTransfer
    queryset = []
    template_name = 'bank_transfer_list.html'
    context_object_name = 'bank_transfers'
    title = _('Transfers')
    active_level1 = 'financial'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get_queryset(self):
        page_number = self.request.GET.get("page", None)
        return Paginator(_filtered_bank_transfers(self.request.GET), 100).get_page(page_number)

    def get_context_data(self, **kwargs):
        ctx = super(BankTransfersListView, self).get_context_data(**kwargs)
        ctx['search'] = self.request.GET.get("search", None)
        ctx.update(build_filter_context(self.request, projects=True, bank_transfers=True, year=True))
        return ctx


class BankTransferExportView(PageMixin, LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        return export_bank_transfer(_filtered_bank_transfers(request.GET))


class BankTransferDetailView(PageMixin, LoginRequiredMixin, generic.DetailView):
    """Class to present the detail page of one Bank Transfer"""

    model = BankTransfer
    template_name = 'bank_transfer_detail.html'
    context_object_name = 'bank_transfer'
    title = _('Bank Transfer')
    active_level1 = 'financial'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]


class BankTransferDeleteView(PageMixin, LoginRequiredMixin, FinancialPermissionRequiredMixin, SoftDeleteViewMixin, generic.DeleteView):
    """Only the Financial group and superusers may delete a bank transfer."""

    model = BankTransfer
    template_name = 'components/confirm_delete.html'
    title = _('Delete bank transfer')
    active_level1 = 'financial'
    success_url = reverse_lazy('financial:bank_transfers_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = reverse_lazy('financial:bank_transfers_list')
        return context


class BankTransferStatusUpdateView(LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.View):
    """Quick inline status change from the transfers list, without opening the full edit form."""

    def post(self, request, *args, **kwargs):
        bank_transfer = get_object_or_404(BankTransfer, pk=kwargs['pk'])
        status = request.POST.get('status')
        if status in BankTransfer.Status.values:
            bank_transfer.status = status
            bank_transfer.save(user=request.user)
        referer = request.META.get('HTTP_REFERER')
        return redirect(referer or 'financial:bank_transfers_list')


class BankTransferBulkStatusUpdateView(LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.View):
    """Change the status of every checked transfer from the transfers list in one
    go - the confirmation itself happens client-side (see bank_transfer_list.html)
    before this endpoint is ever hit."""

    def post(self, request, *args, **kwargs):
        status = request.POST.get('status')
        ids = request.POST.getlist('selected_transfers')
        if status in BankTransfer.Status.values and ids:
            # Saved one by one (rather than a single queryset .update()) so each
            # transfer's BaseModel.users_involved history records the change -
            # .update() writes SQL directly and never calls save().
            for bank_transfer in BankTransfer.objects.filter(pk__in=ids):
                bank_transfer.status = status
                bank_transfer.save(user=request.user)
        referer = request.META.get('HTTP_REFERER')
        return redirect(referer or 'financial:bank_transfers_list')
