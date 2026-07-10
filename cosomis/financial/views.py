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
    )
from financial.forms import AdministrativeLevelAllocationForm
from financial import function_allocation
# Create your views here.


class FinancialTemplateView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = 'financials.html'
    active_level1 = 'financial'
    title = _('Financials')
    
    def get_context_data(self, **kwargs):
        ctx = super(FinancialTemplateView, self).get_context_data(**kwargs)
        ctx['hide_content_header'] = True
        return ctx



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
        _type = self.request.GET.get("type", "Canton").title()
        if search:
            if search == "All":
                ads = AdministrativeLevelAllocation.objects.filter(
                    Q(
                        Q(administrative_level__type=_type) if _type != "Cvd" else Q(cvd__isnull=False)
                    )
                )
                return Paginator(ads, ads.count()).get_page(page_number)
            search = search.upper()
            return Paginator(AdministrativeLevelAllocation.objects.filter(
                Q(
                    Q(administrative_level__name__icontains=search) if _type != "Cvd" else Q(cvd__name__icontains=search)
                ) | 
                Q(project__name__icontains=search) | 
                Q(allocation_date__icontains=search) | 
                Q(description__icontains=search) | 
                Q(amount__icontains=search),
                Q(
                    Q(administrative_level__type=_type) if _type != "Cvd" else Q(cvd__isnull=False)
                )
            ), 100).get_page(page_number)
        else:
            return Paginator(AdministrativeLevelAllocation.objects.filter(
                Q(
                    Q(administrative_level__type=_type) if _type != "Cvd" else Q(cvd__isnull=False)
                )
            ), 100).get_page(page_number)

        # return super().get_queryset()
    def get_context_data(self, **kwargs):
        ctx = super(AdministrativeLevelAllocationsListView, self).get_context_data(**kwargs)
        ctx['search'] = self.request.GET.get("search", None)
        ctx['type'] = self.request.GET.get("type", "Canton")
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
    