from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import generic

from cosomis.mixins import PageMixin, SoftDeleteViewMixin
from usermanager.permissions import AccountantPermissionRequiredMixin, FinancialPermissionRequiredMixin

from subprojects.models import Project, CategoryIDA, Component
from financial.models.planning import Activity
from financial.forms import CategoryIDAForm, CategoryComponentFormSet
from financial.aggregations import activity_financial_summary, funding_cascade_meta, component_financial_breakdown
from financial.exports import export_category
from financial.list_filters import apply_entity_filters, build_filter_context


def _component_formset_kwargs(category, post_data=None):
    """Resolves the project/category the embedded Composantes/Sous-composantes
    formset should scope its `fundings`/`parent` choices to - reads the submitted
    `project` value first (the CategoryIDAForm may be changing it in this very
    POST), falling back to the persisted instance for a GET render."""
    project_id = None
    if post_data:
        project_id = post_data.get('project')
    if not project_id and category and category.pk:
        project_id = category.project_id
    return {
        'project': Project.objects.filter(pk=project_id).first() if project_id else None,
        'category_pk': category.pk if category and category.pk else None,
    }


def _filtered_categories(get):
    qs = CategoryIDA.objects.all().order_by('name')
    search = get.get('search', None)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(project__name__icontains=search))
    return apply_entity_filters(qs, get, project='project_id')


class CategoryListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = CategoryIDA
    queryset = []
    template_name = 'category_list.html'
    context_object_name = 'categories'
    title = _('IDA categories')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_queryset(self):
        page_number = self.request.GET.get('page', None)
        return Paginator(_filtered_categories(self.request.GET), 100).get_page(page_number)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(build_filter_context(self.request, projects=True))
        return ctx


class CategoryCreateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.CreateView):
    model = CategoryIDA
    template_name = 'category_add.html'
    context_object_name = 'category'
    title = _('Register an IDA category')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]
    form_class = CategoryIDAForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if getattr(self, 'form_mixin', None):
            context['form'] = self.form_mixin
            context['formset'] = self.formset_mixin
        else:
            context['form'] = CategoryIDAForm()
            context['formset'] = CategoryComponentFormSet(instance=CategoryIDA(), form_kwargs=_component_formset_kwargs(None))
        context['funding_meta'] = funding_cascade_meta()
        return context

    def post(self, request, *args, **kwargs):
        form = CategoryIDAForm(request.POST)
        category = form.instance
        formset = CategoryComponentFormSet(request.POST, instance=category, form_kwargs=_component_formset_kwargs(category, request.POST))
        if form.is_valid() and formset.is_valid():
            form.save(commit=False)
            category.save(user=request.user)
            components = formset.save(commit=False)
            for component in components:
                component.project = category.project
                component.save(user=request.user)
            for obj in formset.deleted_objects:
                obj.delete()
            formset.save_m2m()
            return redirect('financial:category_list')
        self.form_mixin = form
        self.formset_mixin = formset
        return super().get(request, *args, **kwargs)


class CategoryUpdateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, generic.UpdateView):
    model = CategoryIDA
    template_name = 'category_add.html'
    context_object_name = 'category'
    title = _('Update IDA category')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]
    form_class = CategoryIDAForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        instance = self.get_object()
        if getattr(self, 'form_mixin', None):
            context['form'] = self.form_mixin
            context['formset'] = self.formset_mixin
        else:
            context['form'] = CategoryIDAForm(instance=instance)
            context['formset'] = CategoryComponentFormSet(instance=instance, form_kwargs=_component_formset_kwargs(instance))
        context['funding_meta'] = funding_cascade_meta()
        return context

    def post(self, request, *args, **kwargs):
        instance = self.get_object()
        form = CategoryIDAForm(request.POST, instance=instance)
        formset = CategoryComponentFormSet(request.POST, instance=instance, form_kwargs=_component_formset_kwargs(instance, request.POST))
        if form.is_valid() and formset.is_valid():
            form.save(commit=False)
            instance.save(user=request.user)
            components = formset.save(commit=False)
            for component in components:
                component.project = instance.project
                component.save(user=request.user)
            for obj in formset.deleted_objects:
                obj.delete()
            formset.save_m2m()
            return redirect('financial:category_list')
        self.form_mixin = form
        self.formset_mixin = formset
        return super().get(request, *args, **kwargs)


class CategoryDeleteView(PageMixin, LoginRequiredMixin, FinancialPermissionRequiredMixin, SoftDeleteViewMixin, generic.DeleteView):
    """Only the Financial group and superusers may delete a category."""

    model = CategoryIDA
    template_name = 'components/confirm_delete.html'
    title = _('Delete IDA category')
    active_level1 = 'financial'
    success_url = reverse_lazy('financial:category_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = reverse_lazy('financial:category_list')
        return context


class CategoryDetailView(PageMixin, LoginRequiredMixin, generic.DetailView):
    model = CategoryIDA
    template_name = 'category_detail.html'
    context_object_name = 'category'
    title = _('IDA category')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        category = self.object
        components = list(Component.objects.filter(category=category))
        for component in components:
            component.planning = component_financial_breakdown(component)
        top_level = [c for c in components if c.parent_id is None]
        sub_level = [c for c in components if c.parent_id is not None]
        ctx['components'] = top_level
        ctx['sub_components'] = sub_level
        ctx['activities'] = Activity.objects.filter(component__category=category)
        ctx['summary'] = activity_financial_summary([c.pk for c in components])
        return ctx


class CategoryExportView(PageMixin, LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        return export_category(_filtered_categories(request.GET))
