from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import generic
from cosomis.mixins import PageMixin
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q


from financial.models.financial import Disbursement, DisbursementRequest, DisbursementRequestValidation
from usermanager.permissions import (
    AccountantPermissionRequiredMixin,
    FinancialPermissionRequiredMixin,
    )
from financial.forms import DisbursementRequestForm, DisbursementRequestFormCreate, DisbursementRequestValidationForm
from financial.list_filters import apply_entity_filters, build_filter_context
from financial.exports import export_disbursement_request
from financial.aggregations import funding_cascade_meta
# Create your views here.


def _sync_request_status(disbursement_request):
    """Recompute DisbursementRequest.status from the current total of its
    DisbursementRequestValidation rows - called after a round is added, edited or
    deleted, so the status never drifts from the actual validation history.
    REJECTED is an explicit manual decision and is never auto-reverted here."""
    if disbursement_request.status == DisbursementRequest.Status.REJECTED:
        return
    total = disbursement_request.amount_validated
    if not total:
        new_status = DisbursementRequest.Status.PENDING
    elif total >= (disbursement_request.amount_requested or 0):
        new_status = DisbursementRequest.Status.FULLY_VALIDATED
    else:
        new_status = DisbursementRequest.Status.PARTIALLY_VALIDATED
    if new_status != disbursement_request.status:
        disbursement_request.status = new_status
        disbursement_request.save()


def _filtered_disbursement_requests(get):
    qs = DisbursementRequest.objects.all().order_by('-requested_date')
    search = get.get('search', None)
    if search and search != 'All':
        search_upper = search.upper()
        qs = qs.filter(
            Q(project__name__icontains=search_upper) |
            Q(description__icontains=search_upper) |
            Q(motif__icontains=search_upper) |
            Q(amount_requested__icontains=search_upper)
        )
    return apply_entity_filters(
        qs, get,
        project='project_id',
        funding='funding_id',
        category='funding__component__category_id',
        component='funding__component_id',
    )



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
        context['funding_meta'] = funding_cascade_meta()
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
        context['funding_meta'] = funding_cascade_meta()
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
        page_number = self.request.GET.get("page", None)
        return Paginator(_filtered_disbursement_requests(self.request.GET), 100).get_page(page_number)

    def get_context_data(self, **kwargs):
        ctx = super(DisbursementRequestsListView, self).get_context_data(**kwargs)
        ctx['search'] = self.request.GET.get("search", None)
        ctx['type'] = self.request.GET.get("type", "cvd")
        ctx.update(build_filter_context(self.request, projects=True, fundings=True, categories=True, components=True))
        return ctx


class DisbursementRequestExportView(PageMixin, LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        return export_disbursement_request(_filtered_disbursement_requests(request.GET))


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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['validations'] = self.object.validations.all()
        ctx['disbursements'] = Disbursement.objects.filter(disbursement_request=self.object).order_by('-disbursement_date')
        return ctx


class DisbursementRequestValidationCreateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.CreateView):
    """Logs one more validation round on a fund request (§ partial validation
    history). amount_validated is a computed property (sum of these rounds), so
    only `status` and `first_response_date` need updating on the parent request -
    a later 'rest of the requested fund' round never erases earlier history."""

    model = DisbursementRequestValidation
    template_name = 'disbursement_request_validation_add.html'
    context_object_name = 'validation'
    title = _('Register a fund request validation')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]
    form_class = DisbursementRequestValidationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        disbursement_request = get_object_or_404(DisbursementRequest, pk=self.kwargs['disbursement_request_pk'])
        context['disbursement_request'] = disbursement_request
        context['form'] = self.form_mixin if getattr(self, 'form_mixin', None) else DisbursementRequestValidationForm()
        return context

    def post(self, request, *args, **kwargs):
        disbursement_request = get_object_or_404(DisbursementRequest, pk=self.kwargs['disbursement_request_pk'])
        form = DisbursementRequestValidationForm(data=request.POST)
        if form.is_valid():
            validation = form.save(commit=False)
            validation.disbursement_request = disbursement_request
            prospective_total = disbursement_request.amount_validated + validation.amount_validated
            validation.status_after = (
                DisbursementRequest.Status.FULLY_VALIDATED
                if prospective_total >= (disbursement_request.amount_requested or 0)
                else DisbursementRequest.Status.PARTIALLY_VALIDATED
            )
            validation.save()

            if not disbursement_request.first_response_date:
                disbursement_request.first_response_date = validation.validation_date
            disbursement_request.comment_linked_to_reply = validation.comment
            disbursement_request.save()
            _sync_request_status(disbursement_request)
            return redirect('financial:disbursement_request_detail', pk=disbursement_request.pk)
        self.form_mixin = form
        return self.get(request, *args, **kwargs)


class DisbursementRequestValidationUpdateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.UpdateView):
    model = DisbursementRequestValidation
    template_name = 'disbursement_request_validation_add.html'
    context_object_name = 'validation'
    title = _('Update fund request validation')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]
    form_class = DisbursementRequestValidationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        instance = self.get_object()
        context['disbursement_request'] = instance.disbursement_request
        context['form'] = self.form_mixin if getattr(self, 'form_mixin', None) else DisbursementRequestValidationForm(instance=instance)
        return context

    def post(self, request, *args, **kwargs):
        instance = self.get_object()
        form = DisbursementRequestValidationForm(data=request.POST, instance=instance)
        if form.is_valid():
            validation = form.save()
            _sync_request_status(validation.disbursement_request)
            return redirect('financial:disbursement_request_detail', pk=validation.disbursement_request_id)
        self.form_mixin = form
        return self.get(request, *args, **kwargs)


class DisbursementRequestValidationDeleteView(PageMixin, LoginRequiredMixin, FinancialPermissionRequiredMixin, generic.DeleteView):
    """Only the Financial group and superusers may delete a validation round."""

    model = DisbursementRequestValidation
    template_name = 'components/confirm_delete.html'
    title = _('Delete fund request validation')
    active_level1 = 'financial'

    def get_success_url(self):
        return reverse_lazy('financial:disbursement_request_detail', kwargs={'pk': self.object.disbursement_request_id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = reverse_lazy('financial:disbursement_request_detail', kwargs={'pk': self.object.disbursement_request_id})
        return context

    def form_valid(self, form):
        # DeleteView handles POST through FormMixin (form_valid actually performs
        # the deletion) - a delete() override never runs for a POST submission.
        disbursement_request = self.object.disbursement_request
        response = super().form_valid(form)
        _sync_request_status(disbursement_request)
        return response


class DisbursementRequestDeleteView(PageMixin, LoginRequiredMixin, FinancialPermissionRequiredMixin, generic.DeleteView):
    """Only the Financial group and superusers may delete a fund request."""

    model = DisbursementRequest
    template_name = 'components/confirm_delete.html'
    title = _('Delete disbursement request')
    active_level1 = 'financial'
    success_url = reverse_lazy('financial:disbursement_requests_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = reverse_lazy('financial:disbursement_requests_list')
        return context
