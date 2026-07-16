from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import generic

from cosomis.mixins import PageMixin
from usermanager.permissions import AccountantPermissionRequiredMixin, FinancialPermissionRequiredMixin

from financial.models.planning import AnnualWorkPlan, Activity
from financial.forms import AnnualWorkPlanForm, ActivityForm
from financial.exports import export_annual_work_plan
from financial.list_filters import apply_entity_filters, build_filter_context


def _filtered_annual_work_plans(get):
    qs = AnnualWorkPlan.objects.all().order_by('-period', 'name')
    search = get.get('search', None)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(project__name__icontains=search))
    return apply_entity_filters(
        qs, get,
        project='project_id',
        funding='activity__component__funding_id',
        category='activity__component__category_id',
        component='activity__component_id',
    )


class AnnualWorkPlanListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = AnnualWorkPlan
    queryset = []
    template_name = 'annual_work_plan_list.html'
    context_object_name = 'annual_work_plans'
    title = _('Annual work plans')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_queryset(self):
        page_number = self.request.GET.get('page', None)
        return Paginator(_filtered_annual_work_plans(self.request.GET), 100).get_page(page_number)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(build_filter_context(self.request, projects=True, fundings=True, categories=True, components=True))
        return ctx


class AnnualWorkPlanCreateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.CreateView):
    model = AnnualWorkPlan
    template_name = 'annual_work_plan_add.html'
    context_object_name = 'annual_work_plan'
    title = _('Register an annual work plan')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]
    form_class = AnnualWorkPlanForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form_mixin if getattr(self, 'form_mixin', None) else AnnualWorkPlanForm()
        return context

    def post(self, request, *args, **kwargs):
        form = AnnualWorkPlanForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('financial:annual_work_plan_list')
        self.form_mixin = form
        return super().get(request, *args, **kwargs)


class AnnualWorkPlanUpdateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.UpdateView):
    model = AnnualWorkPlan
    template_name = 'annual_work_plan_add.html'
    context_object_name = 'annual_work_plan'
    title = _('Update annual work plan')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]
    form_class = AnnualWorkPlanForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form_mixin if getattr(self, 'form_mixin', None) else AnnualWorkPlanForm(instance=self.get_object())
        return context

    def post(self, request, *args, **kwargs):
        form = AnnualWorkPlanForm(request.POST, instance=self.get_object())
        if form.is_valid():
            form.save()
            return redirect('financial:annual_work_plan_detail', pk=self.get_object().pk)
        self.form_mixin = form
        return super().get(request, *args, **kwargs)


class AnnualWorkPlanDeleteView(PageMixin, LoginRequiredMixin, FinancialPermissionRequiredMixin, generic.DeleteView):
    """Only the Financial group and superusers may delete an annual work plan."""

    model = AnnualWorkPlan
    template_name = 'components/confirm_delete.html'
    title = _('Delete annual work plan')
    active_level1 = 'financial'
    success_url = reverse_lazy('financial:annual_work_plan_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = reverse_lazy('financial:annual_work_plan_list')
        return context


class AnnualWorkPlanDetailView(PageMixin, LoginRequiredMixin, generic.DetailView):
    model = AnnualWorkPlan
    template_name = 'annual_work_plan_detail.html'
    context_object_name = 'annual_work_plan'
    title = _('Annual work plan')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['activities'] = self.object.activity_set.all()
        return ctx


class AnnualWorkPlanExportView(PageMixin, LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        return export_annual_work_plan(_filtered_annual_work_plans(request.GET))


# -- Activity CRUD, always scoped to a PTBA - not in the nav menu --------------

class ActivityCreateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.CreateView):
    model = Activity
    template_name = 'activity_add.html'
    context_object_name = 'activity'
    active_level1 = 'financial'
    form_class = ActivityForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plan = get_object_or_404(AnnualWorkPlan, pk=self.kwargs['annual_work_plan_pk'])
        context['annual_work_plan'] = plan
        context['form'] = self.form_mixin if getattr(self, 'form_mixin', None) else ActivityForm(annual_work_plan=plan)
        return context

    def post(self, request, *args, **kwargs):
        plan = get_object_or_404(AnnualWorkPlan, pk=self.kwargs['annual_work_plan_pk'])
        form = ActivityForm(annual_work_plan=plan, data=request.POST)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.annual_work_plan = plan
            activity.save()
            return redirect('financial:annual_work_plan_detail', pk=plan.pk)
        self.form_mixin = form
        return self.get(request, *args, **kwargs)


class ActivityUpdateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.UpdateView):
    model = Activity
    template_name = 'activity_add.html'
    context_object_name = 'activity'
    active_level1 = 'financial'
    form_class = ActivityForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        instance = self.get_object()
        context['annual_work_plan'] = instance.annual_work_plan
        context['form'] = self.form_mixin if getattr(self, 'form_mixin', None) else ActivityForm(
            annual_work_plan=instance.annual_work_plan, instance=instance
        )
        return context

    def post(self, request, *args, **kwargs):
        instance = self.get_object()
        form = ActivityForm(annual_work_plan=instance.annual_work_plan, data=request.POST, instance=instance)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.annual_work_plan = instance.annual_work_plan
            activity.save()
            return redirect('financial:annual_work_plan_detail', pk=instance.annual_work_plan.pk)
        self.form_mixin = form
        return self.get(request, *args, **kwargs)


class ActivityDeleteView(PageMixin, LoginRequiredMixin, FinancialPermissionRequiredMixin, generic.DeleteView):
    """Only the Financial group and superusers may delete an activity."""

    model = Activity
    template_name = 'components/confirm_delete.html'
    title = _('Delete activity')
    active_level1 = 'financial'

    def get_success_url(self):
        return reverse_lazy('financial:annual_work_plan_detail', kwargs={'pk': self.object.annual_work_plan_id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = reverse_lazy('financial:annual_work_plan_detail', kwargs={'pk': self.object.annual_work_plan_id})
        return context
