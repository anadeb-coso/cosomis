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


from financial.models.financial import BankTransfer
from usermanager.permissions import (
    AccountantPermissionRequiredMixin,
    )
from financial.forms import BankTransferForm
# Create your views here.




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
            context['form'] = BankTransferForm(self.request.GET.get("type"))
        return context
    
    def post(self, request, *args, **kwargs):
        form = BankTransferForm(self.request.GET.get("type"), request.POST)
        if form.is_valid():
            form.save()
            return redirect('financial:financials')
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
            context['form'] = BankTransferForm(self.request.GET.get("type"), instance=self.get_object())
        return context
    
    
    def post(self, request, *args, **kwargs):
        form = BankTransferForm(self.request.GET.get("type"), request.POST, instance=self.get_object())
        if form.is_valid():
            form.save()
            return redirect('financial:financials')
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
        search = self.request.GET.get("search", None)
        page_number = self.request.GET.get("page", None)
        _type = self.request.GET.get("type", "cvd").title()
        if search:
            if search == "All":
                ads = BankTransfer.objects.filter(
                    Q(
                        Q(administrative_level__type=_type) if _type != "Cvd" else Q(cvd__isnull=False)
                    )
                )
                return Paginator(ads, ads.count()).get_page(page_number)
            search = search.upper()
            return Paginator(BankTransfer.objects.filter(
                Q(
                    Q(administrative_level__name__icontains=search) if _type != "Cvd" else Q(cvd__name__icontains=search)
                ) | 
                Q(project__name__icontains=search) | 
                Q(transfer_date__icontains=search) | 
                Q(description__icontains=search) | 
                Q(motif__icontains=search) | 
                Q(amount_transferred__icontains=search),
                Q(
                    Q(administrative_level__type=_type) if _type != "Cvd" else Q(cvd__isnull=False)
                )
            ), 100).get_page(page_number)
        else:
            return Paginator(BankTransfer.objects.filter(
                Q(
                    Q(administrative_level__type=_type) if _type != "Cvd" else Q(cvd__isnull=False)
                )
            ), 100).get_page(page_number)

        # return super().get_queryset()
    def get_context_data(self, **kwargs):
        ctx = super(BankTransfersListView, self).get_context_data(**kwargs)
        ctx['search'] = self.request.GET.get("search", None)
        ctx['type'] = self.request.GET.get("type", "cvd")
        return ctx
    

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
    