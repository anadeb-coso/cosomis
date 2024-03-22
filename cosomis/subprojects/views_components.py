from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext_lazy as _
from django.views import generic
from django.http import Http404

from subprojects.models import Subproject
from administrativelevels.views_components import AdministrativeLevelMixin


class SubprojectMixin:
    subproject = None
    canton_id = None

    def dispatch(self, request, pk: int, canton_id: int, *args, **kwargs):
        try:
            self.subproject = Subproject.objects.get(id=pk)
            self.canton_id = canton_id
        except Exception:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

class SubprojectCommonComponent(SubprojectMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'components/common_subprojects.html'
    context_object_name = 'datas'
    

    def get_results(self):
        subprojects = Subproject.objects.filter(full_title_of_approved_subproject=self.subproject.full_title_of_approved_subproject).get_actifs()
        return {
            "name": self.subproject.full_title_of_approved_subproject,
            'subprojects': subprojects,
            'canton_id': self.canton_id
        }
    
    def get_queryset(self):
        return self.get_results()


class SubprojectsByAdministrativeLevelMixin(AdministrativeLevelMixin):
    subprojects = []
    villages = []
    canton_id = None
    def dispatch(self, request, pk: int, *args, **kwargs):
        super().dispatch(request, pk, *args, **kwargs)
        self.subprojects = []
        self.villages = []
        if self.administrative_level.type == "Canton":
            self.villages = self.administrative_level.administrativelevel_set.get_queryset()
            self.subprojects = list(Subproject.objects.filter(canton_id=self.administrative_level.id).get_actifs())
            self.canton_id = self.administrative_level.id
        elif self.administrative_level.type == "Village":
            self.villages = [self.administrative_level]
            self.canton_id = self.administrative_level.parent.id
            
        for v in self.villages:
            self.subprojects += list(Subproject.objects.filter(location_subproject_realized_id=v.id).get_actifs())
            
        return super().dispatch(request, pk, *args, **kwargs)
    

class SubprojectsBySectorANdAdministrativeLevelComponent(SubprojectsByAdministrativeLevelMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'components/subprojects_by_sector.html'
    context_object_name = 'subprojects_by_sector'

    def get_results(self):
        
        length_subprojects = len(self.subprojects)
        subprojects_by_sector = {}
        
        for subp in self.subprojects:
            if not subprojects_by_sector.get(subp.subproject_sector):
                subprojects_by_sector[subp.subproject_sector] = {"number": 1, "percent": float("%.2f"%((1/length_subprojects)*100))}
            else:
                subprojects_by_sector[subp.subproject_sector]['number'] += 1
                subprojects_by_sector[subp.subproject_sector]['percent'] = float("%.2f"%((subprojects_by_sector[subp.subproject_sector]['number']/length_subprojects) * 100))

        return subprojects_by_sector
    
    def get_queryset(self):
        return self.get_results()
    

class SubprojectsByAdministrativeLevelComponent(SubprojectsByAdministrativeLevelMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'components/administrative_level_overview.html'
    context_object_name = 'datas'

    def get_results(self):
        return self.subprojects
    
    def get_queryset(self):
        return self.get_results()

    

class SummarySubprojectsByAdministrativeLevelComponent(SubprojectsByAdministrativeLevelMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'components/summary_suprojects_by_administrative_level.html'
    context_object_name = 'datas'

    def get_results(self):
        summary_subprojects = {}
        
        for subp in self.subprojects:
            if not summary_subprojects.get(subp.full_title_of_approved_subproject):
                summary_subprojects[subp.full_title_of_approved_subproject] = {
                    'beneficiaries': (subp.direct_beneficiaries_men if subp.direct_beneficiaries_men else 0) + \
                    (subp.direct_beneficiaries_women if subp.direct_beneficiaries_women else 0)+ \
                    (subp.indirect_beneficiaries_men if subp.indirect_beneficiaries_men else 0)+ \
                    (subp.indirect_beneficiaries_women if subp.indirect_beneficiaries_women else 0),
                    'cost_unit': subp.estimated_cost, 'cost_total': subp.estimated_cost if subp.estimated_cost else 0,
                    'pk': subp.pk, 'projects_ids': [o.id for o in subp.get_all_projects],
                    'financiers_ids': [o.id for o in subp.get_all_financiers]
                }
                if subp.canton:
                    summary_subprojects[subp.full_title_of_approved_subproject]['number_villages'] = (len(subp.list_of_villages_crossed_by_the_track_or_electrification.all()) if subp.list_of_villages_crossed_by_the_track_or_electrification else 0)
                else:
                    summary_subprojects[subp.full_title_of_approved_subproject]['cvds'] = [subp.cvd.id if subp.cvd else 0]
                    summary_subprojects[subp.full_title_of_approved_subproject]['number_villages'] = subp.location_subproject_realized.cvd.administrativelevel_set.get_queryset().count() if subp.location_subproject_realized.cvd else 0
            else:
                summary_subprojects[subp.full_title_of_approved_subproject]['beneficiaries'] += (subp.direct_beneficiaries_men if subp.direct_beneficiaries_men else 0) + \
                    (subp.direct_beneficiaries_women if subp.direct_beneficiaries_women else 0)+ \
                    (subp.indirect_beneficiaries_men if subp.indirect_beneficiaries_men else 0)+ \
                    (subp.indirect_beneficiaries_women if subp.indirect_beneficiaries_women else 0)
                summary_subprojects[subp.full_title_of_approved_subproject]['cost_total'] += subp.estimated_cost if subp.estimated_cost else 0
                summary_subprojects[subp.full_title_of_approved_subproject]['projects_ids'] = list(set(summary_subprojects[subp.full_title_of_approved_subproject]['projects_ids']+[o.id for o in subp.get_all_projects]))
                summary_subprojects[subp.full_title_of_approved_subproject]['financiers_ids'] = list(set(summary_subprojects[subp.full_title_of_approved_subproject]['financiers_ids']+[o.id for o in subp.get_all_financiers]))

                if subp.canton:
                    summary_subprojects[subp.full_title_of_approved_subproject]['number_villages'] += (len(subp.list_of_villages_crossed_by_the_track_or_electrification.all()) if subp.list_of_villages_crossed_by_the_track_or_electrification else 0)
                else:
                    summary_subprojects[subp.full_title_of_approved_subproject]['cvds'].append(subp.cvd.id if subp.cvd else 0)
                    summary_subprojects[subp.full_title_of_approved_subproject]['number_villages'] += (subp.location_subproject_realized.cvd.administrativelevel_set.get_queryset().count() if subp.location_subproject_realized.cvd else 0)
        
        return {
            "summary_subprojects": summary_subprojects,
            "canton_id": self.canton_id,
            "object": self.administrative_level
        }
    
    def get_queryset(self):
        return self.get_results()