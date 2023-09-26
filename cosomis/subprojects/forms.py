from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Subproject, VulnerableGroup, SubprojectStep, Level, Step, Component
from administrativelevels.models import AdministrativeLevel, CVD
from subprojects import (
    SUB_PROJECT_SECTORS, TYPES_OF_SUB_PROJECT, WORKS_TYPE_OF_SUB_PROJECT,
    LEVEL_OF_ACHIEVEMENT_DONATION_CERTIFICATE_OF_SUB_PROJECT,
    SUB_PROJECT_STEP_STANDART
)

class SubprojectForm(forms.ModelForm):
    subproject_sector = forms.ChoiceField(label=_("Subproject sector"), required=True)
    type_of_subproject = forms.ChoiceField(label=_("Type of subproject"), required=True)
    works_type = forms.ChoiceField(label=_("Works type"), required=True)
    level_of_achievement_donation_certificate = forms.ChoiceField(label=_("Level of donation certificate"), required=True)

    def __init__(self, *args, **kwargs):
        super(SubprojectForm, self).__init__(*args, **kwargs)
        __villages = AdministrativeLevel.objects.filter(type="Village")
        __cantons = AdministrativeLevel.objects.filter(type="Canton")
        for label, field in self.fields.items():
            self.fields[label].widget.attrs.update({'class' : 'form-control'})
            if label in ("list_of_beneficiary_villages", \
                         "list_of_villages_crossed_by_the_track_or_electrification", \
                            "location_subproject_realized"):
                self.fields[label].queryset = __villages
            
            if label == "canton":
                self.fields[label].queryset = __cantons
                self.fields[label].help_text = _("Fill in this field only if the subproject concerns all the villages in the canton.")
                self.fields[label].label = self.fields[label].label + \
                f" ({_('Fill in this field only if the subproject concerns all the villages in the canton.')})"
            
            if "date" in label:
                self.fields[label].widget.attrs['class'] = 'form-control datetimepicker-input'
            
            choices_datas = {
                'subproject_sector': SUB_PROJECT_SECTORS,
                'type_of_subproject': TYPES_OF_SUB_PROJECT,
                'works_type': WORKS_TYPE_OF_SUB_PROJECT,
                'level_of_achievement_donation_certificate': LEVEL_OF_ACHIEVEMENT_DONATION_CERTIFICATE_OF_SUB_PROJECT
            }
            instance_datas = {
                'subproject_sector': self.instance.subproject_sector,
                'type_of_subproject': self.instance.type_of_subproject,
                'works_type': self.instance.works_type,
                'level_of_achievement_donation_certificate': self.instance.level_of_achievement_donation_certificate
            }
            if label in ('subproject_sector', 'type_of_subproject', 'works_type', 'level_of_achievement_donation_certificate'):
                self.fields[label].choices = choices_datas[label]
                self.fields[label].widget.choices = choices_datas[label]
                if instance_datas[label]:
                    self.fields[label].initial = instance_datas[label]
            
            if label == "component":
                self.fields[label].queryset = Component.objects.filter(parent__name="Composante 1")

    class Meta:
        model = Subproject
        # fields = '__all__' # specify the fields to be displayed
        exclude = ('cvd', 'lot')


class VulnerableGroupForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(VulnerableGroupForm, self).__init__(*args, **kwargs)
        __villages = AdministrativeLevel.objects.filter(type="Village")
        for label, field in self.fields.items():
            self.fields[label].widget.attrs.update({'class' : 'form-control'})
            if label == "administrative_level":
                self.fields[label].queryset = __villages
                self.fields[label].label = "Village"


    class Meta:
        model = VulnerableGroup
        fields = '__all__' # specify the fields to be displayed

#Add
class SubprojectAddStepForm(forms.ModelForm):
    begin = forms.DateField(label=_('Begin'), input_formats=['%d/%m/%Y'],
                                      help_text="DD/MM/YYYY")
    # end = forms.DateField(label=_('End'), input_formats=['%d/%m/%Y'],
    #                                   help_text="DD/MM/YYYY", required=False)
    level_image = forms.FileField(label=_('Image of this level'), required=False)
    level_other_file = forms.FileField(label=_('Another file considered important at this level'), required=False)
    def __init__(self, *args, **kwargs):
        # initial = kwargs.get('initial')
        # doc_id = initial.get('doc_id')
        super().__init__(*args, **kwargs)
        for label, field in self.fields.items():
            if label in ("begin", "end"):
                self.fields[label].widget.attrs['class'] = 'form-control datetimepicker-input'

            if label == "step":
                self.fields[label].queryset = Step.objects.all().order_by("ranking")

    class Meta:
        model = SubprojectStep
        fields = (
            'step', 'begin', 'description', 
            'amount_spent_at_this_step', 'level_image', 'level_other_file'
        ) # specify the fields to be displayed
        exclude = ('end', 'total_amount_spent')


class SubprojectAddLevelForm(forms.ModelForm):
    begin = forms.DateField(label=_('Begin'), input_formats=['%d/%m/%Y'],
                                      help_text="DD/MM/YYYY")
    # end = forms.DateField(label=_('End'), input_formats=['%d/%m/%Y'],
    #                                   help_text="DD/MM/YYYY", required=False)
    level_image = forms.FileField(label=_('Image of this level'), required=False)
    level_other_file = forms.FileField(label=_('Another file considered important at this level'), required=False)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for label, field in self.fields.items():
            if label in ("begin", "end"):
                self.fields[label].widget.attrs['class'] = 'form-control datetimepicker-input'

    class Meta:
        model = Level
        fields = (
            'wording', 'percent', 'ranking', 'begin', 'description', 
            'amount_spent_at_this_step', 'level_image', 'level_other_file'
        ) # specify the fields to be displayed
        exclude = ('end', 'total_amount_spent')
#And Add



# #Delete
# class DeleteConfirmForm(forms.Form):
#     confirmation = forms.BooleanField(label=_('Please check this box and click the confirmation button for validation.'),
#                                        widget=forms.CheckboxInput, required=True)
    
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
# #And Delete


class SubprojectFilterForm(forms.Form):
    subproject_sectors = forms.MultipleChoiceField()
    subproject_types = forms.MultipleChoiceField()
    works_type_of_subproject = forms.MultipleChoiceField()
    subproject_step = forms.MultipleChoiceField()

    def __init__(self, has_all=True, *args, **kwargs):
        super().__init__(*args, **kwargs)

        init_list = [('', ''), ('All', _('All'))] if has_all else []
        query_result_subproject_sectors = sorted(init_list + list(SUB_PROJECT_SECTORS))
        query_result_subproject_types = sorted(init_list + list(TYPES_OF_SUB_PROJECT))
        query_result_works_type_of_subproject = sorted(init_list + list(WORKS_TYPE_OF_SUB_PROJECT))
        query_result_subproject_step = init_list + list(SUB_PROJECT_STEP_STANDART)
        
        
        self.fields['subproject_sectors'].widget.choices = query_result_subproject_sectors
        self.fields['subproject_types'].widget.choices = query_result_subproject_types
        self.fields['works_type_of_subproject'].widget.choices = query_result_works_type_of_subproject
        self.fields['subproject_step'].widget.choices = query_result_subproject_step