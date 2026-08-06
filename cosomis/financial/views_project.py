from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views import generic

from cosomis.mixins import PageMixin
from usermanager.permissions import SuperAdminPermissionRequiredMixin

from subprojects.models import Project, CategoryIDA, Component
from financial.models.funding import Funding
from financial.models.planning import AnnualWorkPlan, Activity
from financial.models.financial import DisbursementRequest, Disbursement
from financial.models.supporting_document import SupportingDocument
from financial.forms import ProjectForm
from financial.aggregations import requests_indicators, activity_financial_summary, component_financial_breakdown
from financial.exports import export_project_ida, export_project_ida_detail


class ProjectIDAListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = Project
    queryset = []
    template_name = 'project_ida_list.html'
    context_object_name = 'projects'
    title = _('IDA Projects')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_queryset(self):
        search = self.request.GET.get('search', None)
        page_number = self.request.GET.get('page', None)
        qs = Project.objects.all().order_by('name')
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        return Paginator(qs, 100).get_page(page_number)


class ProjectIDACreateView(PageMixin, LoginRequiredMixin, SuperAdminPermissionRequiredMixin, generic.CreateView):
    """Only superusers may register an IDA project."""

    model = Project
    template_name = 'project_ida_add.html'
    context_object_name = 'project'
    title = _('Register an IDA Project')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]
    form_class = ProjectForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form_mixin if getattr(self, 'form_mixin', None) else ProjectForm()
        return context

    def post(self, request, *args, **kwargs):
        form = ProjectForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.save(user=request.user)
            return redirect('financial:project_ida_list')
        self.form_mixin = form
        return super().get(request, *args, **kwargs)


class ProjectIDAUpdateView(PageMixin, LoginRequiredMixin, SuperAdminPermissionRequiredMixin, generic.UpdateView):
    """Only superusers may edit an IDA project."""

    model = Project
    template_name = 'project_ida_add.html'
    context_object_name = 'project'
    title = _('Update IDA Project')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]
    form_class = ProjectForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form_mixin if getattr(self, 'form_mixin', None) else ProjectForm(instance=self.get_object())
        return context

    def post(self, request, *args, **kwargs):
        form = ProjectForm(request.POST, instance=self.get_object())
        if form.is_valid():
            obj = form.save(commit=False)
            obj.save(user=request.user)
            return redirect('financial:project_ida_list')
        self.form_mixin = form
        return super().get(request, *args, **kwargs)


class ProjectIDADetailView(PageMixin, LoginRequiredMixin, generic.DetailView):
    model = Project
    template_name = 'project_ida_detail.html'
    context_object_name = 'project'
    title = _('IDA Project')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        project = self.object

        fundings = list(Funding.objects.filter(project=project))
        for funding in fundings:
            funding.indicators = requests_indicators(DisbursementRequest.objects.filter(funding=funding))
        ctx['fundings'] = fundings

        categories = list(CategoryIDA.objects.filter(project=project))
        for category in categories:
            component_ids = list(Component.objects.filter(category=category).values_list('pk', flat=True))
            category.summary = activity_financial_summary(component_ids)
        ctx['categories'] = categories

        components = list(Component.objects.filter(project=project))
        for component in components:
            component.planning = component_financial_breakdown(component)
        ctx['components'] = [c for c in components if c.parent_id is None]
        ctx['sub_components'] = [c for c in components if c.parent_id is not None]

        annual_work_plans = list(AnnualWorkPlan.objects.filter(project=project))
        for plan in annual_work_plans:
            plan.activities = Activity.objects.filter(annual_work_plan=plan)
        ctx['annual_work_plans'] = annual_work_plans

        requests_qs = DisbursementRequest.objects.filter(project=project)
        ctx['disbursement_requests'] = requests_qs
        ctx['disbursements'] = Disbursement.objects.filter(disbursement_request__project=project)
        ctx['supporting_documents'] = SupportingDocument.objects.filter(
            Q(disbursement__disbursement_request__project=project) | Q(disbursement_request__project=project)
        ).distinct()
        return ctx


class ProjectIDAExportView(PageMixin, LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        return export_project_ida(Project.objects.all())


class ProjectIDAExportDetailView(PageMixin, LoginRequiredMixin, generic.DetailView):
    model = Project

    def get(self, request, *args, **kwargs):
        project = self.get_object()
        return export_project_ida_detail(project)
