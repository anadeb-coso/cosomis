from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import generic
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q

from cosomis.mixins import PageMixin, SoftDeleteViewMixin
from usermanager.permissions import AccountantPermissionRequiredMixin, FinancialPermissionRequiredMixin
from financial.models.account import Account
from financial.models.financial import BankTransfer
from financial.forms import AccountForm
from financial.exports import export_account
from financial.list_filters import build_filter_context


def _filtered_accounts(get):
    qs = Account.objects.all().order_by('name')
    search = get.get('search', None)
    if search:
        qs = qs.filter(
            Q(name__icontains=search) |
            Q(account_number__icontains=search) |
            Q(contact__icontains=search)
        )
    account_type = get.get('account_type')
    if account_type:
        qs = qs.filter(account_type=account_type)
    account_category = get.get('account_category')
    if account_category:
        qs = qs.filter(account_category=account_category)
    parent_id = get.get('parent')
    if parent_id:
        qs = qs.filter(parent_id=parent_id)
    return qs


class AccountListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = Account
    queryset = []
    template_name = 'account_list.html'
    context_object_name = 'accounts'
    title = _('Accounts')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_queryset(self):
        page_number = self.request.GET.get('page', None)
        return Paginator(_filtered_accounts(self.request.GET), 100).get_page(page_number)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search'] = self.request.GET.get('search', None)
        ctx.update(build_filter_context(self.request, account_attrs=True))
        return ctx


class AccountCreateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.CreateView):
    model = Account
    template_name = 'account_add.html'
    context_object_name = 'account'
    title = _('Register an account')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]
    form_class = AccountForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form_mixin if getattr(self, 'form_mixin', None) else AccountForm()
        return context

    def post(self, request, *args, **kwargs):
        form = AccountForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.save(user=request.user)
            return redirect('financial:account_list')
        self.form_mixin = form
        return super().get(request, *args, **kwargs)


class AccountUpdateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.UpdateView):
    model = Account
    template_name = 'account_add.html'
    context_object_name = 'account'
    title = _('Update account')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]
    form_class = AccountForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form_mixin if getattr(self, 'form_mixin', None) else AccountForm(instance=self.get_object())
        return context

    def post(self, request, *args, **kwargs):
        form = AccountForm(request.POST, instance=self.get_object())
        if form.is_valid():
            obj = form.save(commit=False)
            obj.save(user=request.user)
            return redirect('financial:account_list')
        self.form_mixin = form
        return super().get(request, *args, **kwargs)


class AccountDeleteView(PageMixin, LoginRequiredMixin, FinancialPermissionRequiredMixin, SoftDeleteViewMixin, generic.DeleteView):
    """Only the Financial group and superusers may delete an account (soft delete
    - see SoftDeleteViewMixin)."""

    model = Account
    template_name = 'components/confirm_delete.html'
    title = _('Delete account')
    active_level1 = 'financial'
    success_url = reverse_lazy('financial:account_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = reverse_lazy('financial:account_list')
        return context


class AccountDetailView(PageMixin, LoginRequiredMixin, generic.DetailView):
    model = Account
    template_name = 'account_detail.html'
    context_object_name = 'account'
    title = _('Account')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        account = self.object
        year = self.request.GET.get('year')
        ctx['selected_year'] = year
        ctx['balance'] = account.balance_breakdown(year=int(year) if year else None)
        ctx['allocation_summary'] = account.allocation_summary(year=int(year) if year else None)
        ctx['sub_accounts'] = account.sub_accounts.all()
        ctx['sent_transfers'] = BankTransfer.objects.filter(sender=account).order_by('-transfer_date')
        ctx['received_transfers'] = BankTransfer.objects.filter(recipient=account).order_by('-transfer_date')
        return ctx


class AccountExportView(PageMixin, LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        return export_account(_filtered_accounts(request.GET))


class AccountBalancesListView(PageMixin, LoginRequiredMixin, generic.ListView):
    """Display the balance (§2.14 'Soldes des comptes') of each Account, filterable by account type and year."""

    model = Account
    queryset = []
    template_name = 'account_balances_list.html'
    context_object_name = 'accounts'
    title = _('Account balances')
    active_level1 = 'financial'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get_queryset(self):
        search = self.request.GET.get("search", None)
        page_number = self.request.GET.get("page", None)
        account_type = self.request.GET.get("type", None)

        qs = Account.objects.all()
        if account_type:
            qs = qs.filter(account_type=account_type.upper())
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(account_number__icontains=search)
            )
        return Paginator(qs.order_by('name'), 100).get_page(page_number)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search'] = self.request.GET.get("search", None)
        ctx['type'] = self.request.GET.get("type", None)
        year = self.request.GET.get("year", None)
        ctx['year'] = year

        account_year = int(year) if year else None
        ctx['accounts_with_balance'] = [
            {'account': account, **account.balance_breakdown(year=account_year)}
            for account in ctx['accounts']
        ]
        return ctx
