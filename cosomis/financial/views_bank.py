from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import generic

from cosomis.mixins import PageMixin, SoftDeleteViewMixin
from usermanager.permissions import AccountantPermissionRequiredMixin, FinancialPermissionRequiredMixin

from financial.models.bank import Bank
from financial.forms import BankForm
from financial.exports import export_bank


def _filtered_banks(get):
    qs = Bank.objects.all().order_by('name')
    search = get.get('search', None)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(abbreviation__icontains=search))
    return qs


class BankListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = Bank
    queryset = []
    template_name = 'bank_list.html'
    context_object_name = 'banks'
    title = _('Banks')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_queryset(self):
        page_number = self.request.GET.get('page', None)
        return Paginator(_filtered_banks(self.request.GET), 100).get_page(page_number)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search'] = self.request.GET.get('search', None)
        return ctx


class BankCreateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.CreateView):
    model = Bank
    template_name = 'bank_add.html'
    context_object_name = 'bank'
    title = _('Register a bank')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]
    form_class = BankForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form_mixin if getattr(self, 'form_mixin', None) else BankForm()
        return context

    def post(self, request, *args, **kwargs):
        form = BankForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.save(user=request.user)
            return redirect('financial:bank_list')
        self.form_mixin = form
        return super().get(request, *args, **kwargs)


class BankUpdateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.UpdateView):
    model = Bank
    template_name = 'bank_add.html'
    context_object_name = 'bank'
    title = _('Update bank')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]
    form_class = BankForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form_mixin if getattr(self, 'form_mixin', None) else BankForm(instance=self.get_object())
        return context

    def post(self, request, *args, **kwargs):
        form = BankForm(request.POST, instance=self.get_object())
        if form.is_valid():
            obj = form.save(commit=False)
            obj.save(user=request.user)
            return redirect('financial:bank_list')
        self.form_mixin = form
        return super().get(request, *args, **kwargs)


class BankDeleteView(PageMixin, LoginRequiredMixin, FinancialPermissionRequiredMixin, SoftDeleteViewMixin, generic.DeleteView):
    """Only the Financial group and superusers may delete a bank (soft delete -
    see SoftDeleteViewMixin). bank is on_delete=SET_NULL on Account, not
    CASCADE, so no account gets cascade-deleted along with it."""

    model = Bank
    template_name = 'components/confirm_delete.html'
    title = _('Delete bank')
    active_level1 = 'financial'
    success_url = reverse_lazy('financial:bank_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = reverse_lazy('financial:bank_list')
        return context


class BankDetailView(PageMixin, LoginRequiredMixin, generic.DetailView):
    model = Bank
    template_name = 'bank_detail.html'
    context_object_name = 'bank'
    title = _('Bank')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        bank = self.object
        year = self.request.GET.get('year')
        ctx['selected_year'] = year
        ctx['indicators'] = bank.indicators(year=int(year) if year else None)
        ctx['accounts'] = bank.account_set.all().order_by('name')
        return ctx


class BankExportView(PageMixin, LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        return export_bank(_filtered_banks(request.GET))
