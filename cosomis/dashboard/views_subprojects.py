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
from . import forms
from . import functions



class DashboardTemplateView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = 'dashboard_subprojects.html'
    active_level1 = 'dashboard_subprojects'
    title = _('Subprojects Dashboard')
    
    def get_context_data(self, **kwargs):
        ctx = super(DashboardTemplateView, self).get_context_data(**kwargs)
        ctx['hide_content_header'] = True
        ctx['form_adl'] = forms.AdministrativeLevelFilterForm()
        return ctx


class DashboardSubprojectsMixin:

    table_class_style = 'table-striped table-secondary table-bordered'
    table_thead_class_style = 'bg-primary'

    def get_context_data(self, **kwargs):
        ctx = super(DashboardSubprojectsMixin, self).get_context_data(**kwargs)
        ctx.setdefault('table_class_style', self.table_class_style)
        ctx.setdefault('table_thead_class_style', self.table_thead_class_style)
        return ctx
    
    def get_queryset(self):
        administrative_level_ids_get = self.request.GET.getlist('administrative_level_id[]', None)
        administrative_level_type = self.request.GET.get('administrative_level_type', 'All').title()
        
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

        subprojects = Subproject.objects.filter()

        sectors = sorted(list(set(list(subprojects.values_list('subproject_sector')))))
        
        if not ald_filter_ids:
            pass
        else:
            subprojects = Subproject.objects.filter(
                Q(location_subproject_realized__id__in=administrative_levels_ids) | 
                Q(canton__id__in=administrative_levels_ids)
            )
        administrative_level = administrative_levels.first()

        
        return {
            'subprojects': subprojects,
            'sectors': [s[0] for s in sectors],
            'administrative_level_type': administrative_level.type if administrative_level else "",
            'columns_tuples': list(administrative_levels.filter(Q(type=administrative_level.type)if administrative_level else Q()).order_by('name').values_list('id', 'name')),
            'ald_filter_ids': ald_filter_ids,
            'administrative_levels_ids': administrative_levels_ids
        }
    

class DashboardSubprojectsListView(DashboardSubprojectsMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'tracking.html'
    context_object_name = 'queryset_results'
    
    def summary_subprojects_by_sectors_1(self, columns_listes, sectors, all_subprojects, characters_length):
        datas = {
            _("Sectors"): {},
            _("Type"): {}
        }
        for column in columns_listes:
            datas[column[1]] = {}
            
        datas[_("Total")] = {}
        # datas[_("OBSERVATIONS")] = {}

        count = 0
        number_toal = 0
        _sectors = []
        for s in sectors:
            _sectors.append(s)
            _sectors.append(s)
            
        for i in range(len(_sectors)):
            datas[_("Sectors")][count] = _sectors[i]
            if (i+1)%2 == 0:
                datas[_("Type")][count] = _("Number of subproject infrastructures")
            else:
                datas[_("Type")][count] = _("Number of subprojects")

            number_toal = 0
            for column in columns_listes:
                # number = all_subprojects.filter(
                #     Q(location_subproject_realized__id__in=column[2]) | 
                #     Q(canton__id__in=column[2]),
                #     subproject_sector=_sectors[i], subproject_type_designation__in=(["Infrastructure", "Subproject"] if (i+1)%2 == 0 else ["Subproject"])
                # ).count()
                
                # datas[column[1]][count] = number #str(number).rjust(characters_length,'0')
                # number_toal += number
                number = 0
                for _subp in all_subprojects:
                    if (_subp.location_subproject_realized_id in column[2] or \
                        _subp.canton_id in column[2]) and _subp.subproject_sector == _sectors[i] and \
                        _subp.subproject_type_designation in (["Infrastructure", "Subproject"] if (i+1)%2 == 0 else ["Subproject"]):
                        number += 1
                
                datas[column[1]][count] = number
                number_toal += number

            datas[_("Total")][count] = number_toal #str(number_toal).rjust(characters_length,'0')
            count += 1

        datas[_("Sectors")][count] = _("Total")
        datas[_("Sectors")][count+1] = _("Total")
        datas[_("Sectors")][count+2] = _("Total")
        datas[_("Type")][count] = _("Number of subprojects")
        datas[_("Type")][count+1] = _("Number of subproject infrastructures")
        datas[_("Type")][count+2] = _("All")

        # All sum
        columns_skip = [
            _("Sectors"),
            _("Type"),
            # _("OBSERVATIONS")
        ]
        for i in range(3):
            for k_data in datas.keys():
                _sum = 0
                if k_data not in columns_skip:
                    _sum = functions.sum_dict_value(datas[k_data], count, pair=bool(i) if i < 2 else True)
                if _sum:
                    datas[k_data][count+i] = _sum #str(_sum).rjust(characters_length,'0')
        # End All sum

        return {
            'title': _("Number of sub-projects by administrative level and sector"),
            'datas': datas,
            'length_loop': range(0, count+3),
            'values': list(datas.values())
        }



    def get_context_data(self, **kwargs):
        ctx = super(DashboardSubprojectsListView, self).get_context_data(**kwargs)
        # subprojects = ctx['queryset_results']['subprojects']
        sectors = ctx['queryset_results']['sectors']
        columns_tuples = ctx['queryset_results']['columns_tuples']
        columns_listes = []
        for column in columns_tuples:
            ids_descendants = get_administrative_level_ids_descendants(column[0], None, [])
            columns_listes.append(
                [
                    column[0],
                    column[1],
                    [column[0]] + ids_descendants if column[0] != "All" else ids_descendants
                ]
            )
        all_subprojects = ctx['queryset_results']['subprojects']
        # all_steps = Step.objects.all().order_by('-ranking')

        ctx["summary"] = {}

        characters_length = 0 #len(str(all_subprojects.count()))
        ctx["summary"]["summary_subprojects_by_sectors_1"] = {}
        for k, v in self.summary_subprojects_by_sectors_1(columns_listes, sectors, all_subprojects, characters_length).items():
            ctx["summary"]["summary_subprojects_by_sectors_1"][k] = v
        
        return ctx
    



class DashboardSubprojectsBySectorAmountListView(DashboardSubprojectsMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'tracking.html'
    context_object_name = 'queryset_results'

    def summary_amount_subprojects_by_sectors_1(self, columns_listes, sectors, all_subprojects, characters_length):
        datas = {
            _("Sectors"): {},
            _("Number of subprojects"): {},
            _("Number of subproject infrastructures"): {}
        }
        for column in columns_listes:
            datas[column[1]] = {}
            
        datas[_("Total")] = {}
        # datas[_("OBSERVATIONS")] = {}

        count = 0
        _sectors = sectors
            
        for i in range(len(_sectors)):
            datas[_("Sectors")][count] = _sectors[i]

            subprojects_filter = all_subprojects.filter(subproject_sector=_sectors[i])
            datas[_("Number of subprojects")][count] = subprojects_filter.filter(
                subproject_type_designation="Subproject"
            ).count()
            
            subprojects_filter_infras = all_subprojects.filter(
                subproject_sector=_sectors[i], subproject_type_designation__in=["Infrastructure", "Subproject"]
            )
            datas[_("Number of subproject infrastructures")][count] = subprojects_filter_infras.count()

            toal_mount = 0
            for column in columns_listes:
                # estimated_cost = subprojects_filter_infras.filter(
                #     Q(location_subproject_realized__id__in=column[2]) | 
                #     Q(canton__id__in=column[2])
                # ).aggregate(Sum('estimated_cost'))['estimated_cost__sum']
                # estimated_cost = estimated_cost if estimated_cost else 0

                estimated_cost = 0
                for _subp_structure in subprojects_filter_infras:
                    if (_subp_structure.location_subproject_realized_id in column[2] or \
                        _subp_structure.canton_id in column[2]):
                        estimated_cost += _subp_structure.estimated_cost

                
                datas[column[1]][count] = estimated_cost #str(estimated_cost).rjust(characters_length,'0')
                toal_mount += estimated_cost

            datas[_("Total")][count] = toal_mount #str(toal_mount).rjust(characters_length,'0')
            count += 1

        datas[_("Sectors")][count] = _("Total")

        # All sum
        columns_skip = [
            _("Sectors"),
            # _("OBSERVATIONS")
        ]
        for k_data in datas.keys():
            _sum = 0
            if k_data not in columns_skip:
                _sum = functions.sum_dict_value(datas[k_data], count)
            if _sum:
                datas[k_data][count] = _sum #str(_sum).rjust(characters_length,'0')
        # End All sum

        return {
            'title': _("Amount of sub-projects by administrative level and sector"),
            'datas': datas,
            'length_loop': range(0, count+1),
            'values': list(datas.values())
        }


    def get_context_data(self, **kwargs):
        ctx = super(DashboardSubprojectsBySectorAmountListView, self).get_context_data(**kwargs)
        # subprojects = ctx['queryset_results']['subprojects']
        sectors = ctx['queryset_results']['sectors']
        columns_tuples = ctx['queryset_results']['columns_tuples']
        columns_listes = []
        for column in columns_tuples:
            ids_descendants = get_administrative_level_ids_descendants(column[0], None, [])
            columns_listes.append(
                [
                    column[0],
                    column[1],
                    [column[0]] + ids_descendants if column[0] != "All" else ids_descendants
                ]
            )
        all_subprojects = ctx['queryset_results']['subprojects']
        all_steps = Step.objects.all().order_by('-ranking')

        ctx["summary"] = {}
        
        characters_length = 0 #len(str(all_subprojects.aggregate(Sum('estimated_cost'))['estimated_cost__sum']))
        ctx["summary"]["summary_amount_subprojects_by_sectors_1"] = {}
        for k, v in self.summary_amount_subprojects_by_sectors_1(columns_listes, sectors, all_subprojects, characters_length).items():
            ctx["summary"]["summary_amount_subprojects_by_sectors_1"][k] = v

        return ctx
    




class DashboardSubprojectsSectorsAndStepsListView(DashboardSubprojectsMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'tracking.html'
    context_object_name = 'queryset_results'
    table_class_style = 'table-bordered'

    def summary_subprojects_by_sectors_and_steps(self, all_subprojects, characters_length):
        datas = {
            _("N°"): {},
            _("Region"): {},
            _("Sites"): {},
            _("Structures"): {},
            _("Companies"): {},
            _("Estimated cost") + " FCFA": {},
            _("Amount FCFA TTC"): {},
            _("Level of realization") + " %": {},
            _("Physical level"): {},
        }
        
        count = 0
        all_subprojects = all_subprojects.order_by('number', 'joint_subproject_number')
        
        for subproject in all_subprojects:
            datas[_("N°")][count] = subproject.number
            canton = None
            try:
                canton = subproject.get_canton()
                datas[_("Region")][count] = canton.parent.parent.parent.name if canton else "-"
            except:
                datas[_("Region")][count] = "-"
            
            village = subproject.get_village()
            datas[_("Sites")][count] = village.name if village and village != "CCD" else (f'{canton.name} ({_("Canton")})' if village == "CCD" and canton else "-")

            datas[_("Structures")][count] = (
                subproject.full_title_of_approved_subproject \
                    if subproject.subproject_type_designation != "Infrastructure" else \
                    subproject.type_of_subproject
            )
            datas[_("Companies")][count] = subproject.name_of_the_awarded_company_works_companies if subproject.name_of_the_awarded_company_works_companies else "-"
            datas[_("Estimated cost") + " FCFA"][count] = subproject.estimated_cost if subproject.estimated_cost else 0
            datas[_("Amount FCFA TTC")][count] = subproject.exact_amount_spent if subproject.exact_amount_spent else 0
            
            step_level = subproject.get_current_subproject_step_and_level_object
            
            datas[_("Level of realization") + " %"][count] = step_level.percent if step_level and step_level.percent else 0 #str(int(step_level.percent)).rjust(characters_length,'0') if step_level and step_level.percent else 0
            datas[_("Physical level")][count] = subproject.get_current_subproject_step_and_level_without_percent

            count += 1

        datas[_("N°")][count] = _("Total")

        # All sum
        columns_skip = [
            _("N°"),
            _("Region"),
            _("Sites"),
            _("Structures"),
            _("Companies"),
            _("Level of realization") + " %",
            _("Physical level")
        ]
        for k_data in datas.keys():
            _sum = 0
            if k_data not in columns_skip:
                _sum = functions.sum_dict_value(datas[k_data], count)
            if _sum:
                datas[k_data][count] = _sum #str(_sum).rjust(characters_length,'0')
        # End All sum

        return {
            'title': _("Subprojects by village, sector and step"),
            'datas': datas,
            'length_loop': range(0, count+1),
            'values': list(datas.values())
        }


    def get_context_data(self, **kwargs):
        ctx = super(DashboardSubprojectsSectorsAndStepsListView, self).get_context_data(**kwargs)
        adls = ctx['queryset_results']['ald_filter_ids'] + ctx['queryset_results']['administrative_levels_ids']
        all_subprojects = Subproject.objects.filter(
                Q(location_subproject_realized__id__in=adls) | 
                Q(canton__id__in=adls)
            )
        
        # all_subprojects = ctx['queryset_results']['subprojects']
        
        ctx["summary"] = {}

        characters_length = 3
        ctx["summary"]["summary_subprojects_by_sectors_and_steps"] = {}
        for k, v in self.summary_subprojects_by_sectors_and_steps(all_subprojects, characters_length).items():
            ctx["summary"]["summary_subprojects_by_sectors_and_steps"][k] = v

        ctx["queryset_results"]["administrative_level_type"] = None
        ctx['not_allow_datatable_auto_width'] = True
        return ctx
    


class DashboardSubprojectsStepsAlreadyTrackListView(DashboardSubprojectsMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'tracking.html'
    context_object_name = 'queryset_results'
    table_class_style = 'table-bordered'

    def summary_subprojects_by_steps_already_track(self, all_subprojects, characters_length, administrative_levels_ids):
        datas = {
            _("Step"): {},
            _("Number"): {}
        }
        
        # count = 0

        # for step in Step.objects.all():
        #     datas[_("Step")][count] = step.__str__()

        #     datas[_("Number")][count] = all_subprojects.filter(subprojectstep__step__id=step.id).count() #all_subprojects.filter_by_steps_already_track(Subproject, step_id=step.id).count()
        
        #     count += 1
        administrative_levels_ids_str = ', '.join(str(elt) for elt in administrative_levels_ids)
        count = 0
        with connection.cursor() as cursor:
            try:
                cursor.execute("""
SELECT s.wording, COUNT(subp_subp_step.subp_id) FROM subprojects_step s 
LEFT JOIN (
    SELECT subp.id subp_id, subp_step.step_id subp_step_step_id FROM subprojects_subprojectstep subp_step 
    INNER JOIN subprojects_subproject subp ON subp_step.subproject_id=subp.id 
    WHERE subp.location_subproject_realized_id IN (%s) OR subp.canton_id IN (%s)
    ) subp_subp_step ON s.id=subp_subp_step.subp_step_step_id 
GROUP BY s.id
""" % (administrative_levels_ids_str, administrative_levels_ids_str))
                
                for row in cursor.fetchall():
                    datas[_("Step")][count] = row[0]
                    datas[_("Number")][count] = row[1]
                    count += 1
                    
            except Exception as exc:
                logging.exception(exc)


        return {
            'title': _("Subprojects by step"),
            'datas': datas,
            'length_loop': range(0, count),
            'values': list(datas.values())
        }
    


    def get_context_data(self, **kwargs):
        ctx = super(DashboardSubprojectsStepsAlreadyTrackListView, self).get_context_data(**kwargs)
        all_subprojects = ctx['queryset_results']['subprojects']
        
        ctx["summary"] = {}

        characters_length = 3
        ctx["summary"]["summary_subprojects_by_steps_already_track"] = {}
        for k, v in self.summary_subprojects_by_steps_already_track(all_subprojects, characters_length, ctx['queryset_results']['administrative_levels_ids']).items():
            ctx["summary"]["summary_subprojects_by_steps_already_track"][k] = v

        ctx["queryset_results"]["administrative_level_type"] = None

        return ctx
    


class DashboardSubprojectsCurrentStepsListView(DashboardSubprojectsMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'tracking.html'
    context_object_name = 'queryset_results'
    table_class_style = 'table-bordered'
    
    def summary_subprojects_by_current_steps(self, all_subprojects, characters_length, administrative_levels_ids):
        datas = {
            _("Step"): {},
            _("Number"): {}
        }
        
        # count = 0
        # for step in Step.objects.all():
        #     datas[_("Step")][count] = step.__str__()

        #     datas[_("Number")][count] = all_subprojects.filter_by_step(Subproject, step_id=step.id).count()
        #     count += 1
        administrative_levels_ids_str = ', '.join(str(elt) for elt in administrative_levels_ids)
        count = 0
        with connection.cursor() as cursor:
            try:
                cursor.execute("""
SELECT s.wording, COUNT(subp_step_current.subp_id) FROM subprojects_step s 
LEFT JOIN (
        SELECT subp.id subp_id, (
            SELECT subp_step.step_id FROM subprojects_subprojectstep subp_step 
            WHERE subp_step.subproject_id=subp.id 
            ORDER BY subp_step.begin DESC, subp_step.ranking DESC LIMIT 1 
        ) subp_step_step_id FROM subprojects_subproject subp 
        WHERE subp.location_subproject_realized_id IN (%s) OR subp.canton_id IN (%s)
    ) subp_step_current ON s.id=subp_step_step_id 
GROUP BY s.id
""" % (administrative_levels_ids_str, administrative_levels_ids_str))
                
                for row in cursor.fetchall():
                    datas[_("Step")][count] = row[0]
                    datas[_("Number")][count] = row[1]
                    count += 1
                    
            except Exception as exc:
                logging.exception(exc)

        datas[_("Step")][count] = _("Total")
        # All sum
        columns_skip = [
            _("Step°"),
        ]
        for k_data in datas.keys():
            _sum = 0
            if k_data not in columns_skip:
                _sum = functions.sum_dict_value(datas[k_data], count)
            if _sum:
                datas[k_data][count] = _sum #str(_sum).rjust(characters_length,'0')
        # End All sum


        return {
            'title': _("Subprojects by current step"),
            'datas': datas,
            'length_loop': range(0, count+1),
            'values': list(datas.values())
        }


    def get_context_data(self, **kwargs):
        ctx = super(DashboardSubprojectsCurrentStepsListView, self).get_context_data(**kwargs)
        all_subprojects = ctx['queryset_results']['subprojects']
        
        ctx["summary"] = {}

        characters_length = 3

        ctx["summary"]["summary_subprojects_by_current_steps"] = {}
        for k, v in self.summary_subprojects_by_current_steps(all_subprojects, characters_length, ctx['queryset_results']['administrative_levels_ids']).items():
            ctx["summary"]["summary_subprojects_by_current_steps"][k] = v

        ctx["queryset_results"]["administrative_level_type"] = None

        return ctx