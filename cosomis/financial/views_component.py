from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, get_object_or_404
from django.utils.translation import gettext_lazy as _
from django.views import generic

from cosomis.mixins import PageMixin
from usermanager.permissions import SuperAdminPermissionRequiredMixin, ComponentEditPermissionRequiredMixin

from subprojects.models import Component
from financial.models.planning import Activity
from financial.forms import ComponentForm
from financial.aggregations import activity_financial_summary, component_descendant_ids, category_cascade_meta, funding_cascade_meta, component_financial_breakdown, activity_sort_key
from financial.exports import export_component
from financial.list_filters import apply_entity_filters, build_filter_context


def _filtered_components(get):
    qs = Component.objects.all().order_by('name')
    search = get.get('search', None)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(project__name__icontains=search) | Q(category__name__icontains=search))
    qs = apply_entity_filters(qs, get, project='project_id', funding='fundings', category='category_id')
    parent_id = get.get('parent')
    if parent_id:
        qs = qs.filter(parent_id=parent_id)
    return qs


class ComponentListView(PageMixin, LoginRequiredMixin, generic.ListView):
    """Both "Composante" (parent=None) and "Sous-composante" (parent set, at any
    depth) records - the list clearly labels which is which, and a "parent" filter
    lets you drill into a specific component's children."""

    model = Component
    queryset = []
    template_name = 'component_list.html'
    context_object_name = 'components'
    title = _('Components')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_queryset(self):
        page_number = self.request.GET.get('page', None)
        return Paginator(_filtered_components(self.request.GET), 100).get_page(page_number)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(build_filter_context(self.request, projects=True, fundings=True, categories=True))
        ctx['show_parent_filter'] = True
        ctx['filter_parent_components'] = Component.objects.all().order_by('name')
        ctx['selected_parent'] = self.request.GET.get('parent')
        return ctx


class ComponentCreateView(PageMixin, LoginRequiredMixin, SuperAdminPermissionRequiredMixin, generic.CreateView):
    """Only superusers may register a component/sub-component."""

    model = Component
    template_name = 'component_add.html'
    context_object_name = 'component'
    active_level1 = 'financial'
    form_class = ComponentForm

    def _resolve_kwargs(self, request):
        category_id = request.GET.get('category_id') or request.POST.get('category_id')
        parent_id = request.GET.get('parent_id') or request.POST.get('parent_id')
        return category_id, parent_id

    def get(self, request, *args, **kwargs):
        category_id, parent_id = self._resolve_kwargs(request)
        self.title = _('Register a sub-component') if parent_id else _('Register a component')
        self.breadcrumb = [{'url': '', 'title': self.title}]
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category_id, parent_id = self._resolve_kwargs(self.request)
        context['form'] = self.form_mixin if getattr(self, 'form_mixin', None) else ComponentForm(category_id=category_id, parent_id=parent_id)
        context['category_id'] = category_id
        context['parent_id'] = parent_id
        if not parent_id:
            context['category_meta'] = category_cascade_meta()
            context['funding_meta'] = funding_cascade_meta()
        return context

    def post(self, request, *args, **kwargs):
        category_id, parent_id = self._resolve_kwargs(request)
        form = ComponentForm(category_id=category_id, parent_id=parent_id, data=request.POST)
        if form.is_valid():
            component = form.save(commit=False)
            if parent_id:
                parent = get_object_or_404(Component, pk=parent_id)
                component.parent = parent
                component.project = parent.project
            else:
                component.parent = None
                component.project = component.category.project if component.category_id else None
            component.save(user=request.user)
            form.save_m2m()
            if parent_id:
                return redirect('financial:component_detail', pk=parent_id)
            return redirect('financial:component_list')
        self.form_mixin = form
        return self.get(request, *args, **kwargs)


class ComponentUpdateView(PageMixin, LoginRequiredMixin, ComponentEditPermissionRequiredMixin, generic.UpdateView):
    """Financial/Evaluator/Accountant users and superusers may edit a
    component/sub-component's category, funding, description, own amount and
    target(s) - renaming it (the `name` field) stays superuser-only."""

    model = Component
    template_name = 'component_add.html'
    context_object_name = 'component'
    active_level1 = 'financial'
    form_class = ComponentForm

    def get(self, request, *args, **kwargs):
        instance = self.get_object()
        self.title = _('Update sub-component') if instance.parent_id else _('Update component')
        self.breadcrumb = [{'url': '', 'title': self.title}]
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        instance = self.get_object()
        category_id = instance.category_id
        parent_id = instance.parent_id
        context['form'] = self.form_mixin if getattr(self, 'form_mixin', None) else ComponentForm(
            category_id=category_id, parent_id=parent_id, instance=instance,
            restrict_name=not self.request.user.is_superuser,
        )
        context['category_id'] = category_id
        context['parent_id'] = parent_id
        if not parent_id:
            context['category_meta'] = category_cascade_meta()
            context['funding_meta'] = funding_cascade_meta()
        return context

    def post(self, request, *args, **kwargs):
        instance = self.get_object()
        parent_id = instance.parent_id
        category_id = instance.category_id
        form = ComponentForm(
            category_id=category_id, parent_id=parent_id, data=request.POST, instance=instance,
            restrict_name=not request.user.is_superuser,
        )
        if form.is_valid():
            component = form.save(commit=False)
            if parent_id:
                component.project = component.parent.project
            else:
                component.parent = None
                component.project = component.category.project if component.category_id else None
            component.save(user=request.user)
            form.save_m2m()
            if parent_id:
                return redirect('financial:component_detail', pk=parent_id)
            return redirect('financial:component_detail', pk=component.pk)
        self.form_mixin = form
        return self.get(request, *args, **kwargs)


class ComponentDetailView(PageMixin, LoginRequiredMixin, generic.DetailView):
    model = Component
    template_name = 'component_detail.html'
    context_object_name = 'component'
    title = _('Component')
    active_level1 = 'financial'
    breadcrumb = [{'url': '', 'title': title}]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        component = self.object
        sub_components = list(component.component_set.all())
        for sub in sub_components:
            sub.planning = component_financial_breakdown(sub)
        ctx['sub_components'] = sub_components
        # Descendants at any depth (a Sous-composante can itself have Sous-composantes)
        # so the activities/summary below aren't limited to direct children.
        descendant_ids = component_descendant_ids(component)
        component_ids = [component.pk] + descendant_ids
        ctx['activities'] = sorted(Activity.objects.filter(component_id__in=component_ids).select_related('component'), key=activity_sort_key)
        ctx['summary'] = activity_financial_summary(component_ids)
        return ctx


class ComponentExportView(PageMixin, LoginRequiredMixin, generic.View):
    def get(self, request, *args, **kwargs):
        return export_component(_filtered_components(request.GET))
