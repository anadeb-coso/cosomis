from django import forms
from django.utils.translation import gettext_lazy as _

from administrativelevels.grm.functions import (
    get_issue_category_choices, get_issue_status_choices
)


class SearchIssueForm(forms.Form):
    start_date = forms.DateTimeField(label=_('Start Date'))
    end_date = forms.DateTimeField(label=_('End Date'))
    code = forms.CharField(label=_('ID Number / Access Code'))
    category = forms.ChoiceField()
    status = forms.ChoiceField()
    other = forms.ChoiceField()
    publish = forms.ChoiceField()
    administrative_id = forms.IntegerField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        initial = kwargs.get('initial')
        self.fields['administrative_id'].initial = initial.get('administrative_id')

        self.fields['start_date'].widget.attrs['class'] = self.fields['end_date'].widget.attrs[
            'class'] = 'form-control datetimepicker-input'
        self.fields['start_date'].widget.attrs['data-target'] = '#start_date'
        self.fields['end_date'].widget.attrs['data-target'] = '#end_date'
        self.fields['category'].widget.choices = get_issue_category_choices()
        # self.fields['type'].widget.choices = get_issue_type_choices()
        self.fields['status'].widget.choices = get_issue_status_choices()
        self.fields['other'].widget.choices = [('', ''), ('Escalate', _('Escalated'))]
        self.fields['publish'].widget.choices = [('', ''), (True, _('Publish')), (False, _('Unpublish'))]