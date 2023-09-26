from django import forms
from django.utils.translation import gettext_lazy as _

from administrativelevels.models import AdministrativeLevel



class AdministrativeLevelFilterForm(forms.Form):
    region = forms.MultipleChoiceField()
    prefecture = forms.MultipleChoiceField()
    commune = forms.MultipleChoiceField()
    canton = forms.MultipleChoiceField()
    village = forms.MultipleChoiceField()

    def __init__(self, has_all=True, *args, **kwargs):
        super().__init__(*args, **kwargs)

        administrativelevels_docs = AdministrativeLevel.objects.all()
        init_list = [('', ''), ('All', _('All'))] if has_all else []
        query_result_regions = init_list + list(administrativelevels_docs.filter(type="Region").values_list('id', 'name'))
        query_result_prefectures = init_list + list(administrativelevels_docs.filter(type="Prefecture").values_list('id', 'name'))
        query_result_communes = init_list + list(administrativelevels_docs.filter(type="Commune").values_list('id', 'name'))
        query_result_cantons = init_list + list(administrativelevels_docs.filter(type="Canton").values_list('id', 'name'))
        query_result_villages = init_list + list(administrativelevels_docs.filter(type="Village").values_list('id', 'name'))
        
        
        self.fields['region'].widget.choices = query_result_regions
        self.fields['prefecture'].widget.choices = query_result_prefectures
        self.fields['commune'].widget.choices = query_result_communes
        self.fields['canton'].widget.choices = query_result_cantons
        self.fields['village'].widget.choices = query_result_villages