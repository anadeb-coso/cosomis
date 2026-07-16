from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import generic

from cosomis.mixins import PageMixin
from usermanager.permissions import AccountantPermissionRequiredMixin, FinancialPermissionRequiredMixin

from subprojects.models import CategoryIDA, Component
from financial.models.planning import Activity
from financial.forms import CategoryIDAForm
from financial.aggregations import activity_financial_summary
from financial.exports import export_category
from financial.list_filters import apply_entity_filters, build_filter_context


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
        context['form'] = self.form_mixin if getattr(self, 'form_mixin', None) else CategoryIDAForm()
        return context

    def post(self, request, *args, **kwargs):
        form = CategoryIDAForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('financial:category_list')
        self.form_mixin = form
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
        context['form'] = self.form_mixin if getattr(self, 'form_mixin', None) else CategoryIDAForm(instance=self.get_object())
        return context

    def post(self, request, *args, **kwargs):
        form = CategoryIDAForm(request.POST, instance=self.get_object())
        if form.is_valid():
            form.save()
            return redirect('financial:category_list')
        self.form_mixin = form
        return super().get(request, *args, **kwargs)


class CategoryDeleteView(PageMixin, LoginRequiredMixin, FinancialPermissionRequiredMixin, generic.DeleteView):
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
        components = Component.objects.filter(category=category)
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
