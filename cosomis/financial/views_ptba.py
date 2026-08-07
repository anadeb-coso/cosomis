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
from financial.models.planning import AnnualWorkPlan, Activity, ActivityFunding
from financial.models.funding import Funding
from financial.forms import AnnualWorkPlanForm, ActivityForm, PTBAActivityFormSet
from financial.aggregations import activity_sort_key
from financial.exports import export_annual_work_plan
from financial.list_filters import apply_entity_filters, build_filter_context
from financial.management.commands.import_disbursement_workbook import get_value, to_str, to_float


def _sort_formset_forms(formset):
    """Reorders an already-built PTBAActivityFormSet's display order by
    activity_sort_key (component natural order, then code) - blank/unsaved extra
    rows (no instance.pk yet) are left at the end so "add a new line" still
    appears last rather than jumping to wherever an empty sort key would land.
    Only the display order changes - form prefixes/indices (and therefore POST
    processing) are untouched."""
    existing = [f for f in formset.forms if f.instance.pk]
    new = [f for f in formset.forms if not f.instance.pk]
    existing.sort(key=lambda f: activity_sort_key(f.instance))
    formset.forms = existing + new
    return formset


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


def _save_activity_fundings(formset, post_data, project, user):
    """Upserts ActivityFunding rows from the per-Funding amount matrix rendered
    alongside the PTBAActivityFormSet (one column per Funding of the PTBA's
    project - see annual_work_plan_detail.html / annual_work_plan_sheet.html).
    Each cell is submitted as "<form.prefix>-funding_<funding.pk>" - reusing the
    formset's own prefixes means the empty-row JS template (which already
    rewrites __prefix__ to the real index) needs no extra wiring for these
    inputs. An amount left blank/zero removes the link, matching "si le montant
    est renseigné, ce Crédit/Don est [lié] à l'activité"."""
    from financial.management.commands.import_disbursement_workbook import to_float

    fundings = list(Funding.objects.filter(project=project))
    if not fundings:
        return
    for form in formset.forms:
        if form in formset.deleted_forms:
            continue
        activity = form.instance
        if not activity.pk:
            continue
        for funding in fundings:
            raw = post_data.get(f'{form.prefix}-funding_{funding.pk}')
            amount = to_float(raw) if raw not in (None, '') else None
            existing = ActivityFunding.objects.filter(activity=activity, funding=funding).first()
            if amount:
                if existing:
                    if existing.amount != amount:
                        existing.amount = amount
                        existing.save(user=user)
                else:
                    ActivityFunding(activity=activity, funding=funding, amount=amount).save(user=user)
            elif existing:
                existing.delete()


def _activity_funding_amounts_map(activity_ids, project_fundings):
    """{activity_id: {funding_id: amount}} for the given activities - the raw
    data behind the per-Funding amount matrix (see _attach_funding_amounts()
    and _attach_funding_amounts_readonly() below)."""
    activity_ids = [pk for pk in activity_ids if pk]
    if not activity_ids:
        return {}
    links = ActivityFunding.objects.filter(activity_id__in=activity_ids, funding__in=project_fundings)
    amounts_by_activity = {}
    for link in links:
        amounts_by_activity.setdefault(link.activity_id, {})[link.funding_id] = link.amount
    return amounts_by_activity


def _attach_funding_amounts(forms_list, project_fundings):
    """Pre-fills form.funding_amounts (a {funding_id: amount} dict) for every
    form so the template can render each existing ActivityFunding value in its
    matrix cell - empty for unsaved/extra rows, which simply have none yet."""
    amounts_by_activity = _activity_funding_amounts_map([f.instance.pk for f in forms_list], project_fundings)
    for form in forms_list:
        form.funding_amounts = amounts_by_activity.get(form.instance.pk, {})


def _attach_funding_amounts_readonly(activities, project_fundings):
    """Same as _attach_funding_amounts(), for a plain list/queryset of Activity
    instances (the read-only "Activities" tables on the PTBA/Project/Funding/
    Category/Component detail pages) rather than formset forms."""
    amounts_by_activity = _activity_funding_amounts_map([a.pk for a in activities], project_fundings)
    for activity in activities:
        activity.funding_amounts = amounts_by_activity.get(activity.pk, {})


def _save_activity_formset(plan, post_data, user):
    """Validates + saves the PTBAActivityFormSet for `plan` - shared by the
    detail page's embedded table and the dedicated activities sheet page so the
    two can never drift. Returns (formset, success)."""
    formset = PTBAActivityFormSet(post_data, instance=plan, form_kwargs={'project': plan.project, 'annual_work_plan': plan})
    if not formset.is_valid():
        return formset, False
    activities = formset.save(commit=False)
    for activity in activities:
        activity.save(user=user)
    for obj in formset.deleted_objects:
        obj.delete()
    formset.save_m2m()
    _save_activity_fundings(formset, post_data, plan.project, user)
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
        ctx['activities'] = sorted(plan.activity_set.select_related('component').all(), key=activity_sort_key)
        if getattr(self, 'formset_mixin', None):
            ctx['formset'] = self.formset_mixin
        else:
            ctx['formset'] = PTBAActivityFormSet(instance=plan, form_kwargs={'project': plan.project, 'annual_work_plan': plan})
        _sort_formset_forms(ctx['formset'])
        project_fundings = list(Funding.objects.filter(project=plan.project).order_by('label'))
        ctx['project_fundings'] = project_fundings
        _attach_funding_amounts(ctx['formset'].forms, project_fundings)
        ctx['formset'].empty_form.funding_amounts = {}
        _attach_funding_amounts_readonly(ctx['activities'], project_fundings)
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
            ctx['formset'] = PTBAActivityFormSet(instance=plan, form_kwargs={'project': plan.project, 'annual_work_plan': plan})
        _sort_formset_forms(ctx['formset'])
        project_fundings = list(Funding.objects.filter(project=plan.project).order_by('label'))
        ctx['project_fundings'] = project_fundings
        _attach_funding_amounts(ctx['formset'].forms, project_fundings)
        ctx['formset'].empty_form.funding_amounts = {}
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
    Code, Libellé, Montant, Statut, Cible(s) columns, matching
    import_disbursement_workbook.py's column names) - a scoped alternative to
    the full multi-sheet import command, for adding/updating just this plan's
    activities from a spreadsheet. Only the core fields are handled here (not
    the richer résultats/indicateurs/structures/period-of-realization set,
    which the full command and the "Edit full details" page both cover) -
    keeping this upload path quick for the common case of a plain activity list."""

    def post(self, request, *args, **kwargs):
        plan = get_object_or_404(AnnualWorkPlan, pk=kwargs['pk'])
        uploaded = request.FILES.get('file')
        if not uploaded:
            messages.error(request, _("No file was uploaded."))
            return redirect('financial:annual_work_plan_detail', pk=plan.pk)

        from financial.management.commands.import_disbursement_workbook import ACTIVITY_STATUS_MAP, map_choice

        df = pd.read_excel(uploaded)
        created, updated, skipped = 0, 0, 0
        for _row_index, row in df.iterrows():
            ref = to_str(get_value(row, 'ID_Activité', 'ID_Activite'))
            component_ref = to_str(get_value(row, 'ID_Composante', 'ID_SousComposante'))
            component_name = to_str(get_value(row, 'Composante', 'Sous-composante', 'Nom de la composante'))
            name = to_str(get_value(row, 'Libellé', 'Nom'))
            amount = to_float(get_value(row, 'Montant', 'Montant propre'))

            component = None
            if component_ref:
                component = Component.objects.filter(project=plan.project, external_id=component_ref).first()
            if not component and component_name:
                component = Component.objects.filter(project=plan.project, name=component_name).first()

            if not component or not name:
                skipped += 1
                continue

            code = to_str(get_value(row, 'Code'))
            target = to_str(get_value(row, 'Cible(s)', 'Cibles'))
            status = map_choice(get_value(row, 'Statut'), ACTIVITY_STATUS_MAP)

            # Re-uploading a corrected file should update in place rather than
            # duplicate: match by external_id if given, else by (plan, component,
            # name) - the file rarely carries an ID_Activité column.
            activity = Activity.objects.filter(external_id=ref).first() if ref else None
            if not activity:
                activity = Activity.objects.filter(annual_work_plan=plan, component=component, name=name).first()
            if activity:
                activity.component = component
                activity.amount = amount
                activity.code = code
                activity.target = target
                if status:
                    activity.status = status
                if ref:
                    activity.external_id = ref
                activity.save(user=request.user)
                updated += 1
            else:
                Activity(
                    external_id=ref, component=component, annual_work_plan=plan,
                    name=name, amount=amount, code=code, target=target,
                    status=status or Activity.Status.NOT_STARTED,
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
            form.save_m2m()
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
            form.save_m2m()
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
