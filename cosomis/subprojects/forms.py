from django import forms
from django.utils.translation import gettext_lazy as _
from datetime import date

from .models import Subproject, VulnerableGroup, SubprojectStep, Level, Step, Component
from administrativelevels.models import AdministrativeLevel, CVD
from subprojects import (
    WORKS_TYPE_OF_SUB_PROJECT,
    LEVEL_OF_ACHIEVEMENT_DONATION_CERTIFICATE_OF_SUB_PROJECT,
    SUB_PROJECT_STEP_STANDART, CURRENT_STATUS_OF_THE_SITE
)
from subprojects.vars import VAR_SUB_PROJECT_SECTORS, VAR_TYPES_OF_SUB_PROJECT, VAR_COMPONENTS
from cosomis import FORM_FIELDS_TO_EXCLUDE
from cosomis.constants import (
    STRUCTURE_NOT_START_STATUS, FIRST_CONTRACT_RANKING, OTHERS_CONTRACT_RANKING, SELECTED_COMPANY_RANKING,
    SITE_DISCOUNT_RANKING, ANOTHER_SITE_HANDED_OVER_FOR_CONSTRUCTION_RANKING, IN_PROGRESS_RANKING, ABANDONED_RANKING, 
    INTERRUPTED_RANKING, RESUME_IN_PROGRESS_RANKING
)

class SubprojectForm(forms.ModelForm):
    subproject_sector = forms.ChoiceField(label=_("Subproject sector"), required=True)
    type_of_subproject = forms.ChoiceField(label=_("Type of subproject"), required=True)
    works_type = forms.ChoiceField(label=_("Works type"), required=True)
    level_of_achievement_donation_certificate = forms.ChoiceField(label=_("Level of donation certificate"), required=True)
    current_status_of_the_site = forms.ChoiceField(label=_("Current site status (Work in progress, Work stopped, Work abandoned, Technical acceptance, Provisional acceptance, etc.)"), required=True)

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
                'subproject_sector': VAR_SUB_PROJECT_SECTORS,
                'type_of_subproject': VAR_TYPES_OF_SUB_PROJECT,
                'works_type': WORKS_TYPE_OF_SUB_PROJECT,
                'level_of_achievement_donation_certificate': LEVEL_OF_ACHIEVEMENT_DONATION_CERTIFICATE_OF_SUB_PROJECT,
                'current_status_of_the_site': CURRENT_STATUS_OF_THE_SITE
            }
            instance_datas = {
                'subproject_sector': self.instance.subproject_sector,
                'type_of_subproject': self.instance.type_of_subproject,
                'works_type': self.instance.works_type,
                'level_of_achievement_donation_certificate': self.instance.level_of_achievement_donation_certificate,
                'current_status_of_the_site': self.instance.current_status_of_the_site
            }
            if label in ('subproject_sector', 'type_of_subproject', 'works_type', \
                         'level_of_achievement_donation_certificate', 'current_status_of_the_site'):
                self.fields[label].choices = choices_datas[label]
                self.fields[label].widget.choices = choices_datas[label]
                if instance_datas[label]:
                    self.fields[label].initial = instance_datas[label]
            
            if label == "component":
                self.fields[label].queryset = Component.objects.filter(parent__name="Composante 1")

    class Meta:
        model = Subproject
        # fields = '__all__' # specify the fields to be displayed
        exclude = [
            'cvd', 'lot', 'has_latrine_blocs', 'number_of_latrine_blocks', 'has_fence', 
            'current_level_of_physical_realization_of_the_work_percent', 'current_level_of_physical_realization_of_the_work_wording'
        ] + FORM_FIELDS_TO_EXCLUDE


class SubprojectWithoutLinkHeavyObjectsForm(forms.ModelForm):
    subproject_sector = forms.ChoiceField(label=_("Subproject sector"), required=True)
    type_of_subproject = forms.ChoiceField(label=_("Type of subproject"), required=True)
    works_type = forms.ChoiceField(label=_("Works type"), required=True)
    level_of_achievement_donation_certificate = forms.ChoiceField(label=_("Level of donation certificate"), required=True)
    current_status_of_the_site = forms.ChoiceField(label=_("Current site status (Work in progress, Work stopped, Work abandoned, Technical acceptance, Provisional acceptance, etc.)"), required=True)

    def __init__(self, *args, **kwargs):
        super(SubprojectWithoutLinkHeavyObjectsForm, self).__init__(*args, **kwargs)
        for label, field in self.fields.items():
            self.fields[label].widget.attrs.update({'class' : 'form-control'})
            
            if "date" in label:
                self.fields[label].widget.attrs['class'] = 'form-control datetimepicker-input'
            
            choices_datas = {
                'subproject_sector': VAR_SUB_PROJECT_SECTORS,
                'type_of_subproject': VAR_TYPES_OF_SUB_PROJECT,
                'works_type': WORKS_TYPE_OF_SUB_PROJECT,
                'level_of_achievement_donation_certificate': LEVEL_OF_ACHIEVEMENT_DONATION_CERTIFICATE_OF_SUB_PROJECT,
                'current_status_of_the_site': CURRENT_STATUS_OF_THE_SITE
            }
            instance_datas = {
                'subproject_sector': self.instance.subproject_sector,
                'type_of_subproject': self.instance.type_of_subproject,
                'works_type': self.instance.works_type,
                'level_of_achievement_donation_certificate': self.instance.level_of_achievement_donation_certificate,
                'current_status_of_the_site': self.instance.current_status_of_the_site
            }
            if label in ('subproject_sector', 'type_of_subproject', 'works_type', \
                         'level_of_achievement_donation_certificate', 'current_status_of_the_site'):
                self.fields[label].choices = choices_datas[label]
                self.fields[label].widget.choices = choices_datas[label]
                if instance_datas[label]:
                    self.fields[label].initial = instance_datas[label]
            
            if label == "component":
                self.fields[label].queryset = Component.objects.filter(parent__name="Composante 1")

    class Meta:
        model = Subproject
        # fields = '__all__' # specify the fields to be displayed
        exclude = [
            'cvd', 'lot', 'has_latrine_blocs', 'number_of_latrine_blocks', 'has_fence', 
            'current_level_of_physical_realization_of_the_work_percent', 'current_level_of_physical_realization_of_the_work_wording',

            'location_subproject_realized', 'list_of_beneficiary_villages', 'canton', 'list_of_villages_crossed_by_the_track_or_electrification',
            'link_to_subproject'
        ] + FORM_FIELDS_TO_EXCLUDE


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
        # fields = '__all__' # specify the fields to be displayed
        exclude = [
            'current_level_of_physical_realization_of_the_work_percent', 'current_level_of_physical_realization_of_the_work_wording'
        ] + FORM_FIELDS_TO_EXCLUDE

#Add
class SubprojectAddStepForm(forms.ModelForm):
    begin = forms.DateField(
        label=_('Begin'), input_formats=['%d/%m/%Y'], help_text="DD/MM/YYYY", 
        required=True, initial=date.today,
    )
    # end = forms.DateField(label=_('End'), input_formats=['%d/%m/%Y'],
    #                                   help_text="DD/MM/YYYY", required=False)
    level_image = forms.FileField(label=_('Image of this level'), required=False)
    level_other_file = forms.FileField(label=_('Another file considered important at this level'), required=False)
    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial', {})
        self.subproject = initial.get('subproject')
        super().__init__(*args, **kwargs)
        for label, field in self.fields.items():
            if label in ("begin", "end"):
                self.fields[label].widget.attrs['class'] = 'form-control datetimepicker-input'

            if label == "step":
                if hasattr(self, 'instance') and self.instance and self.instance.pk:
                    self.fields[label].queryset = Step.objects.filter(id=self.instance.step.id)
                else:
                    
                    if self.subproject:
                        current_subproject_step = self.subproject.get_current_subproject_step
                        if current_subproject_step and current_subproject_step.step:
                            current_step = current_subproject_step.step
                            if current_step.next_steps.exists():
                                self.fields[label].queryset = current_step.next_steps.all().order_by("ranking")

                                if current_step.ranking == SELECTED_COMPANY_RANKING:
                                    first_contract = Step.objects.filter(ranking=FIRST_CONTRACT_RANKING).first()
                                    if self.subproject.check_step(first_contract):
                                        self.fields[label].queryset = self.fields[label].queryset.exclude(ranking=first_contract.ranking)
                                    else:
                                        self.fields[label].queryset = self.fields[label].queryset.exclude(ranking=OTHERS_CONTRACT_RANKING)
                                
                                if current_step.ranking == OTHERS_CONTRACT_RANKING:
                                    site_discount = Step.objects.filter(ranking=SITE_DISCOUNT_RANKING).first()
                                    if self.subproject.check_step(site_discount):
                                        self.fields[label].queryset = self.fields[label].queryset.exclude(ranking=site_discount.ranking)
                                    else:
                                        self.fields[label].queryset = self.fields[label].queryset.exclude(ranking=ANOTHER_SITE_HANDED_OVER_FOR_CONSTRUCTION_RANKING)
                                    
                                    another_site_discount = Step.objects.filter(ranking=ANOTHER_SITE_HANDED_OVER_FOR_CONSTRUCTION_RANKING).first()
                                    
                                    if not self.subproject.check_step(site_discount) and not self.subproject.check_step(another_site_discount):
                                        self.fields[label].queryset = self.fields[label].queryset.exclude(ranking__in=[IN_PROGRESS_RANKING, RESUME_IN_PROGRESS_RANKING])
                                    else:
                                        in_progress = Step.objects.filter(ranking=IN_PROGRESS_RANKING).first()
                                        if in_progress and self.subproject.check_step(in_progress):
                                            self.fields[label].queryset = self.fields[label].queryset.exclude(ranking=in_progress.ranking)
                                        else:
                                            self.fields[label].queryset = self.fields[label].queryset.exclude(ranking=RESUME_IN_PROGRESS_RANKING)
                                
                                if current_step.ranking == ANOTHER_SITE_HANDED_OVER_FOR_CONSTRUCTION_RANKING:
                                    in_progress = Step.objects.filter(ranking=IN_PROGRESS_RANKING).first()
                                    if in_progress and self.subproject.check_step(in_progress):
                                        self.fields[label].queryset = self.fields[label].queryset.exclude(ranking=in_progress.ranking)
                                    else:
                                        self.fields[label].queryset = self.fields[label].queryset.exclude(ranking=RESUME_IN_PROGRESS_RANKING)


                            else:
                                self.fields[label].queryset = Step.objects.none() # empty queryset
                        else:
                            self.fields[label].queryset = Step.objects.filter(wording__in=STRUCTURE_NOT_START_STATUS).order_by("ranking")
                    else:
                        self.fields[label].queryset = Step.objects.all().order_by("ranking")
    
    class Meta:
        model = SubprojectStep
        fields = (
            'step', 'begin', 'description', 
            'amount_spent_at_this_step', 'level_image', 'level_other_file'
        ) # specify the fields to be displayed
        exclude = [
            'end', 'total_amount_spent', 'current_level_of_physical_realization_of_the_work_percent', 'current_level_of_physical_realization_of_the_work_wording'
        ] + FORM_FIELDS_TO_EXCLUDE


class SubprojectAddLevelForm(forms.ModelForm):
    # max date
    begin = forms.DateField(
        label=_('Begin'), input_formats=['%d/%m/%Y'], help_text="DD/MM/YYYY", 
        required=True, initial=date.today
    )
    # end = forms.DateField(label=_('End'), input_formats=['%d/%m/%Y'],
    #                                   help_text="DD/MM/YYYY", required=False)
    level_image = forms.FileField(label=_('Image of this level'), required=False)
    level_other_file = forms.FileField(label=_('Another file considered important at this level'), required=False)
    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial', {})
        self.subproject = initial.get('subproject')
        super().__init__(*args, **kwargs)
        for label, field in self.fields.items():
            if label in ("begin", "end"):
                self.fields[label].widget.attrs['class'] = 'form-control datetimepicker-input'
            
            if label == "ranking":
                if hasattr(self, 'instance') and (not self.instance or (self.instance and not self.instance.pk)) and self.subproject:
                    current_level_object = self.subproject.get_current_level_object
                    if current_level_object and current_level_object.ranking is not None:
                        self.fields[label].initial = current_level_object.ranking + 1
                    else:
                        self.fields[label].initial = 0
                self.fields[label].widget.attrs['readonly'] = True

    
    class Meta:
        model = Level
        fields = (
            'wording', 'percent', 'ranking', 'begin', 'description', 
            'amount_spent_at_this_step', 'level_image', 'level_other_file'
        ) # specify the fields to be displayed
        exclude = [
            'end', 'total_amount_spent', 'current_level_of_physical_realization_of_the_work_percent', 'current_level_of_physical_realization_of_the_work_wording'
        ] + FORM_FIELDS_TO_EXCLUDE
#And Add



# #Delete
# class DeleteConfirmForm(forms.Form):
#     confirmation = forms.BooleanField(label=_('Please check this box and click the confirmation button for validation.'),
#                                        widget=forms.CheckboxInput, required=True)
    
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
# #And Delete


class SubprojectFilterForm(forms.Form):
    subproject_sectors = forms.MultipleChoiceField(required=False)
    subproject_types = forms.MultipleChoiceField(required=False)
    works_type_of_subproject = forms.MultipleChoiceField(required=False)
    subproject_step = forms.MultipleChoiceField(required=False)
    components = forms.MultipleChoiceField(required=False)

    def __init__(
            self, 
            has_all=True, 
            default_subproject_sectors=[], default_subproject_types=[], default_works_type_of_subproject=[],
            default_subproject_steps=[], default_components=[],
            *args, **kwargs
        ):
        super().__init__(*args, **kwargs)

        init_list = [('', ''), ('All', _('All'))] if has_all else []
        query_result_subproject_sectors = sorted(init_list + list(VAR_SUB_PROJECT_SECTORS))
        query_result_subproject_types = sorted(init_list + list(VAR_TYPES_OF_SUB_PROJECT))
        query_result_works_type_of_subproject = sorted(init_list + list(WORKS_TYPE_OF_SUB_PROJECT))
        query_result_subproject_step = init_list + list(SUB_PROJECT_STEP_STANDART)
        query_result_components = init_list + list(VAR_COMPONENTS)
        
        
        self.fields['subproject_sectors'].widget.choices = query_result_subproject_sectors
        self.fields['subproject_types'].widget.choices = query_result_subproject_types
        self.fields['works_type_of_subproject'].widget.choices = query_result_works_type_of_subproject
        self.fields['subproject_step'].widget.choices = query_result_subproject_step
        self.fields['components'].widget.choices = query_result_components

        if default_subproject_sectors:
            self.fields['subproject_sectors'].initial = default_subproject_sectors
        if default_subproject_types:
            self.fields['subproject_types'].initial = default_subproject_types
        if default_works_type_of_subproject:
            self.fields['works_type_of_subproject'].initial = default_works_type_of_subproject
        if default_subproject_steps:
            self.fields['subproject_step'].initial = default_subproject_steps
        if default_components:
            self.fields['components'].initial = default_components



class SearchForm(forms.Form):
    start_date = forms.DateTimeField(label=_('Start Date'), required=False)
    end_date = forms.DateTimeField(label=_('End Date'), required=False)

    def __init__(
            self, 
            default_start_date=None, default_end_date=None,
            *args, **kwargs
        ):
        super().__init__(*args, **kwargs)

        if default_start_date:
            self.fields['start_date'].initial = default_start_date
        if default_end_date:
            self.fields['end_date'].initial = default_end_date