from django import forms
from django.utils.translation import gettext_lazy as _

from administrativelevels.models import AdministrativeLevel



class AdministrativeLevelFilterForm(forms.Form):
    region = forms.MultipleChoiceField(required=False)
    prefecture = forms.MultipleChoiceField(required=False)
    commune = forms.MultipleChoiceField(required=False)
    canton = forms.MultipleChoiceField(required=False)
    village = forms.MultipleChoiceField(required=False)

    def __init__(
            self, 
            has_all=True, 
            regions=[], prefectures=[], communes=[], cantons=[], villages=[], 
            default_regions=[], default_prefectures=[], default_communes=[], default_cantons=[], default_villages=[], 
            *args, **kwargs
        ):
        super().__init__(*args, **kwargs)

        administrativelevels = AdministrativeLevel.objects.all()
        init_list = [('', ''), ('All', _('All'))] if has_all else []
        query_result_regions = init_list + list((regions if regions else administrativelevels.filter(type=AdministrativeLevel.REGION)).values_list('id', 'name'))
        query_result_prefectures = init_list + list((prefectures if prefectures else administrativelevels.filter(type=AdministrativeLevel.PREFECTURE)).values_list('id', 'name'))
        query_result_communes = init_list + list((communes if communes else administrativelevels.filter(type=AdministrativeLevel.COMMUNE)).values_list('id', 'name'))
        query_result_cantons = init_list + list((cantons if cantons else administrativelevels.filter(type=AdministrativeLevel.CANTON)).values_list('id', 'name'))
        query_result_villages = init_list + list((villages if villages else administrativelevels.filter(type=AdministrativeLevel.VILLAGE)).values_list('id', 'name'))
        
        
        self.fields['region'].widget.choices = query_result_regions
        self.fields['prefecture'].widget.choices = query_result_prefectures
        self.fields['commune'].widget.choices = query_result_communes
        self.fields['canton'].widget.choices = query_result_cantons
        self.fields['village'].widget.choices = query_result_villages

        if default_regions:
            self.fields['region'].initial = default_regions
        if default_prefectures:
            self.fields['prefecture'].initial = default_prefectures
        if default_communes:
            self.fields['commune'].initial = default_communes
        if default_cantons:
            self.fields['canton'].initial = default_cantons
        if default_villages:
            self.fields['village'].initial = default_villages