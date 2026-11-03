"""Results framework pages: indicators per IDA project, their measurements and achievement rate."""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext, gettext_lazy as _
from django.views import generic
from django.views.decorators.http import require_POST

from cosomis.access import EditorRequiredMixin, SaveWithHistoryMixin, can_edit
from cosomis.project_scope import ProjectRequiredMixin, ProjectScope, project_required
from results_framework.models import IndicatorMeasurement, ResultIndicator
from subprojects.models import Component, Project

ACTIVE = 'results_framework'


def indicators_in_scope(request):
    """Indicators of the projects shown on the page (selection + linked projects, or the filtered one)."""
    return ResultIndicator.objects.filter(project_id__in=ProjectScope(request).ids)


def _styled(form):
    for field in form.fields.values():
        if not isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs.setdefault('class', 'form-control')
    return form


class ResultIndicatorForm(forms.ModelForm):
    class Meta:
        model = ResultIndicator
        fields = ['project', 'component', 'code', 'label', 'indicator_type', 'unit', 'baseline_value', 'baseline_year',
                  'target', 'target_year', 'frequency', 'responsible', 'means_of_verification', 'description']
        widgets = {'means_of_verification': forms.Textarea(attrs={'rows': 2}), 'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, project_ids=None, **kwargs):
        super().__init__(*args, **kwargs)
        projects, components = Project.objects.order_by('name'), Component.objects.order_by('name')
        if project_ids is not None:
            projects, components = projects.filter(pk__in=project_ids), components.filter(project_id__in=project_ids)
        self.fields['project'].queryset = projects
        self.fields['component'].queryset = components
        _styled(self)

    def clean(self):
        data = super().clean()
        component, project = data.get('component'), data.get('project')
        if component and project and getattr(component, 'project_id', None) and component.project_id != project.pk:
            self.add_error('component', _("The component must belong to the selected IDA project."))
        return data


class MeasurementForm(forms.ModelForm):
    class Meta:
        model = IndicatorMeasurement
        fields = ['date', 'value', 'source', 'comment']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
                   'source': forms.Textarea(attrs={'rows': 2}), 'comment': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _styled(self)

    def validate_unique(self):
        # The indicator is set on the instance, not in the form fields: check "one value per date" here.
        try:
            self.instance.validate_unique()
            self.instance.validate_constraints()
        except forms.ValidationError as error:
            self._update_errors(error)


def _rate_class(rate):
    if rate is None:
        return 'secondary'
    if rate >= 100:
        return 'success'
    if rate >= 50:
        return 'info'
    if rate >= 25:
        return 'warning'
    return 'danger'


@login_required
@project_required
def indicator_list(request):
    scope = ProjectScope(request)
    indicator_type = request.GET.get('type', '')
    search = request.GET.get('q', '').strip()
    indicators = (indicators_in_scope(request).select_related('project', 'component')
                  .prefetch_related(Prefetch('measurements', IndicatorMeasurement.objects.order_by('-date'))))
    if indicator_type:
        indicators = indicators.filter(indicator_type=indicator_type)
    if search:
        indicators = indicators.filter(Q(label__icontains=search) | Q(code__icontains=search))

    groups, by_project = [], {}
    for indicator in indicators.order_by('project__name', 'indicator_type', 'code'):
        measurements = list(indicator.measurements.all())
        latest = measurements[0] if measurements else None
        rate = indicator.achievement_rate if latest else None
        if indicator.project_id not in by_project:
            by_project[indicator.project_id] = {'project': indicator.project, 'rows': []}
            groups.append(by_project[indicator.project_id])
        by_project[indicator.project_id]['rows'].append({
            'indicator': indicator, 'latest': latest, 'rate': rate, 'rate_class': _rate_class(rate),
            'bar': max(0, min(float(rate), 100)) if rate is not None else 0,
        })
    all_rows = [row for group in groups for row in group['rows']]
    rated = [row['rate'] for row in all_rows if row['rate'] is not None]
    figures = {
        'total': len(all_rows),
        'measured': sum(1 for row in all_rows if row['latest']),
        'achieved': sum(1 for rate in rated if rate >= 100),
        'average': round(sum(min(float(r), 100) for r in rated) / len(rated), 1) if rated else None,
    }
    return render(request, 'results_framework/indicator_list.html', {
        'title': gettext("Results framework"), 'active_level1': ACTIVE,
        'breadcrumb': [{'url': '', 'title': gettext("Results framework")}],
        'groups': groups, 'figures': figures, 'types': ResultIndicator.IndicatorType.choices,
        'selected_type': indicator_type, 'search': search, 'can_edit': can_edit(request.user), **scope.context(),
    })


@login_required
@project_required
def indicator_detail(request, pk):
    indicator = get_object_or_404(indicators_in_scope(request).select_related('project', 'component'), pk=pk)
    measurements = list(indicator.measurements.order_by('-date'))
    form = MeasurementForm(request.POST or None, instance=IndicatorMeasurement(indicator=indicator))
    if request.method == 'POST':
        if not can_edit(request.user):
            raise Http404
        if form.is_valid():
            form.instance.save_and_return_object(request.user)
            messages.success(request, gettext("The measurement has been saved."))
            return redirect('results_framework:indicator_detail', pk=indicator.pk)
    rate = indicator.achievement_rate
    chart = [{'date': m.date.strftime('%d/%m/%Y'), 'value': float(m.value)} for m in reversed(measurements)]
    return render(request, 'results_framework/indicator_detail.html', {
        'title': str(indicator), 'active_level1': ACTIVE,
        'breadcrumb': [{'url': reverse('results_framework:indicator_list'), 'title': gettext("Results framework")},
                       {'url': '', 'title': indicator.code or indicator.label[:40]}],
        'indicator': indicator, 'measurements': measurements, 'form': form, 'rate': rate,
        'rate_class': _rate_class(rate), 'bar': max(0, min(float(rate), 100)) if rate is not None else 0,
        'chart': chart, 'can_edit': can_edit(request.user),
    })


class IndicatorMixin(ProjectRequiredMixin, EditorRequiredMixin, SaveWithHistoryMixin):
    model = ResultIndicator
    form_class = ResultIndicatorForm
    template_name = 'common/page_form.html'
    active_level1 = ACTIVE

    def get_queryset(self):
        return indicators_in_scope(self.request)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), 'project_ids': ProjectScope(self.request).available_ids}

    def get_success_url(self):
        return reverse('results_framework:indicator_detail', args=[self.object.pk])

    def get_back_url(self):
        return reverse('results_framework:indicator_list')


class IndicatorCreateView(IndicatorMixin, generic.CreateView):
    page_title = _("New indicator")

    def get_initial(self):
        return {'project': self.request.GET.get('project')}


class IndicatorUpdateView(IndicatorMixin, generic.UpdateView):
    page_title = _("Edit indicator")


@login_required
@require_POST
def indicator_delete(request, pk):
    if not can_edit(request.user):
        raise Http404
    get_object_or_404(indicators_in_scope(request), pk=pk).soft_delete(user=request.user)
    messages.success(request, gettext("The indicator has been deleted."))
    return redirect('results_framework:indicator_list')


class MeasurementUpdateView(ProjectRequiredMixin, EditorRequiredMixin, SaveWithHistoryMixin, generic.UpdateView):
    model = IndicatorMeasurement
    form_class = MeasurementForm
    template_name = 'common/page_form.html'
    active_level1 = ACTIVE
    page_title = _("Edit measurement")

    def get_queryset(self):
        return IndicatorMeasurement.objects.filter(indicator__in=indicators_in_scope(self.request))

    def get_success_url(self):
        return reverse('results_framework:indicator_detail', args=[self.object.indicator_id])

    def get_back_url(self):
        return self.get_success_url()


@login_required
@require_POST
def measurement_delete(request, pk):
    if not can_edit(request.user):
        raise Http404
    measurement = get_object_or_404(IndicatorMeasurement.objects.filter(indicator__in=indicators_in_scope(request)), pk=pk)
    indicator_id = measurement.indicator_id
    measurement.delete()
    messages.success(request, gettext("The measurement has been deleted."))
    return redirect('results_framework:indicator_detail', pk=indicator_id)
