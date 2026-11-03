"""Reports page: predefined financial reports, on-demand generator (PDF, Word or Excel)
and periodic report templates sent by email."""
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy as _
from django.views import generic
from django.views.decorators.http import require_POST

from financial.models.funding import Funding
from reports.financial_reports import ReportParameters, ReportType, excel, pdf
from reports.word_report import word
from financial.models.report_template import ReportTemplate
from reports.sending import send
from subprojects.models import Project

CONTENT_TYPES = {
    'pdf': 'application/pdf',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}
RENDERERS = {'pdf': pdf, 'docx': word, 'xlsx': excel}
MANAGER_GROUPS = ('Accountant', 'Evaluator', 'Admin')


def can_manage_templates(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name__in=MANAGER_GROUPS).exists())


def _file_response(content, name, file_format):
    response = HttpResponse(content, content_type=CONTENT_TYPES[file_format])
    disposition = 'inline' if file_format == 'pdf' else 'attachment'
    response['Content-Disposition'] = f'{disposition}; filename="{name}.{file_format}"'
    return response


def _with_form_control(form):
    for field in form.fields.values():
        if not isinstance(field.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
            field.widget.attrs['class'] = 'form-control'


class ReportForm(forms.Form):
    report_type = forms.ChoiceField(choices=ReportType.choices, label=_("Report"))
    project = forms.ModelChoiceField(Project.objects.all().order_by('name'), required=False, label=_("IDA project"),
                                     empty_label=_("All"))
    funding = forms.ModelChoiceField(Funding.objects.all().order_by('label'), required=False, label=_("Credit / Grant"),
                                     empty_label=_("All"))
    year = forms.IntegerField(required=False, min_value=2000, max_value=2100, label=_("Year"))
    title = forms.CharField(required=False, label=_("Title (optional)"))
    format = forms.ChoiceField(choices=[('pdf', 'PDF'), ('docx', 'Word'), ('xlsx', 'Excel')], label=_("Format"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _with_form_control(self)


class ReportTemplateForm(forms.ModelForm):
    class Meta:
        model = ReportTemplate
        fields = ['title', 'report_type', 'project', 'funding', 'year', 'introduction', 'recipient_mention', 'signatory',
                  'periodicity', 'file_format', 'language', 'recipients', 'other_emails', 'is_active']
        widgets = {'introduction': forms.Textarea(attrs={'rows': 3}), 'other_emails': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['recipients'].queryset = get_user_model().objects.filter(is_active=True).exclude(email='').order_by(
            'first_name', 'last_name')
        self.fields['recipients'].label_from_instance = lambda u: f"{u.get_full_name() or u.username} <{u.email}>"
        _with_form_control(self)

    def clean_other_emails(self):
        value = self.cleaned_data.get('other_emails') or ''
        validator = forms.EmailField()
        for line in value.splitlines():
            if line.strip():
                validator.clean(line.strip())
        return value


@login_required
def reports_home(request):
    form = ReportForm(request.GET or None)
    if request.GET and form.is_valid():
        d = form.cleaned_data
        parameters = ReportParameters(report_type=d['report_type'], title=d['title'], project=d['project'],
                                      funding=d['funding'], year=d['year'])
        content = RENDERERS[d['format']](parameters)
        return _file_response(content, f"rapport_{d['report_type'].lower()}_{timezone.localdate():%Y%m%d}", d['format'])
    manager = can_manage_templates(request.user)
    return render(request, 'reports/reports.html', {
        'title': gettext("Reports"),
        'active_level1': 'reports',
        'breadcrumb': [{'url': '', 'title': gettext("Reports")}],
        'form': form,
        'types': ReportType.choices,
        'templates': ReportTemplate.objects.prefetch_related('recipients') if manager else None,
    })


class TemplateManagerMixin(LoginRequiredMixin, UserPassesTestMixin):
    model = ReportTemplate
    form_class = ReportTemplateForm
    template_name = 'reports/report_template_form.html'
    success_url = reverse_lazy('rapports:home')

    def test_func(self):
        return can_manage_templates(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['active_level1'] = 'reports'
        ctx['breadcrumb'] = [{'url': reverse_lazy('rapports:home'), 'title': gettext("Reports")},
                             {'url': '', 'title': self.page_title}]
        ctx['title'] = self.page_title
        return ctx

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.save_and_return_object(self.request.user)
        form.save_m2m()
        messages.success(self.request, gettext("The report template has been saved."))
        return redirect(self.success_url)


class ReportTemplateCreateView(TemplateManagerMixin, generic.CreateView):
    page_title = _("New report template")


class ReportTemplateUpdateView(TemplateManagerMixin, generic.UpdateView):
    page_title = _("Edit report template")


def _template_or_404(request, pk):
    if not can_manage_templates(request.user):
        raise Http404
    return get_object_or_404(ReportTemplate, pk=pk)


@login_required
def preview_template(request, pk):
    template = _template_or_404(request, pk)
    file_format = request.GET.get('format') if request.GET.get('format') in RENDERERS else 'pdf'
    content = RENDERERS[file_format](ReportParameters.from_template(template))
    return _file_response(content, f"apercu_{template.pk}", file_format)


@login_required
@require_POST
def send_template(request, pk):
    template = _template_or_404(request, pk)
    try:
        count = send(template, request.user)
    except Exception as error:
        messages.error(request, gettext("Sending failed: {error}").format(error=error))
    else:
        if count:
            messages.success(request, gettext("Report sent to {count} recipient(s).").format(count=count))
        else:
            messages.warning(request, gettext("No recipient is set for this template."))
    return redirect('rapports:home')


@login_required
@require_POST
def delete_template(request, pk):
    _template_or_404(request, pk).delete()
    messages.success(request, gettext("The report template has been deleted."))
    return redirect('rapports:home')
