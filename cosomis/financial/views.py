from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.http import Http404
from django.urls import reverse_lazy
from django.contrib import messages
from django.views import generic
from cosomis.mixins import PageMixin
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q


from financial.models.allocation import AdministrativeLevelAllocation
from usermanager.permissions import (
    AccountantPermissionRequiredMixin,
    FinancialPermissionRequiredMixin,
    )
from financial.forms import AdministrativeLevelAllocationForm
from financial import function_allocation
from financial.list_filters import build_filter_context
from financial.exports import export_allocation
from financial.aggregations import component_cascade_meta
# Create your views here.


def _filtered_allocations(get):
    _type = get.get("type", "Canton").title()
    qs = AdministrativeLevelAllocation.objects.filter(
        Q(administrative_level__type=_type) if _type != "Cvd" else Q(cvd__isnull=False)
    )
    search = get.get("search", None)
    if search and search != "All":
        search_upper = search.upper()
        qs = qs.filter(
            Q(administrative_level__name__icontains=search_upper) if _type != "Cvd" else Q(cvd__name__icontains=search_upper)
        ) | qs.filter(
            Q(project__name__icontains=search_upper) |
            Q(allocation_date__icontains=search_upper) |
            Q(description__icontains=search_upper) |
            Q(amount__icontains=search_upper)
        )

    project_id = get.get('project')
    if project_id:
        qs = qs.filter(project_id=project_id)
    component_id = get.get('component')
    if component_id:
        qs = qs.filter(component_id=component_id)
    year = get.get('year')
    if year:
        qs = qs.filter(allocation_date__year=year)
    return qs


class FinancialTemplateView(LoginRequiredMixin, generic.RedirectView):
    """`/financial/` is the historical entry point of the app (linked from
    redirect()-after-save calls across the financial views) - each section is
    now its own real GET page, with the dashboard as the section's home page."""
    pattern_name = 'financial:financial_dashboard'



class AdministrativeLevelAllocationCreateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.CreateView):
    model = AdministrativeLevelAllocation
    template_name = 'allocation_add.html'
    context_object_name = 'allocation'
    title = _('Create Administrative level Allocation')
    active_level1 = 'financial'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    form_class = AdministrativeLevelAllocationForm # specify the class form to be displayed
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.form_mixin:
            context['form'] = self.form_mixin
        else:
            context['form'] = AdministrativeLevelAllocationForm(self.request.GET.get("type"))
        context['component_meta'] = component_cascade_meta()
        return context
    
    def post(self, request, *args, **kwargs):
        form = AdministrativeLevelAllocationForm(self.request.GET.get("type"), request.POST)
        if form.is_valid():
            form.save()
            return redirect('financial:financials')
        self.form_mixin = form
        return super(AdministrativeLevelAllocationCreateView, self).get(request, *args, **kwargs)


class AdministrativeLevelAllocationUpdateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.UpdateView):
    model = AdministrativeLevelAllocation
    template_name = 'allocation_add.html'
    context_object_name = 'allocation'
    title = _('Update Administrative level Allocation')
    active_level1 = 'financial'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    form_class = AdministrativeLevelAllocationForm # specify the class form to be displayed
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.form_mixin:
            context['form'] = self.form_mixin
        else:
            context['form'] = AdministrativeLevelAllocationForm(self.request.GET.get("type"), instance=self.get_object())
        context['component_meta'] = component_cascade_meta()
        return context
    
    
    def post(self, request, *args, **kwargs):
        form = AdministrativeLevelAllocationForm(self.request.GET.get("type"), request.POST, instance=self.get_object())
        if form.is_valid():
            form.save()
            return redirect('financial:financials')
        self.form_mixin = form
        return super(AdministrativeLevelAllocationForm, self).get(request, *args, **kwargs)
    


class AdministrativeLevelAllocationsListView(PageMixin, LoginRequiredMixin, generic.ListView):
    """Display allocations list"""

    model = AdministrativeLevelAllocation
    queryset = []
    template_name = 'allocation_list.html'
    context_object_name = 'allocations'
    title = _('Allocations')
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
        qs = _filtered_allocations(self.request.GET)
        if search == "All":
            return Paginator(qs, qs.count() or 1).get_page(page_number)
        return Paginator(qs, 100).get_page(page_number)

    def get_context_data(self, **kwargs):
        ctx = super(AdministrativeLevelAllocationsListView, self).get_context_data(**kwargs)
        ctx['search'] = self.request.GET.get("search", None)
        ctx['type'] = self.request.GET.get("type", "Canton")
        ctx.update(build_filter_context(self.request, projects=True, components=True, year=True))
        ctx['preserve_type'] = ctx['type']
        is_administrative_level = False if str(ctx['type']).lower() == 'cvd' else True
        ctx['sum_allocation_mount'] = function_allocation.sum_allocation_amount(is_administrative_level)
        ctx['sum_allocation_amount_in_dollars'] = function_allocation.sum_allocation_amount_in_dollars(is_administrative_level)

        ctx['sum_allocation_amount_by_component_1_1'] = function_allocation.sum_allocation_amount_by_component(2, is_administrative_level)
        ctx['sum_allocation_amount_by_component_1_2'] = function_allocation.sum_allocation_amount_by_component(3, is_administrative_level)
        ctx['sum_allocation_amount_by_component_1_3'] = function_allocation.sum_allocation_amount_by_component(6, is_administrative_level)
        
        ctx['sum_allocation_amount_in_dollars_by_component_1_1'] = function_allocation.sum_allocation_amount_in_dollars_by_component(2, is_administrative_level)
        ctx['sum_allocation_amount_in_dollars_by_component_1_2'] = function_allocation.sum_allocation_amount_in_dollars_by_component(3, is_administrative_level)
        ctx['sum_allocation_amount_in_dollars_by_component_1_3'] = function_allocation.sum_allocation_amount_in_dollars_by_component(6, is_administrative_level)
        return ctx


class AdministrativeLevelAllocationExportView(PageMixin, LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        return export_allocation(_filtered_allocations(request.GET))


class AdministrativeLevelAllocationDeleteView(PageMixin, LoginRequiredMixin, FinancialPermissionRequiredMixin, generic.DeleteView):
    """Only the Financial group and superusers may delete an allocation."""

    model = AdministrativeLevelAllocation
    template_name = 'components/confirm_delete.html'
    title = _('Delete allocation')
    active_level1 = 'financial'
    success_url = reverse_lazy('financial:allocations_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = reverse_lazy('financial:allocations_list')
        return context


class AdministrativeLevelAllocationDetailView(PageMixin, LoginRequiredMixin, generic.DetailView):
    """Class to present the detail page of one allocations"""

    model = AdministrativeLevelAllocation
    template_name = 'alocation_detail.html'
    context_object_name = 'allocation'
    title = _('Allocation')
    active_level1 = 'financial'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]
    