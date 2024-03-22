from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from cosomis.mixins import PageMixin, AJAXRequestMixin
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models import Sum, Max
from django.db import connection
import logging

from subprojects.models import Subproject, Step
from administrativelevels.models import AdministrativeLevel
from administrativelevels.functions import get_administrative_level_ids_descendants
from dashboard import forms
from dashboard import functions
from subprojects.forms import SubprojectFilterForm



class DashboardTemplateView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = 'display_grouped/display_grouped.html'
    active_level1 = 'subprojects'
    title = _("Grouped by sector")
    
    def get_context_data(self, **kwargs):
        ctx = super(DashboardTemplateView, self).get_context_data(**kwargs)
        ctx['hide_content_header'] = True
        ctx['form_adl'] = forms.AdministrativeLevelFilterForm()
        ctx['form_suproject'] = SubprojectFilterForm(False)
        return ctx


class DashboardSubprojectsMixin:

    table_class_style = 'table-striped table-secondary table-bordered'
    table_thead_class_style = 'bg-primary'

    def get_context_data(self, **kwargs):
        ctx = super(DashboardSubprojectsMixin, self).get_context_data(**kwargs)
        ctx.setdefault('table_class_style', self.table_class_style)
        ctx.setdefault('table_thead_class_style', self.table_thead_class_style)
        return ctx
    
    
    def filter_list_by_delete_empty(self, _list):
        if _list:
            return [elt for elt in _list if elt]
        else:
            return []
        
    def get_queryset(self):
        administrative_level_ids_get = self.request.GET.getlist('administrative_level_id[]', None)
        administrative_level_type = self.request.GET.get('administrative_level_type', 'All').title()
        subproject_sectors = self.filter_list_by_delete_empty(self.request.GET.getlist('id_subproject_sectors[]'))
        subproject_types = self.filter_list_by_delete_empty(self.request.GET.getlist('id_subproject_types[]'))
        works_type_of_subprojects = self.filter_list_by_delete_empty(self.request.GET.getlist('id_works_type_of_subproject[]'))
        subproject_steps = self.filter_list_by_delete_empty(self.request.GET.getlist('id_subproject_step[]'))
        
        administrative_level_type = "All" if administrative_level_type in ("", "null", "undefined") else administrative_level_type

        ald_filter_ids = []
        administrative_levels_ids = []
        if not administrative_level_ids_get:
            administrative_level_ids_get.append("")
        for ald_id in administrative_level_ids_get:
            ald_id = 0 if ald_id in ("", "null", "undefined", "All") else ald_id
            administrative_levels_ids += get_administrative_level_ids_descendants(
                ald_id, administrative_level_type, []
            )
            if ald_id:
                ald_filter_ids.append(ald_id)

        administrative_levels_ids = list(set(administrative_levels_ids))
        administrative_levels = AdministrativeLevel.objects.filter(id__in=administrative_levels_ids)
        if administrative_level_type == "All":
            administrative_levels = AdministrativeLevel.objects.filter(type="Region")
        elif ald_filter_ids and administrative_level_type != "All":
            administrative_levels = AdministrativeLevel.objects.filter(parent__id__in=ald_filter_ids)
        elif administrative_level_type:
            administrative_levels = AdministrativeLevel.objects.filter(parent__type=administrative_level_type)
        
        if not administrative_levels:
            administrative_levels = AdministrativeLevel.objects.filter(id__in=ald_filter_ids)

        # subprojects = Subproject.objects.filter().get_actifs()

        # if not ald_filter_ids:
        #     pass
        # else:
        #     subprojects = Subproject.objects.filter(
        #         Q(location_subproject_realized__id__in=administrative_levels_ids) | 
        #         Q(canton__id__in=administrative_levels_ids)
        #     ).get_actifs()

        adls = ald_filter_ids + administrative_levels_ids

        subprojects = Subproject.objects.filter(
            Q(location_subproject_realized__id__in=adls) | 
            Q(canton__id__in=adls)
        ).get_actifs()
        sectors = sorted(list(set(list(subprojects.values_list('subproject_sector')))))
        
        
        administrative_level = administrative_levels.first()


        if subproject_sectors:
            subprojects = subprojects.filter(subproject_sector__in=[elt for elt in subproject_sectors if elt])
        
        if subproject_types:
            subprojects = subprojects.filter(type_of_subproject__in=[elt for elt in subproject_types if elt])
            
        if works_type_of_subprojects:
            subprojects = subprojects.filter(works_type__in=[elt for elt in works_type_of_subprojects if elt])
        
        if subproject_steps:
            _subprojects = []
            for subproject in subprojects:
                subproject_step = subproject.current_status_of_the_site
                if subproject_step:
                    if 'not_started' in subproject_steps and subproject_step == "Identifié":
                        _subprojects.append(subproject)
                    if 'in_progress' in subproject_steps and subproject_step == "En cours":
                        _subprojects.append(subproject)
                    if 'completed' in subproject_steps and subproject_step in ("Achevé", \
                            "Réception technique", "Réception provisoire", "Réception définitive"):
                        _subprojects.append(subproject)

            subprojects = Subproject.objects.filter(id__in=[o.id for o in _subprojects]).get_actifs()

        return {
            'subprojects': subprojects,
            'sectors': [s[0] for s in sectors],
            'administrative_level_type': administrative_level.type if administrative_level else "",
            'columns_tuples': list(administrative_levels.filter(Q(type=administrative_level.type)if administrative_level else Q()).order_by('name').values_list('id', 'name')),
            'ald_filter_ids': ald_filter_ids,
            'administrative_levels_ids': administrative_levels_ids
        }
    






class DashboardSubprojectsDisplayGroupedBySectorsListView(DashboardSubprojectsMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'display_grouped/display_grouped_by_sector.html'
    context_object_name = 'queryset_results'
    table_class_style = 'table-bordered'

    def summary_subprojects_by_sectors_and_steps(self, all_subprojects, characters_length):
        datas = {
            
        }
        datas_on_liste = {
            
        }
        
        count = 0
        all_subprojects = all_subprojects.order_by('number', 'joint_subproject_number')
        
        for subproject in all_subprojects:
            if not datas.get(subproject.subproject_sector):
                datas[subproject.subproject_sector] = {
                    _("N°"): {},
                    _("Region"): {},
                    _("Commune"): {},
                    _("Sites"): {},
                    _("Structures"): {},
                    _("Type"): {},
                    _("Companies"): {},
                    _("Estimated cost") + " FCFA": {},
                    _("Amount FCFA TTC"): {},
                    _("Level of realization") + " %": {},
                    _("Physical level"): {},
                }
                datas_on_liste[subproject.subproject_sector] = []

            obj = {
                'number': None,
                'region': None,
                'commune': None,
                'sites': None,
                'type': None,
                'structures': None,
                'companies': None,
                'estimated_cost': None,
                'amount_ttc': None,
                'realization_level': None,
                'physical_level': None
            }
            datas[subproject.subproject_sector][_("N°")][count] = subproject.number
            obj['number'] = subproject.number
            canton = None
            try:
                canton = subproject.get_canton()
                datas[subproject.subproject_sector][_("Region")][count] = canton.parent.parent.parent.name if canton else "-"
                datas[subproject.subproject_sector][_("Commune")][count] = canton.parent.name if canton else "-"
            except:
                datas[subproject.subproject_sector][_("Region")][count] = "-"
                datas[subproject.subproject_sector][_("Commune")][count] = "-"
            obj['region'] = datas[subproject.subproject_sector][_("Region")][count]
            obj['commune'] = datas[subproject.subproject_sector][_("Commune")][count]

            village = subproject.get_village()
            datas[subproject.subproject_sector][_("Sites")][count] = village.name if village and village != "CCD" else (f'{canton.name} ({_("Canton")})' if village == "CCD" and canton else "-")
            obj['sites'] = datas[subproject.subproject_sector][_("Sites")][count]
            
            datas[subproject.subproject_sector][_("Structures")][count] = subproject.full_title_of_approved_subproject 
            # (
            #     subproject.full_title_of_approved_subproject \
            #         if subproject.subproject_type_designation != "Infrastructure" else \
            #         subproject.type_of_subproject
            # )
            obj['structures'] = datas[subproject.subproject_sector][_("Structures")][count]

            datas[subproject.subproject_sector][_("Type")][count] = subproject.type_of_subproject
            obj['type'] = subproject.type_of_subproject

            datas[subproject.subproject_sector][_("Companies")][count] = subproject.name_of_the_awarded_company_works_companies if subproject.name_of_the_awarded_company_works_companies else "-"
            obj['companies'] = datas[subproject.subproject_sector][_("Companies")][count]
            
            datas[subproject.subproject_sector][_("Estimated cost") + " FCFA"][count] = subproject.estimated_cost if subproject.estimated_cost else 0
            obj['estimated_cost'] = datas[subproject.subproject_sector][_("Estimated cost") + " FCFA"][count]
            
            datas[subproject.subproject_sector][_("Amount FCFA TTC")][count] = subproject.exact_amount_spent if subproject.exact_amount_spent else 0
            obj['amount_ttc'] = datas[subproject.subproject_sector][_("Amount FCFA TTC")][count]

            step_level = subproject.get_current_subproject_step_and_level_object
            
            datas[subproject.subproject_sector][_("Level of realization") + " %"][count] = step_level.percent if step_level and step_level.percent else 0 #str(int(step_level.percent)).rjust(characters_length,'0') if step_level and step_level.percent else 0
            obj['realization_level'] = datas[subproject.subproject_sector][_("Level of realization") + " %"][count]
            
            datas[subproject.subproject_sector][_("Physical level")][count] = subproject.get_current_subproject_step_and_level_without_percent
            obj['physical_level'] = datas[subproject.subproject_sector][_("Physical level")][count]


            count += 1

            datas[subproject.subproject_sector][_("N°")][count] = _("Total")

            datas_on_liste[subproject.subproject_sector].append(obj)

        # All sum
        columns_skip = [
            _("N°"),
            _("Region"),
            _("Commune"),
            _("Sites"),
            _("Structures"),
            _("Type"),
            _("Companies"),
            _("Level of realization") + " %",
            _("Physical level")
        ]
        
        for k_data, v_data in datas.items():
            for _k in v_data.keys():
                _sum = 0
                if _k not in columns_skip:
                    _sum = functions.sum_dict_value(v_data[_k], len(v_data[_k]))
                if _sum:
                    datas[k_data][_k][len(datas[k_data][_k].values())] = _sum #str(_sum).rjust(characters_length,'0')
        # End All sum

        return {
            'title': _("Grouped by sector"),
            'datas': datas,
            'data_id': 'datas_grouped_by_sector',
            'datas_on_liste': datas_on_liste,
            'datas_headers': [
                    _("N°"),
                    _("Region"),
                    _("Commune"),
                    _("Sites"),
                    _("Structures"),
                    _("Type"),
                    _("Companies"),
                    _("Estimated cost") + " FCFA",
                    _("Amount FCFA TTC"),
                    _("Level of realization") + " %",
                    _("Physical level"),
            ]
        }


    def get_context_data(self, **kwargs):
        ctx = super(DashboardSubprojectsDisplayGroupedBySectorsListView, self).get_context_data(**kwargs)
        # adls = ctx['queryset_results']['ald_filter_ids'] + ctx['queryset_results']['administrative_levels_ids']
        # all_subprojects = Subproject.objects.filter(
        #         Q(location_subproject_realized__id__in=adls) | 
        #         Q(canton__id__in=adls)
        #     ).get_actifs()
        
        all_subprojects = ctx['queryset_results']['subprojects']
        
       
        characters_length = 3
        for k, v in self.summary_subprojects_by_sectors_and_steps(all_subprojects, characters_length).items():
            ctx[k] = v

        # ctx["queryset_results"]["administrative_level_type"] = None
        # ctx['not_allow_datatable_auto_width'] = True
        ctx['subprojects_number'] = all_subprojects.count()

        return ctx




class DashboardSubprojectsDisplayGroupedBySectorsListSubView(DashboardSubprojectsMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'display_grouped/display_grouped_by_sector_sub.html'
    context_object_name = 'queryset_results'
    table_class_style = 'table-bordered'

    def summary_subprojects_by_sectors_and_steps(self, all_subprojects, characters_length):
        datas = {
            
        }
        datas_on_liste = {
            
        }
        
        count = 0
        all_subprojects = all_subprojects.order_by('number', 'joint_subproject_number')
        
        for subproject in all_subprojects:
            if not datas.get(subproject.subproject_sector):
                datas[subproject.subproject_sector] = {
                    _("N°"): {},
                    _("Region"): {},
                    _("Commune"): {},
                    _("Sites"): {},
                    _("Structures"): {},
                    _("Type"): {},
                    _("Companies"): {},
                    _("Estimated cost") + " FCFA": {},
                    _("Amount FCFA TTC"): {},
                    _("Level of realization") + " %": {},
                    _("Physical level"): {},
                }
                datas_on_liste[subproject.subproject_sector] = []

            obj = {
                'number': None,
                'region': None,
                'commune': None,
                'sites': None,
                'structures': None,
                'type': None,
                'companies': None,
                'estimated_cost': None,
                'amount_ttc': None,
                'realization_level': None,
                'physical_level': None
            }
            datas[subproject.subproject_sector][_("N°")][count] = subproject.number
            obj['number'] = subproject.number
            canton = None
            try:
                canton = subproject.get_canton()
                datas[subproject.subproject_sector][_("Region")][count] = canton.parent.parent.parent.name if canton else "-"
                datas[subproject.subproject_sector][_("Commune")][count] = canton.parent.name if canton else "-"
            except:
                datas[subproject.subproject_sector][_("Region")][count] = "-"
                datas[subproject.subproject_sector][_("Commune")][count] = "-"
            obj['region'] = datas[subproject.subproject_sector][_("Region")][count]
            obj['commune'] = datas[subproject.subproject_sector][_("Commune")][count]

            village = subproject.get_village()
            datas[subproject.subproject_sector][_("Sites")][count] = village.name if village and village != "CCD" else (f'{canton.name} ({_("Canton")})' if village == "CCD" and canton else "-")
            obj['sites'] = datas[subproject.subproject_sector][_("Sites")][count]

            datas[subproject.subproject_sector][_("Structures")][count] = subproject.full_title_of_approved_subproject
            # (
            #     subproject.full_title_of_approved_subproject \
            #         if subproject.subproject_type_designation != "Infrastructure" else \
            #         subproject.type_of_subproject
            # )
            obj['structures'] = datas[subproject.subproject_sector][_("Structures")][count]

            datas[subproject.subproject_sector][_("Type")][count] = subproject.type_of_subproject
            obj['type'] = subproject.type_of_subproject

            datas[subproject.subproject_sector][_("Companies")][count] = subproject.name_of_the_awarded_company_works_companies if subproject.name_of_the_awarded_company_works_companies else "-"
            obj['companies'] = datas[subproject.subproject_sector][_("Companies")][count]
            
            datas[subproject.subproject_sector][_("Estimated cost") + " FCFA"][count] = subproject.estimated_cost if subproject.estimated_cost else 0
            obj['estimated_cost'] = datas[subproject.subproject_sector][_("Estimated cost") + " FCFA"][count]
            
            datas[subproject.subproject_sector][_("Amount FCFA TTC")][count] = subproject.exact_amount_spent if subproject.exact_amount_spent else 0
            obj['amount_ttc'] = datas[subproject.subproject_sector][_("Amount FCFA TTC")][count]

            step_level = subproject.get_current_subproject_step_and_level_object
            
            datas[subproject.subproject_sector][_("Level of realization") + " %"][count] = step_level.percent if step_level and step_level.percent else 0 #str(int(step_level.percent)).rjust(characters_length,'0') if step_level and step_level.percent else 0
            obj['realization_level'] = datas[subproject.subproject_sector][_("Level of realization") + " %"][count]
            
            datas[subproject.subproject_sector][_("Physical level")][count] = subproject.get_current_subproject_step_and_level_without_percent
            obj['physical_level'] = datas[subproject.subproject_sector][_("Physical level")][count]


            count += 1

            datas[subproject.subproject_sector][_("N°")][count] = _("Total")

            datas_on_liste[subproject.subproject_sector].append(obj)

        # All sum
        columns_skip = [
            _("N°"),
            _("Region"),
            _("Commune"),
            _("Sites"),
            _("Structures"),
            _("Type"),
            _("Companies"),
            _("Level of realization") + " %",
            _("Physical level")
        ]
        
        for k_data, v_data in datas.items():
            for _k in v_data.keys():
                _sum = 0
                if _k not in columns_skip:
                    _sum = functions.sum_dict_value(v_data[_k], len(v_data[_k]))
                if _sum:
                    datas[k_data][_k][len(datas[k_data][_k].values())] = _sum #str(_sum).rjust(characters_length,'0')
        # End All sum

        return {
            'title': _("Grouped by sector"),
            'datas': datas,
            'data_id': 'datas_grouped_by_sub_sector',
            'datas_on_liste': datas_on_liste,
            'datas_headers': [
                    _("N°"),
                    _("Region"),
                    _("Commune"),
                    _("Sites"),
                    _("Structures"),
                    _("Type"),
                    _("Companies"),
                    _("Estimated cost") + " FCFA",
                    _("Amount FCFA TTC"),
                    _("Level of realization") + " %",
                    _("Physical level"),
            ]
        }


    def get_context_data(self, **kwargs):
        ctx = super(DashboardSubprojectsDisplayGroupedBySectorsListSubView, self).get_context_data(**kwargs)
        # adls = ctx['queryset_results']['ald_filter_ids'] + ctx['queryset_results']['administrative_levels_ids']
        # all_subprojects = Subproject.objects.filter(
        #         Q(location_subproject_realized__id__in=adls) | 
        #         Q(canton__id__in=adls)
        #     ).get_actifs()
        
        all_subprojects = ctx['queryset_results']['subprojects']
        
       
        characters_length = 3
        for k, v in self.summary_subprojects_by_sectors_and_steps(all_subprojects, characters_length).items():
            ctx[k] = v

        # ctx["queryset_results"]["administrative_level_type"] = None
        # ctx['not_allow_datatable_auto_width'] = True
        ctx['subprojects_number'] = all_subprojects.count()

        return ctx



class DashboardSubprojectsDisplayGroupedByTypeListSubView(DashboardSubprojectsMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'display_grouped/display_grouped_by_type_sub.html'
    context_object_name = 'queryset_results'
    table_class_style = 'table-bordered'

    def summary_subprojects_by_sectors_and_steps(self, all_subprojects, characters_length):
        datas = {
            
        }
        datas_on_liste = {
            
        }
        
        count = 0
        all_subprojects = all_subprojects.order_by('number', 'joint_subproject_number')
        
        for subproject in all_subprojects:
            if not datas.get(subproject.type_of_subproject):
                datas[subproject.type_of_subproject] = {
                    _("N°"): {},
                    _("Region"): {},
                    _("Commune"): {},
                    _("Sites"): {},
                    _("Structures"): {},
                    _("Type"): {},
                    _("Companies"): {},
                    _("Estimated cost") + " FCFA": {},
                    _("Amount FCFA TTC"): {},
                    _("Level of realization") + " %": {},
                    _("Physical level"): {},
                }
                datas_on_liste[subproject.type_of_subproject] = []

            obj = {
                'number': None,
                'region': None,
                'commune': None,
                'sites': None,
                'structures': None,
                'type': None,
                'companies': None,
                'estimated_cost': None,
                'amount_ttc': None,
                'realization_level': None,
                'physical_level': None
            }
            datas[subproject.type_of_subproject][_("N°")][count] = subproject.number
            obj['number'] = subproject.number
            canton = None
            try:
                canton = subproject.get_canton()
                datas[subproject.type_of_subproject][_("Region")][count] = canton.parent.parent.parent.name if canton else "-"
                datas[subproject.type_of_subproject][_("Commune")][count] = canton.parent.name if canton else "-"
            except:
                datas[subproject.type_of_subproject][_("Region")][count] = "-"
                datas[subproject.type_of_subproject][_("Commune")][count] = "-"
            obj['region'] = datas[subproject.type_of_subproject][_("Region")][count]
            obj['commune'] = datas[subproject.type_of_subproject][_("Commune")][count]

            village = subproject.get_village()
            datas[subproject.type_of_subproject][_("Sites")][count] = village.name if village and village != "CCD" else (f'{canton.name} ({_("Canton")})' if village == "CCD" and canton else "-")
            obj['sites'] = datas[subproject.type_of_subproject][_("Sites")][count]

            datas[subproject.type_of_subproject][_("Structures")][count] = subproject.full_title_of_approved_subproject
            # (
            #     subproject.full_title_of_approved_subproject \
            #         if subproject.subproject_type_designation != "Infrastructure" else \
            #         subproject.type_of_subproject
            # )
            obj['structures'] = datas[subproject.type_of_subproject][_("Structures")][count]

            datas[subproject.type_of_subproject][_("Type")][count] = subproject.type_of_subproject
            obj['type'] = datas[subproject.type_of_subproject][_("Type")][count]

            datas[subproject.type_of_subproject][_("Companies")][count] = subproject.name_of_the_awarded_company_works_companies if subproject.name_of_the_awarded_company_works_companies else "-"
            obj['companies'] = datas[subproject.type_of_subproject][_("Companies")][count]
            
            datas[subproject.type_of_subproject][_("Estimated cost") + " FCFA"][count] = subproject.estimated_cost if subproject.estimated_cost else 0
            obj['estimated_cost'] = datas[subproject.type_of_subproject][_("Estimated cost") + " FCFA"][count]
            
            datas[subproject.type_of_subproject][_("Amount FCFA TTC")][count] = subproject.exact_amount_spent if subproject.exact_amount_spent else 0
            obj['amount_ttc'] = datas[subproject.type_of_subproject][_("Amount FCFA TTC")][count]

            step_level = subproject.get_current_subproject_step_and_level_object
            
            datas[subproject.type_of_subproject][_("Level of realization") + " %"][count] = step_level.percent if step_level and step_level.percent else 0 #str(int(step_level.percent)).rjust(characters_length,'0') if step_level and step_level.percent else 0
            obj['realization_level'] = datas[subproject.type_of_subproject][_("Level of realization") + " %"][count]
            
            datas[subproject.type_of_subproject][_("Physical level")][count] = subproject.get_current_subproject_step_and_level_without_percent
            obj['physical_level'] = datas[subproject.type_of_subproject][_("Physical level")][count]


            count += 1

            datas[subproject.type_of_subproject][_("N°")][count] = _("Total")

            datas_on_liste[subproject.type_of_subproject].append(obj)

        # All sum
        columns_skip = [
            _("N°"),
            _("Region"),
            _("Commune"),
            _("Sites"),
            _("Structures"),
            _("Type"),
            _("Companies"),
            _("Level of realization") + " %",
            _("Physical level")
        ]
        
        for k_data, v_data in datas.items():
            for _k in v_data.keys():
                _sum = 0
                if _k not in columns_skip:
                    _sum = functions.sum_dict_value(v_data[_k], len(v_data[_k]))
                if _sum:
                    datas[k_data][_k][len(datas[k_data][_k].values())] = _sum #str(_sum).rjust(characters_length,'0')
        # End All sum

        return {
            'title': _("Grouped by sector"),
            'datas': datas,
            'data_id': 'datas_grouped_by_sub_sector',
            'datas_on_liste': datas_on_liste,
            'datas_headers': [
                    _("N°"),
                    _("Region"),
                    _("Commune"),
                    _("Sites"),
                    _("Structures"),
                    _("Companies"),
                    _("Estimated cost") + " FCFA",
                    _("Amount FCFA TTC"),
                    _("Level of realization") + " %",
                    _("Physical level"),
            ]
        }


    def get_context_data(self, **kwargs):
        ctx = super(DashboardSubprojectsDisplayGroupedByTypeListSubView, self).get_context_data(**kwargs)
        
        all_subprojects = ctx['queryset_results']['subprojects']
        
       
        characters_length = 3
        for k, v in self.summary_subprojects_by_sectors_and_steps(all_subprojects, characters_length).items():
            ctx[k] = v

        ctx['subprojects_number'] = all_subprojects.count()

        return ctx
    