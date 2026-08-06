import pandas as pd
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import generic

from cosomis.mixins import PageMixin, SoftDeleteViewMixin
from usermanager.permissions import AccountantPermissionRequiredMixin, FinancialPermissionRequiredMixin

from subprojects.models import Component
from financial.models.planning import AnnualWorkPlan, Activity
from financial.forms import AnnualWorkPlanForm, ActivityForm, PTBAActivityFormSet
from financial.exports import export_annual_work_plan
from financial.list_filters import apply_entity_filters, build_filter_context
from financial.management.commands.import_disbursement_workbook import get_value, to_str, to_float


def _filtered_annual_work_plans(get):
    qs = AnnualWorkPlan.objects.all().order_by('-period', 'name')
    search = get.get('search', None)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(project__name__icontains=search))
    return apply_entity_filters(
        qs, get,
        project='project_id',
        funding='activity__component__fundings',
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
            obj = form.save(commit=False)
            obj.save(user=request.user)
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
            obj = form.save(commit=False)
            obj.save(user=request.user)
            return redirect('financial:annual_work_plan_detail', pk=self.get_object().pk)
        self.form_mixin = form
        return super().get(request, *args, **kwargs)


class AnnualWorkPlanDeleteView(PageMixin, LoginRequiredMixin, FinancialPermissionRequiredMixin, SoftDeleteViewMixin, generic.DeleteView):
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


def _save_activity_formset(plan, post_data, user):
    """Validates + saves the PTBAActivityFormSet for `plan` - shared by the
    detail page's embedded table and the dedicated activities sheet page so the
    two can never drift. Returns (formset, success)."""
    formset = PTBAActivityFormSet(post_data, instance=plan, form_kwargs={'project': plan.project})
    if not formset.is_valid():
        return formset, False
    activities = formset.save(commit=False)
    for activity in activities:
        activity.save(user=user)
    for obj in formset.deleted_objects:
        obj.delete()
    return formset, True


class AnnualWorkPlanDetailView(PageMixin, LoginRequiredMixin, generic.DetailView):
    """The Activités table is an inline formset directly on this page (no more
    popup add/edit pages needed) - rows can be added, edited and deleted, then
    saved together in one submit. See also AnnualWorkPlanActivitySheetView for
    the dedicated full-page spreadsheet-style editor."""

    model = AnnualWorkPlan
    template_name = 'annual_work_plan_detail.html'
    context_object_name = 'annual_work_plan'
    title = _('Annual work plan')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        plan = self.object
        ctx['activities'] = plan.activity_set.all()
        if getattr(self, 'formset_mixin', None):
            ctx['formset'] = self.formset_mixin
        else:
            ctx['formset'] = PTBAActivityFormSet(instance=plan, form_kwargs={'project': plan.project})
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = plan = self.get_object()
        formset, success = _save_activity_formset(plan, request.POST, request.user)
        if success:
            return redirect('financial:annual_work_plan_detail', pk=plan.pk)
        self.formset_mixin = formset
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


class AnnualWorkPlanActivitySheetView(PageMixin, LoginRequiredMixin, generic.DetailView):
    """Dedicated, spreadsheet-style page for a PTBA's activities (one row per
    Activity - add/edit/delete rows, save them all at once) - a more spacious
    alternative to the compact table embedded in the PTBA detail page, reusing
    the exact same PTBAActivityFormSet so the two never drift."""

    model = AnnualWorkPlan
    template_name = 'annual_work_plan_sheet.html'
    context_object_name = 'annual_work_plan'
    title = _('Activities sheet')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        plan = self.object
        if getattr(self, 'formset_mixin', None):
            ctx['formset'] = self.formset_mixin
        else:
            ctx['formset'] = PTBAActivityFormSet(instance=plan, form_kwargs={'project': plan.project})
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = plan = self.get_object()
        formset, success = _save_activity_formset(plan, request.POST, request.user)
        if success:
            messages.success(request, _("Activities saved."))
            return redirect('financial:annual_work_plan_activity_sheet', pk=plan.pk)
        self.formset_mixin = formset
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


class AnnualWorkPlanExportView(PageMixin, LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        return export_annual_work_plan(_filtered_annual_work_plans(request.GET))


class AnnualWorkPlanActivityImportView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.View):
    """Imports Activités for a single PTBA from a lightweight .xlsx (Composante,
    Libellé, Montant, Cible(s) columns, matching import_disbursement_workbook.py's
    column names) - a scoped alternative to the full multi-sheet import command,
    for adding/updating just this plan's activities from a spreadsheet."""

    def post(self, request, *args, **kwargs):
        plan = get_object_or_404(AnnualWorkPlan, pk=kwargs['pk'])
        uploaded = request.FILES.get('file')
        if not uploaded:
            messages.error(request, _("No file was uploaded."))
            return redirect('financial:annual_work_plan_detail', pk=plan.pk)

        df = pd.read_excel(uploaded)
        created, updated, skipped = 0, 0, 0
        for _row_index, row in df.iterrows():
            ref = to_str(get_value(row, 'ID_Activité', 'ID_Activite'))
            component_ref = to_str(get_value(row, 'ID_Composante', 'ID_SousComposante'))
            component_name = to_str(get_value(row, 'Composante', 'Sous-composante', 'Nom de la composante'))
            name = to_str(get_value(row, 'Libellé', 'Nom'))
            amount = to_float(get_value(row, 'Montant'))

            component = None
            if component_ref:
                component = Component.objects.filter(project=plan.project, external_id=component_ref).first()
            if not component and component_name:
                component = Component.objects.filter(project=plan.project, name=component_name).first()

            if not component or not name or amount is None:
                skipped += 1
                continue

            target = to_str(get_value(row, 'Cible(s)', 'Cibles'))

            # Re-uploading a corrected file should update in place rather than
            # duplicate: match by external_id if given, else by (plan, component,
            # name) - the file rarely carries an ID_Activité column.
            activity = Activity.objects.filter(external_id=ref).first() if ref else None
            if not activity:
                activity = Activity.objects.filter(annual_work_plan=plan, component=component, name=name).first()
            if activity:
                activity.component = component
                activity.amount = amount
                activity.target = target
                if ref:
                    activity.external_id = ref
                activity.save(user=request.user)
                updated += 1
            else:
                Activity(
                    external_id=ref, component=component, annual_work_plan=plan,
                    name=name, amount=amount, target=target,
                ).save(user=request.user)
                created += 1

        messages.success(request, _("Import complete: %(created)s created, %(updated)s updated, %(skipped)s skipped.") % {
            'created': created, 'updated': updated, 'skipped': skipped,
        })
        return redirect('financial:annual_work_plan_detail', pk=plan.pk)


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
            activity.save(user=request.user)
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
            activity.save(user=request.user)
            return redirect('financial:annual_work_plan_detail', pk=instance.annual_work_plan.pk)
        self.form_mixin = form
        return self.get(request, *args, **kwargs)


class ActivityDeleteView(PageMixin, LoginRequiredMixin, FinancialPermissionRequiredMixin, SoftDeleteViewMixin, generic.DeleteView):
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
