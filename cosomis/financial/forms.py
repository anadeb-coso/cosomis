from django import forms
from django.utils.translation import gettext_lazy as _

from .models.allocation import AdministrativeLevelAllocation
from administrativelevels.models import AdministrativeLevel, CVD
from financial.models.financial import BankTransfer, DisbursementRequest, Disbursement
from cosomis import FORM_FIELDS_TO_EXCLUDE


class AdministrativeLevelAllocationForm(forms.ModelForm):
    def __init__(self, adl_type: str = None, *args, **kwargs):
        super(AdministrativeLevelAllocationForm, self).__init__(*args, **kwargs)
        instance = kwargs.get('instance')

        self.fields['administrative_level'].queryset = AdministrativeLevel.objects.none()
        self.fields['cvd'].queryset = CVD.objects.none()
        
        if adl_type:
            if adl_type == 'cvd':
                qs = CVD.objects.order_by('name')
                if instance and instance.cvd:
                    qs = CVD.objects.filter(pk=instance.cvd.pk) | qs

                self.fields['cvd'].queryset = qs.distinct()

                self.fields['cvd'].choices = [('', '---------')] + [
                    (o.id, f'{o.name} ({o.headquarters_village.parent.name})') for o in self.fields['cvd'].queryset
                ]
            else:
                qs = AdministrativeLevel.objects.filter(type=adl_type.capitalize()).order_by('name')
                
                if instance and instance.administrative_level:
                    qs = AdministrativeLevel.objects.filter(pk=instance.administrative_level.pk) | qs
                
                self.fields['administrative_level'].queryset = qs.distinct()

                self.fields['administrative_level'].choices = [('', '---------')] + [
                    (o.id, f'{o.name} ({o.type} {_("Of")} {o.parent if o.parent else "TOGO" })') for o in self.fields['administrative_level'].queryset
                ]
        
        # self.fields['administrative_level'].choices = [('', '---------')] + [
        #     (o.id, f'{o.name} ({o.type} {_("Of")} {o.parent if o.parent else "TOGO" })') for o in AdministrativeLevel.objects.filter().order_by('name')
        # ]

        # self.fields['cvd'].choices = [('', '---------')] + [
        #     (o.id, f'{o.name} ({o.headquarters_village.parent.name})') for o in CVD.objects.filter().order_by('name')
        # ]

    class Meta:
        model = AdministrativeLevelAllocation
        # fields = '__all__'
        exclude  = FORM_FIELDS_TO_EXCLUDE # specify the fields to be hid


    def clean(self):
        administrative_level = self.cleaned_data['administrative_level']
        cvd = self.cleaned_data['cvd']
        if cvd and administrative_level:
            raise forms.ValidationError(_("You must select either an administrative level or a CVD"))
        elif not cvd and not administrative_level:
            raise forms.ValidationError(_("You must choose an administrative level or a CVD"))
        return super().clean()


class BankTransferForm(forms.ModelForm):
    def __init__(self, adl_type: str = None, *args, **kwargs):
        super(BankTransferForm, self).__init__(*args, **kwargs)
        instance = kwargs.get('instance')

        self.fields['administrative_level'].queryset = AdministrativeLevel.objects.none()
        self.fields['cvd'].queryset = CVD.objects.none()
        
        if adl_type:
            if adl_type == 'cvd':
                qs = CVD.objects.order_by('name')
                if instance and instance.cvd:
                    qs = CVD.objects.filter(pk=instance.cvd.pk) | qs

                self.fields['cvd'].queryset = qs.distinct()

                self.fields['cvd'].choices = [('', '---------')] + [
                    (o.id, f'{o.name} ({o.headquarters_village.parent.name})') for o in self.fields['cvd'].queryset
                ]
            else:
                qs = AdministrativeLevel.objects.filter(type=adl_type.capitalize()).order_by('name')
                
                if instance and instance.administrative_level:
                    qs = AdministrativeLevel.objects.filter(pk=instance.administrative_level.pk) | qs
                
                self.fields['administrative_level'].queryset = qs.distinct()

                self.fields['administrative_level'].choices = [('', '---------')] + [
                    (o.id, f'{o.name} ({o.type} {_("Of")} {o.parent if o.parent else "TOGO" })') for o in self.fields['administrative_level'].queryset
                ]
        

    class Meta:
        model = BankTransfer
        # fields = '__all__'
        exclude  = FORM_FIELDS_TO_EXCLUDE # specify the fields to be hid
        
    def clean(self):
        administrative_level = self.cleaned_data['administrative_level']
        cvd = self.cleaned_data['cvd']
        if cvd and administrative_level:
            raise forms.ValidationError(_("You must select either an administrative level or a CVD"))
        elif not cvd and not administrative_level:
            raise forms.ValidationError(_("You must choose an administrative level or a CVD"))
        return super().clean()
    

class DisbursementRequestForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(DisbursementRequestForm, self).__init__(*args, **kwargs)

    class Meta:
        model = DisbursementRequest
        # fields = '__all__'
        exclude  = FORM_FIELDS_TO_EXCLUDE # specify the fields to be hid

class DisbursementRequestFormCreate(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(DisbursementRequestFormCreate, self).__init__(*args, **kwargs)

    class Meta:
        model = DisbursementRequest
        # fields = '__all__'
        exclude  = ['reply_date', 'comment_linked_to_reply'] + FORM_FIELDS_TO_EXCLUDE # specify the fields to be hid



class DisbursementForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(DisbursementForm, self).__init__(*args, **kwargs)

    class Meta:
        model = Disbursement
        # fields = '__all__'
        exclude  = FORM_FIELDS_TO_EXCLUDE # specify the fields to be hid

        