from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import generic
from cosomis.mixins import PageMixin
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q


from financial.models.financial import DisbursementRequest
from usermanager.permissions import (
    AccountantPermissionRequiredMixin,
    )
from financial.forms import DisbursementRequestForm, DisbursementRequestFormCreate
# Create your views here.



class DisbursementRequestCreateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.CreateView):
    model = DisbursementRequest
    template_name = 'disbursement_request_add.html'
    context_object_name = 'disbursement_request'
    title = _('Register a disbursement request')
    active_level1 = 'financial'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    form_class = DisbursementRequestFormCreate # specify the class form to be displayed
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.form_mixin:
            context['form'] = self.form_mixin
        else:
            context['form'] = DisbursementRequestFormCreate()
        return context
    
    def post(self, request, *args, **kwargs):
        form = DisbursementRequestFormCreate(request.POST)
        if form.is_valid():
            form.save()
            return redirect('financial:financials')
        self.form_mixin = form
        return super(DisbursementRequestCreateView, self).get(request, *args, **kwargs)


class DisbursementRequestUpdateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.UpdateView):
    model = DisbursementRequest
    template_name = 'disbursement_request_add.html'
    context_object_name = 'disbursement_request'
    title = _('Update disbursement request')
    active_level1 = 'financial'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    form_class = DisbursementRequestForm # specify the class form to be displayed
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.form_mixin:
            context['form'] = self.form_mixin
        else:
            context['form'] = DisbursementRequestForm(instance=self.get_object())
        return context
    
    
    def post(self, request, *args, **kwargs):
        form = DisbursementRequestForm(request.POST, instance=self.get_object())
        if form.is_valid():
            form.save()
            return redirect('financial:financials')
        self.form_mixin = form
        return super(DisbursementRequestUpdateView, self).get(request, *args, **kwargs)
    


class DisbursementRequestsListView(PageMixin, LoginRequiredMixin, generic.ListView):
    """Display bank DisbursementRequests list"""

    model = DisbursementRequest
    queryset = []
    template_name = 'disbursement_request_list.html'
    context_object_name = 'disbursement_requests'
    title = _('Disbursements Request')
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
        if search:
            if search == "All":
                ads = DisbursementRequest.objects.filter()
                return Paginator(ads, ads.count()).get_page(page_number)
            search = search.upper()
            return Paginator(DisbursementRequest.objects.filter(
                Q(project__name__icontains=search) | 
                Q(transfer_date__icontains=search) | 
                Q(description__icontains=search) | 
                Q(motif__icontains=search) | 
                Q(amount_transferred__icontains=search)
            ), 100).get_page(page_number)
        else:
            return Paginator(DisbursementRequest.objects.filter(), 100).get_page(page_number)

        # return super().get_queryset()
    def get_context_data(self, **kwargs):
        ctx = super(DisbursementRequestsListView, self).get_context_data(**kwargs)
        ctx['search'] = self.request.GET.get("search", None)
        ctx['type'] = self.request.GET.get("type", "cvd")
        return ctx
    

class DisbursementRequestDetailView(PageMixin, LoginRequiredMixin, generic.DetailView):
    """Class to present the detail page of one DisbursementRequest"""

    model = DisbursementRequest
    template_name = 'disbursement_request_detail.html'
    context_object_name = 'disbursement_request'
    title = _('Disbursement Request')
    active_level1 = 'financial'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]
    