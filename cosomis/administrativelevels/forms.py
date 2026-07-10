from django import forms
from .models import GeographicalUnit, CVD, AdministrativeLevel
from django.core.exceptions import NON_FIELD_ERRORS
from cosomis import FORM_FIELDS_TO_EXCLUDE

class GeographicalUnitForm(forms.ModelForm):
    
    # cvds = forms.MultipleChoiceField(required=False, label="CVD")
    villages = forms.MultipleChoiceField(required=False, label="Villages")
    def __init__(self, *args, **kwargs):
        super(GeographicalUnitForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

        administrative_levels = AdministrativeLevel.objects.filter(type__in=["Canton", "Village"]).select_related('parent')
        cantons = [obj for obj in administrative_levels if obj.type == "Canton"]
        villages = [(obj.id, obj.name) for obj in administrative_levels if obj.type == "Village" and obj.parent]
        if "canton" in self.fields:
            self.fields["canton"].queryset = AdministrativeLevel.objects.filter(pk__in=[c.id for c in cantons])
        if "villages" in self.fields:
            self.fields["villages"].choices = villages

        # for label, field in self.fields.items():
        #     self.fields[label].widget.attrs.update({'class' : 'form-control'})
        #     if label == "canton":
        #         self.fields[label].queryset = AdministrativeLevel.objects.filter(type="Canton")
        # self.fields['villages'].choices = [(o.id, o.name) for o in AdministrativeLevel.objects.filter(type="Village") if o.parent]


        # d = {}

        # _cvds = CVD.objects.filter()
        # d['cvds'] = list(set([(obj.pk, obj.get_name()) for obj in _cvds if obj.administrativelevel_set.get_queryset()]))

        # for field_name, values in d.items():
        #     # self.fields[field_name].queryset = values
        #     self.fields[field_name].widget.choices = values
        #     self.fields[field_name].choices = values
        #     self.fields[field_name].widget.attrs['class'] += ' ' + field_name

    class Meta:
        model = GeographicalUnit
        exclude  = ['unique_code'] + FORM_FIELDS_TO_EXCLUDE # specify the fields to be hid
        error_messages = {
            NON_FIELD_ERRORS: {
                'unique_together': "Le numéro d'unité géographique doit être unique dans un canton.",
            }
        }

    

class CVDForm(forms.ModelForm):
    villages = forms.MultipleChoiceField(required=False, label="Villages")
    def __init__(self, *args, **kwargs):
        super(CVDForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
        
        relation_fields = ['headquarters_village']
        for field_name in relation_fields:
            if field_name in self.fields:
                if self.instance.pk:
                    instance_value = getattr(self.instance, field_name)
                    if instance_value:
                        self.fields[field_name].queryset = type(instance_value).objects.filter(pk=instance_value.pk)
                    else:
                        self.fields[field_name].queryset = self.fields[field_name].queryset.model.objects.none()
                else:
                    self.fields[field_name].queryset = self.fields[field_name].queryset.model.objects.none()
                
        if 'villages' in self.fields:
            self.fields['villages'].choices = [
                (o.id, o.name)
                for o in AdministrativeLevel.objects.filter(type="Village", parent__isnull=False)
            ]
        # for label, field in self.fields.items():
        #     self.fields[label].widget.attrs.update({'class' : 'form-control'})
        # self.fields['villages'].choices = [(o.id, o.name) for o in AdministrativeLevel.objects.filter(type="Village") if o.parent]

    class Meta:
        model = CVD
        exclude  = ['unique_code'] + FORM_FIELDS_TO_EXCLUDE # specify the fields to be hid

    def clean(self):
        villages = self.cleaned_data['villages']
        if not villages:
            raise forms.ValidationError("Au moins un village doit être sélectionné.")
        return super().clean()
    


class AdministrativeLevelForm(forms.ModelForm):
    def __init__(self, parent: str = None, *args, **kwargs):
        super(AdministrativeLevelForm, self).__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})

        if 'parent' in self.fields and parent:
            parent_field = self.fields['parent']
            parent_field.queryset = AdministrativeLevel.objects.filter(type=parent)
            parent_field.label = parent
            
        # for label, field in self.fields.items():
        #     self.fields[label].widget.attrs.update({'class' : 'form-control'})
        #     if label == "parent":
        #         self.fields[label].queryset = AdministrativeLevel.objects.filter(type=parent)
        #         self.fields[label].label = parent

    class Meta:
        model = AdministrativeLevel
        exclude  = ['no_sql_db_id'] + FORM_FIELDS_TO_EXCLUDE # specify the fields to be hid
