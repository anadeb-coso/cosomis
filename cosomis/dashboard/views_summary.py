from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from cosomis.mixins import PageMixin, AJAXRequestMixin, ModalListMixin, JSONResponseMixin
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models import Sum, Max
from django.db import connection
import logging

from subprojects.models import Subproject, Step, Component
from administrativelevels.models import AdministrativeLevel
from financial.models.allocation import AdministrativeLevelAllocation
from process_manager.models import AdministrativeLevelWave
from administrativelevels.functions import get_administrative_level_ids_descendants
from . import forms
from cosomis.constants import (
    TYPES_OF_STRUCTURE_COLOR, STRUCTURE_COMPLETED_STATUS, STRUCTURE_IN_PROGRESS_STATUS,
    STRUCTURE_NOT_START_STATUS, SUB_PROJECT_SECTORS_COLOR, OTHER_STRUCUTURES,
    SUB_PROJECT_STATUS_COLOR_TRANSLATE, FINANCING_COLOR, STRUCTURE_PROVISIONAL_ACCEPTANCE_STATUS,
    STRUCTURE_FINAL_ACCEPTANCE_STATUS
)


class DashboardTemplateView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = 'dashboard_summary.html'
    active_level1 = 'dashboard_summary'
    title = _('Dashboard')
    
    def get_context_data(self, **kwargs):
        ctx = super(DashboardTemplateView, self).get_context_data(**kwargs)
        ctx['hide_content_header'] = True
        ctx['form_adl'] = forms.AdministrativeLevelFilterForm()
        return ctx


class DashboardSubprojectsMixin(ModalListMixin):

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
        administrative_levels = [] #AdministrativeLevel.objects.filter(id__in=administrative_levels_ids)
        if administrative_level_type == "All":
            administrative_levels = AdministrativeLevel.objects.filter(type="Region")
        elif ald_filter_ids and administrative_level_type != "All":
            administrative_levels = AdministrativeLevel.objects.filter(parent__id__in=ald_filter_ids)
        elif administrative_level_type:
            administrative_levels = AdministrativeLevel.objects.filter(parent__type=administrative_level_type)
        
        if not administrative_levels:
            administrative_levels = AdministrativeLevel.objects.filter(id__in=ald_filter_ids)

        subprojects = Subproject.objects.filter().get_actifs()

        sectors = sorted(list(set(list(subprojects.values_list('subproject_sector')))))
        
        if not ald_filter_ids:
            pass
        else:
            adls = ald_filter_ids + administrative_levels_ids
            subprojects = subprojects.filter(
                Q(location_subproject_realized__id__in=adls) | 
                Q(canton__id__in=adls)
            )
        administrative_level = administrative_levels.first()

        
        return {
            'subprojects': subprojects,
            'sectors': sorted([s[0] for s in sectors]),
            'administrative_level_type': administrative_level.type if administrative_level else "",
            'columns_tuples': list(administrative_levels.filter(Q(type=administrative_level.type)if administrative_level else Q()).order_by('name').values_list('id', 'name')),
            'ald_filter_ids': ald_filter_ids,
            'administrative_levels_ids': administrative_levels_ids
        }
    

class DashboardSubprojectsListView(DashboardSubprojectsMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'components/dashboard_summary_subprojects.html'
    context_object_name = 'queryset_results'
    
    def get_context_data(self, **kwargs):
        ctx = super(DashboardSubprojectsListView, self).get_context_data(**kwargs)
        all_subprojects = ctx['queryset_results']['subprojects']
        sectors = ctx['queryset_results']['sectors']
        
        ctx['total'] = all_subprojects.count()
        ctx['total_without_link'] = all_subprojects.filter(link_to_subproject=None, subproject_type_designation="Subproject").count()
        ctx['total_subproject'] = all_subprojects.filter(subproject_type_designation="Subproject").count()
        ctx['total_infrastruture'] = all_subprojects.filter(subproject_type_designation="Infrastructure").count()
        # ctx['total_latrine_blocks'] = all_subprojects.filter(has_latrine_blocs=True).count()
        # ctx['total_number_latrine_blocks'] = all_subprojects.filter(has_latrine_blocs=True).aggregate(Sum('number_of_latrine_blocks'))['number_of_latrine_blocks__sum']
        # ctx['total_number_latrine_blocks'] = ctx['total_number_latrine_blocks'] if ctx['total_number_latrine_blocks'] else 0
        # ctx['total_fences'] = all_subprojects.filter(has_fence=True).count()
        ctx['total_infrastrutures'] = ctx['total'] # + ctx['total_latrine_blocks'] + ctx['total_fences']
        
        # ctx['total_subproject_in_progress'] = all_subprojects.filter(subproject_type_designation="Subproject", current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS).count()
        # ctx['total_subproject_completed'] = all_subprojects.filter(subproject_type_designation="Subproject", current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).count()
        _s = all_subprojects.filter(subproject_type_designation="Subproject")
        # Get SQL representation of the first filter's queryset
        if _s.exists():
            _sql, _params = _s.query.get_compiler('default').as_sql()
            # Use the SQL representation in the raw query for the second filter
            final_queryset = _s.raw(
                f"""
                SELECT DISTINCT sub_subp.id, sub_subp.full_title_of_approved_subproject 
                FROM subprojects_subproject AS sub_subp 
                LEFT JOIN subprojects_subproject AS sub_infras ON sub_subp.id=sub_infras.link_to_subproject_id 
                WHERE (((sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_NOT_START_STATUS*2)} 
                    AND sub_infras.current_status_of_the_site IN {tuple(STRUCTURE_COMPLETED_STATUS+STRUCTURE_IN_PROGRESS_STATUS)}) 
                    OR (sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_IN_PROGRESS_STATUS+STRUCTURE_COMPLETED_STATUS)} 
                    AND (sub_infras.current_status_of_the_site IN {tuple(STRUCTURE_NOT_START_STATUS+STRUCTURE_IN_PROGRESS_STATUS)}))
                    OR (sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_IN_PROGRESS_STATUS*2)})) 
                    AND sub_subp.id IN (
                        SELECT sub.id FROM ({_sql}) AS sub 
                    ))
                """, _params
            )
            
            ctx['total_subproject_in_progress'] = len(final_queryset)
            final_queryset = _s.raw(
                f"""
                SELECT DISTINCT sub_subp.id, sub_subp.full_title_of_approved_subproject 
                FROM subprojects_subproject AS sub_subp 
                LEFT JOIN subprojects_subproject AS sub_infras ON sub_subp.id=sub_infras.link_to_subproject_id 
                WHERE (sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_COMPLETED_STATUS)}
                    AND (sub_infras.current_status_of_the_site IS NULL OR sub_infras.current_status_of_the_site IN {tuple(STRUCTURE_COMPLETED_STATUS)})) 
                    AND sub_subp.id IN (
                        SELECT sub.id FROM ({_sql}) AS sub 
                    )
                """, _params
            )
            ctx['total_subproject_completed'] = len(final_queryset)
            ctx['total_subproject_not_started'] = ctx['total_subproject'] - (ctx['total_subproject_in_progress'] + ctx['total_subproject_completed'])
            
            ctx['total_infrastruture_in_progress'] = all_subprojects.filter(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS).count()
            ctx['total_infrastruture_completed'] = all_subprojects.filter(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).count()
            ctx['total_infrastruture_not_started'] = ctx['total'] - (ctx['total_infrastruture_in_progress'] + ctx['total_infrastruture_completed'])
            
            # ctx['total_latrines_in_progress'] = all_subprojects.filter(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS, has_latrine_blocs=True).count()
            # ctx['total_latrines_completed'] = all_subprojects.filter(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS, has_latrine_blocs=True).count()
            # ctx['total_latrines_not_started'] = ctx['total_latrine_blocks'] - (ctx['total_latrines_in_progress'] + ctx['total_latrines_completed'])
            
            # ctx['total_number_latrine_in_progress'] = all_subprojects.filter(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS, has_latrine_blocs=True).aggregate(Sum('number_of_latrine_blocks'))['number_of_latrine_blocks__sum']
            # ctx['total_number_latrine_in_progress'] = ctx['total_number_latrine_in_progress'] if ctx['total_number_latrine_in_progress'] else 0
            # ctx['total_number_latrine_completed'] = all_subprojects.filter(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS, has_latrine_blocs=True).aggregate(Sum('number_of_latrine_blocks'))['number_of_latrine_blocks__sum']
            # ctx['total_number_latrine_completed'] = ctx['total_number_latrine_completed'] if ctx['total_number_latrine_completed'] else 0
            # ctx['total_number_latrine_not_started'] = ctx['total_number_latrine_blocks'] - (ctx['total_number_latrine_in_progress'] + ctx['total_number_latrine_completed'])
            
            # ctx['total_fences_in_progress'] = all_subprojects.filter(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS, has_fence=True).count()
            # ctx['total_fences_completed'] = all_subprojects.filter(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS, has_fence=True).count()
            # ctx['total_fences_not_started'] = ctx['total_fences'] - (ctx['total_fences_in_progress'] + ctx['total_fences_completed'])
            
            ctx['total_infrastrutures_in_progress'] = ctx['total_infrastruture_in_progress'] #+ ctx['total_latrines_in_progress'] + ctx['total_fences_in_progress']
            ctx['total_infrastrutures_completed'] = ctx['total_infrastruture_completed'] #+ ctx['total_latrines_completed'] + ctx['total_fences_completed']
            ctx['total_infrastrutures_not_started'] = ctx['total_infrastruture_not_started'] #+ ctx['total_latrines_not_started'] + ctx['total_fences_not_started']
            
            ctx['number_subproject_infrastrutures'] = {
                'title': _("Number of subprojects selected in relation to infrastructure by sector"),
                'labels': sectors,
                'bars': [
                    {
                        'label': _("Subproject"),
                        'backgroundColor': 'red',
                        'data': [
                            all_subprojects.filter(subproject_type_designation="Subproject", subproject_sector=sector).count() for sector in sectors
                        ]
                    },
                    {
                        'label': _("Infrastructure"),
                        'backgroundColor': 'blue',
                        'data': [
                            all_subprojects.filter(subproject_sector=sector).count() for sector in sectors
                        ]
                    },
                    {
                        'label': _("Infras with latrines/fences"),
                        'backgroundColor': 'green',
                        'data': [
                            (
                                all_subprojects.filter(subproject_sector=sector).count() #+ \
                                    # all_subprojects.filter(subproject_sector=sector, has_latrine_blocs=True).count() + \
                                    #     all_subprojects.filter(subproject_sector=sector, has_fence=True).count()
                            ) for sector in sectors
                        ]
                    }
                ]
            }
            
            
            ctx['amount_subproject_infrastrutures'] = {
                'title': _("Amount of subprojects selected in relation to infrastructure by sector"),
                'labels': sectors,
                'bars': [
                    # {
                    #     'label': _("Subproject"),
                    #     'backgroundColor': 'red',
                    #     'data': [(elt if elt else 0) for elt in [
                    #         all_subprojects.filter(subproject_type_designation="Subproject", subproject_sector=sector).aggregate(Sum('estimated_cost'))['estimated_cost__sum'] for sector in sectors
                    #     ]]
                    # },
                    {
                        'label': _("Infrastructure"),
                        'backgroundColor': 'blue',
                        'data': [(elt if elt else 0) for elt in [
                            all_subprojects.filter(subproject_sector=sector).aggregate(Sum('estimated_cost'))['estimated_cost__sum'] for sector in sectors
                        ]]
                    }
                    # ,
                    # {
                    #     'label': _("Infras with latrines/fences"),
                    #     'backgroundColor': 'green',
                    #     'data': [
                    #         (
                    #             all_subprojects.filter(subproject_sector=sector).aggregate(Sum('estimated_cost'))['estimated_cost__sum']
                    #         ) for sector in sectors
                    #     ]
                    # }
                ]
            }
            
            
            #Structure Graphe
            # structures = dict(sorted(TYPES_OF_STRUCTURE_COLOR.items()))
            # type_structures = sorted(list(structures.keys()))
            type_structures = list(TYPES_OF_STRUCTURE_COLOR.keys())
            ctx['type_structures'] = type_structures
            bars_type_structures = [
                {
                    'label': _("Structure"),
                    'backgroundColor': 'blue',
                    'data': [
                        (
                            # (all_subprojects.filter(type_of_subproject__istartswith='Bâtiment Scolaire', has_latrine_blocs=True).count() if type_structure == 'Latrine Scolaire' else \
                            #     (all_subprojects.filter(type_of_subproject__istartswith='Pédiatrie', has_fence=True).count() if type_structure == 'Clôture Pédiatrie' else \
                            #         (all_subprojects.filter(type_of_subproject__istartswith='Bâtiment Scolaire', has_fence=True).count()))) \
                            #     if type_structure in OTHER_STRUCUTURES \
                            #     else 
                                all_subprojects.filter(type_of_subproject=type_structure).count()
                        ) for type_structure in type_structures
                    ],
                    'classrooms': [(elt if elt else 0) for elt in [
                        (
                            all_subprojects.filter(type_of_subproject=type_structure, number_of_classrooms__isnull=False).aggregate(Sum('number_of_classrooms'))['number_of_classrooms__sum']
                        ) for type_structure in type_structures
                    ]]
                },
                {
                    'label': _("Not start"),
                    'backgroundColor': 'red',
                    'data': [
                        (
                            # (all_subprojects.filter(type_of_subproject__istartswith='Bâtiment Scolaire', has_latrine_blocs=True).exclude(current_status_of_the_site__in=(STRUCTURE_COMPLETED_STATUS+STRUCTURE_IN_PROGRESS_STATUS)).count() if type_structure == 'Latrine Scolaire' else \
                            #     (all_subprojects.filter(type_of_subproject__istartswith='Pédiatrie', has_fence=True).exclude(current_status_of_the_site__in=(STRUCTURE_COMPLETED_STATUS+STRUCTURE_IN_PROGRESS_STATUS)).count() if type_structure == 'Clôture Pédiatrie' else \
                            #         (all_subprojects.filter(type_of_subproject__istartswith='Bâtiment Scolaire', has_fence=True).exclude(current_status_of_the_site__in=(STRUCTURE_COMPLETED_STATUS+STRUCTURE_IN_PROGRESS_STATUS)).count()))) \
                            #     if type_structure in OTHER_STRUCUTURES \
                            #     else 
                                all_subprojects.filter(type_of_subproject=type_structure).exclude(current_status_of_the_site__in=(STRUCTURE_COMPLETED_STATUS+STRUCTURE_IN_PROGRESS_STATUS)).count()
                        ) for type_structure in type_structures
                    ],
                    'classrooms': [(elt if elt else 0) for elt in [
                        (
                            all_subprojects.filter(type_of_subproject=type_structure, number_of_classrooms__isnull=False).exclude(current_status_of_the_site__in=(STRUCTURE_COMPLETED_STATUS+STRUCTURE_IN_PROGRESS_STATUS)).aggregate(Sum('number_of_classrooms'))['number_of_classrooms__sum']
                        ) for type_structure in type_structures
                    ]]
                },
                {
                    'label': _("In progress"),
                    'backgroundColor': 'purple',
                    'data': [
                        (
                            # (all_subprojects.filter(type_of_subproject__istartswith='Bâtiment Scolaire', has_latrine_blocs=True, current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS).count() if type_structure == 'Latrine Scolaire' else \
                            #     (all_subprojects.filter(type_of_subproject__istartswith='Pédiatrie', has_fence=True, current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS).count() if type_structure == 'Clôture Pédiatrie' else \
                            #         (all_subprojects.filter(type_of_subproject__istartswith='Bâtiment Scolaire', has_fence=True, current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS).count()))) \
                            #     if type_structure in OTHER_STRUCUTURES \
                            #     else 
                                all_subprojects.filter(type_of_subproject=type_structure, current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS).count()
                        ) for type_structure in type_structures
                    ],
                    'classrooms': [(elt if elt else 0) for elt in [
                        (
                            all_subprojects.filter(type_of_subproject=type_structure, current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS, number_of_classrooms__isnull=False).aggregate(Sum('number_of_classrooms'))['number_of_classrooms__sum']
                        ) for type_structure in type_structures
                    ]]
                },
                {
                    'label': _("Completed"),
                    'backgroundColor': 'green',
                    'data': [
                        (
                            # (all_subprojects.filter(type_of_subproject__istartswith='Bâtiment Scolaire', has_latrine_blocs=True, current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).count() if type_structure == 'Latrine Scolaire' else \
                            #     (all_subprojects.filter(type_of_subproject__istartswith='Pédiatrie', has_fence=True, current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).count() if type_structure == 'Clôture Pédiatrie' else \
                            #         (all_subprojects.filter(type_of_subproject__istartswith='Bâtiment Scolaire', has_fence=True, current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).count()))) \
                            #     if type_structure in OTHER_STRUCUTURES \
                            #     else 
                                all_subprojects.filter(type_of_subproject=type_structure, current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).count()
                        ) for type_structure in type_structures
                    ],
                    'classrooms': [(elt if elt else 0) for elt in [
                        (
                            all_subprojects.filter(type_of_subproject=type_structure, current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS, number_of_classrooms__isnull=False).aggregate(Sum('number_of_classrooms'))['number_of_classrooms__sum']
                        ) for type_structure in type_structures
                    ]]
                }
            ]
            ctx['bars_type_structures'] = bars_type_structures
            ctx['sum_bars_type_structures'] = [sum(elt.get('data')) for elt in bars_type_structures]
            ctx['number_structures_by_type'] = {
                'title': _("Structures by type"),
                'labels': type_structures,
                'bars': [bars_type_structures[0], bars_type_structures[3]]
            }
            
            
            #Summary Recap
            datas = {
                _("Types of work"): {},
                _("Total number of sub-projects selected"): {},
                _("Total number of sub-projects completed"): {},
                _("Total number of structures to be built"): {},
                _("Total number of projects launched"): {},
                _("Total number of works completed"): {},
                _("Total number of provisionally approved structures"): {},
                _("Total number of works finally accepted"): {},
                _("Comments"): {}
            }
            
            count = 0
            # str().capitalize()
            count_sectors = 0
            lines_to_skip_for_sum = []
            for _sector in [s.upper() for s in sectors]:
                all_subprojects_sector = all_subprojects.filter(subproject_sector=_sector)
                _types = sorted(list(set(list([o[0].capitalize() for o in all_subprojects_sector.values_list('type_of_subproject')]))))
                
                for k, v in datas.items():
                    datas[k][count] = _(f"{_sector}")
                count += 1
                
                count_types = 0
                count_start = count
                for _type in _types:
                    all_subprojects_sector_type = all_subprojects_sector.filter(type_of_subproject=_type)
                    datas[_("Types of work")][count] = _type
                    datas[_("Total number of sub-projects selected")][count] = all_subprojects_sector_type.filter(subproject_type_designation="Subproject").count()
                    datas[_("Total number of structures to be built")][count] = all_subprojects_sector_type.count()
                    datas[_("Total number of projects launched")][count] = all_subprojects_sector_type.filter(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS).count()
                    datas[_("Total number of works completed")][count] = all_subprojects_sector_type.filter(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).count()
                    datas[_("Total number of provisionally approved structures")][count] = all_subprojects_sector_type.filter(current_status_of_the_site__in=STRUCTURE_PROVISIONAL_ACCEPTANCE_STATUS).count()
                    datas[_("Total number of works finally accepted")][count] = all_subprojects_sector_type.filter(current_status_of_the_site__in=STRUCTURE_FINAL_ACCEPTANCE_STATUS).count()
                    
                    _s = all_subprojects_sector_type.filter(subproject_type_designation="Subproject")
                    if _s.exists():
                        _sql, _params = _s.query.get_compiler('default').as_sql()
                        final_queryset = _s.raw(
                            f"""
                            SELECT DISTINCT sub_subp.id, sub_subp.full_title_of_approved_subproject 
                            FROM subprojects_subproject AS sub_subp 
                            LEFT JOIN subprojects_subproject AS sub_infras ON sub_subp.id=sub_infras.link_to_subproject_id 
                            WHERE (sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_COMPLETED_STATUS)}
                                AND (sub_infras.current_status_of_the_site IS NULL OR sub_infras.current_status_of_the_site IN {tuple(STRUCTURE_COMPLETED_STATUS)})) 
                                AND sub_subp.id IN (
                                    SELECT sub.id FROM ({_sql}) AS sub 
                                )
                            """, _params
                        )
                        datas[_("Total number of sub-projects completed")][count] = len(final_queryset)
                    else:
                        datas[_("Total number of sub-projects completed")][count] = 0
                    
                    count += 1
                    count_types += 1
                
                datas[_("Types of work")][count] = _(f"Total {_sector}")
                for k, v in datas.items():
                    if k not in [_("Types of work"), _("Comments")]:
                        datas[k][count] = sum(list(v.values())[count_start:count])
                        lines_to_skip_for_sum.append(count)
                count += 1
                
                
                count_sectors += 1
            
            
            datas[_("Types of work")][count] = _(f"Total")
            for k, v in datas.items():
                if k not in [_("Types of work"), _("Comments")]:
                    datas[k][count] = sum([elt for k_elt, elt in list(v.items()) if str(elt).isdigit() and k_elt not in lines_to_skip_for_sum])
            count += 1
                
                
            summary_recap = {
                'title': _("Summary of results"),
                'datas': datas,
                'length_loop': range(0, count),
                'values': list(datas.values())
            }
            ctx["summary_recap"] = {}
            for k, v in summary_recap.items():
                ctx["summary_recap"][k] = v
            
            ctx["table_class_style"] = 'table table-striped table-secondary table-bordered'
            #End Summary Recap
            
            
            
            ctx['number_subproject_infrastrutures_by_sectors_and_type'] = {
                _('Identified'): dict([
                    (sector,{
                        'types': dict([
                            (t[0], all_subprojects.filter(subproject_sector=sector, type_of_subproject=t[0]).count()) for t in sorted(list(set(list(all_subprojects.filter(subproject_sector=sector).values_list('type_of_subproject')))))
                        ] 
                        #               + [
                        #     (type_structure,
                        #     (all_subprojects.filter(subproject_sector=sector, type_of_subproject__istartswith='Bâtiment Scolaire', has_latrine_blocs=True).count() if type_structure == 'Latrine Scolaire' else \
                        #         (all_subprojects.filter(subproject_sector=sector, type_of_subproject__istartswith='Pédiatrie', has_fence=True).count() if type_structure == 'Clôture Pédiatrie' else \
                        #             (all_subprojects.filter(subproject_sector=sector, type_of_subproject__istartswith='Bâtiment Scolaire', has_fence=True).count()))) 
                        # ) for type_structure in OTHER_STRUCUTURES
                        # ]
                                      ), 
                        'total': {
                            'subprojects': all_subprojects.filter(subproject_type_designation="Subproject", subproject_sector=sector).count(),
                            'infrastructures': all_subprojects.filter(subproject_sector=sector).count(),
                            'infrastructures_with_latrines_and_fences': (
                                all_subprojects.filter(subproject_sector=sector).count()
                                # + \
                                #     all_subprojects.filter(subproject_sector=sector, has_latrine_blocs=True).count() + \
                                #         all_subprojects.filter(subproject_sector=sector, has_fence=True).count()
                            )
                        }
                    }) for sector in sectors
                ] + [('total', ctx['total_infrastrutures'])]),
                _('Completed'): dict([
                    (sector,{
                        'types': dict([
                            (t[0], all_subprojects.filter(subproject_sector=sector, type_of_subproject=t[0], current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).count()) for t in sorted(list(set(list(all_subprojects.filter(subproject_sector=sector, current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).values_list('type_of_subproject')))))
                        ]
                        #               + [
                        #     (type_structure,
                        #     (all_subprojects.filter(subproject_sector=sector, type_of_subproject__istartswith='Bâtiment Scolaire', has_latrine_blocs=True, current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).count() if type_structure == 'Latrine Scolaire' else \
                        #         (all_subprojects.filter(subproject_sector=sector, type_of_subproject__istartswith='Pédiatrie', has_fence=True, current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).count() if type_structure == 'Clôture Pédiatrie' else \
                        #             (all_subprojects.filter(subproject_sector=sector, type_of_subproject__istartswith='Bâtiment Scolaire', has_fence=True, current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).count()))) 
                        # ) for type_structure in OTHER_STRUCUTURES
                        # ]
                                      ), 
                        'total': {
                            'subprojects': len(all_subprojects.raw(
                                f"""
                                SELECT DISTINCT sub_subp.id, sub_subp.full_title_of_approved_subproject 
                                FROM subprojects_subproject AS sub_subp 
                                LEFT JOIN subprojects_subproject AS sub_infras ON sub_subp.id=sub_infras.link_to_subproject_id 
                                WHERE (sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_COMPLETED_STATUS)}
                                    AND (sub_infras.current_status_of_the_site IS NULL OR sub_infras.current_status_of_the_site IN {tuple(STRUCTURE_COMPLETED_STATUS)})) 
                                    AND sub_subp.id IN (
                                        SELECT sub.id FROM ({_sql}) AS sub 
                                    ) AND sub_subp.subproject_sector=%s
                                """, _params + (sector,)
                            )),
                            'infrastructures': all_subprojects.filter(subproject_sector=sector, current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).count(),
                            'infrastructures_with_latrines_and_fences': (
                                all_subprojects.filter(subproject_sector=sector, current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).count()
                                # + \
                                #     all_subprojects.filter(subproject_sector=sector, has_latrine_blocs=True, current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).count() + \
                                #         all_subprojects.filter(subproject_sector=sector, has_fence=True, current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).count()
                            )
                        }
                    }) for sector in sectors
                ] + [('total', ctx['total_infrastrutures_completed'])]),
                _('In progress'): dict([
                    (sector,{
                        'types': dict([
                            (t[0], all_subprojects.filter(subproject_sector=sector, type_of_subproject=t[0], current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS).count()) for t in sorted(list(set(list(all_subprojects.filter(subproject_sector=sector, current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS).values_list('type_of_subproject')))))
                        ] 
                        #               + [
                        #     (type_structure,
                        #     (all_subprojects.filter(subproject_sector=sector, type_of_subproject__istartswith='Bâtiment Scolaire', has_latrine_blocs=True, current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS).count() if type_structure == 'Latrine Scolaire' else \
                        #         (all_subprojects.filter(subproject_sector=sector, type_of_subproject__istartswith='Pédiatrie', has_fence=True, current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS).count() if type_structure == 'Clôture Pédiatrie' else \
                        #             (all_subprojects.filter(subproject_sector=sector, type_of_subproject__istartswith='Bâtiment Scolaire', has_fence=True, current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS).count()))) 
                        # ) for type_structure in OTHER_STRUCUTURES
                        # ]
                                      ), 
                        'total': {
                            'subprojects': len(all_subprojects.raw(
                                f"""
                                SELECT DISTINCT sub_subp.id, sub_subp.full_title_of_approved_subproject 
                                FROM subprojects_subproject AS sub_subp 
                                LEFT JOIN subprojects_subproject AS sub_infras ON sub_subp.id=sub_infras.link_to_subproject_id 
                                WHERE (((sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_NOT_START_STATUS*2)} 
                                    AND sub_infras.current_status_of_the_site IN {tuple(STRUCTURE_COMPLETED_STATUS+STRUCTURE_IN_PROGRESS_STATUS)}) 
                                    OR (sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_IN_PROGRESS_STATUS+STRUCTURE_COMPLETED_STATUS)} 
                                    AND (sub_infras.current_status_of_the_site IN {tuple(STRUCTURE_NOT_START_STATUS+STRUCTURE_IN_PROGRESS_STATUS)}))
                                    OR (sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_IN_PROGRESS_STATUS*2)})) 
                                    AND sub_subp.id IN (
                                        SELECT sub.id FROM ({_sql}) AS sub 
                                    ) AND sub_subp.subproject_sector=%s)
                                """, _params + (sector,)
                            )),
                            'infrastructures': all_subprojects.filter(subproject_sector=sector, current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS).count(),
                            'infrastructures_with_latrines_and_fences': (
                                all_subprojects.filter(subproject_sector=sector, current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS).count()
                                # + \
                                #     all_subprojects.filter(subproject_sector=sector, has_latrine_blocs=True, current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS).count() + \
                                #         all_subprojects.filter(subproject_sector=sector, has_fence=True, current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS).count()
                            )
                        }
                    }) for sector in sectors
                ] + [('total', ctx['total_infrastrutures_in_progress'])]),
                _('Not start'): dict([
                    (sector,{
                        'types': dict([
                            (t[0], all_subprojects.filter(subproject_sector=sector, type_of_subproject=t[0], current_status_of_the_site__in=STRUCTURE_NOT_START_STATUS).count()) for t in sorted(list(set(list(all_subprojects.filter(subproject_sector=sector, current_status_of_the_site__in=STRUCTURE_NOT_START_STATUS).values_list('type_of_subproject')))))
                        ] 
                        #               + [
                        #     (type_structure,
                        #     (all_subprojects.filter(subproject_sector=sector, type_of_subproject__istartswith='Bâtiment Scolaire', has_latrine_blocs=True, current_status_of_the_site__in=STRUCTURE_NOT_START_STATUS).count() if type_structure == 'Latrine Scolaire' else \
                        #         (all_subprojects.filter(subproject_sector=sector, type_of_subproject__istartswith='Pédiatrie', has_fence=True, current_status_of_the_site__in=STRUCTURE_NOT_START_STATUS).count() if type_structure == 'Clôture Pédiatrie' else \
                        #             (all_subprojects.filter(subproject_sector=sector, type_of_subproject__istartswith='Bâtiment Scolaire', has_fence=True, current_status_of_the_site__in=STRUCTURE_NOT_START_STATUS).count()))) 
                        # ) for type_structure in OTHER_STRUCUTURES
                        # ]
                                      ), 
                        'total': {
                            'subprojects': len(all_subprojects.raw(
                                f"""
                                SELECT DISTINCT sub_subp.id 
                                FROM subprojects_subproject AS sub_subp 
                                LEFT JOIN subprojects_subproject AS sub_infras ON sub_infras.link_to_subproject_id=sub_subp.id AND sub_infras.subproject_type_designation='Infrastructure' 
                                WHERE (sub_subp.current_status_of_the_site NOT IN {tuple(STRUCTURE_IN_PROGRESS_STATUS+STRUCTURE_COMPLETED_STATUS)} 
                                    AND (sub_infras.current_status_of_the_site IS NULL OR sub_infras.current_status_of_the_site NOT IN {tuple(STRUCTURE_IN_PROGRESS_STATUS+STRUCTURE_COMPLETED_STATUS)})) 
                                    AND sub_subp.id IN (
                                        SELECT sub.id FROM ({_sql}) AS sub 
                                    ) AND sub_subp.subproject_sector=%s
                                """, _params + (sector,)
                            )),
                            'infrastructures': all_subprojects.filter(subproject_sector=sector, current_status_of_the_site__in=STRUCTURE_NOT_START_STATUS).count(),
                            'infrastructures_with_latrines_and_fences': (
                                all_subprojects.filter(subproject_sector=sector, current_status_of_the_site__in=STRUCTURE_NOT_START_STATUS).count()
                                # + \
                                #     all_subprojects.filter(subproject_sector=sector, has_latrine_blocs=True, current_status_of_the_site__in=STRUCTURE_NOT_START_STATUS).count() + \
                                #         all_subprojects.filter(subproject_sector=sector, has_fence=True, current_status_of_the_site__in=STRUCTURE_NOT_START_STATUS).count()
                            )
                        }
                    }) for sector in sectors
                ] + [('total', ctx['total_infrastrutures_not_started'])])
            }
            
        
            ctx['pie_graphes'] = [
                {
                    'type': _("Level"),
                    'title': _("Number of infrastructures by status"),
                    'labels': [_("Completed"), _("In progress"), _("Not start")],
                    'data': [ctx['total_infrastrutures_completed'], ctx['total_infrastrutures_in_progress'], ctx['total_infrastrutures_not_started']],
                    'sorted': 0
                },
                {
                    'type': _("Sector"),
                    'title': _("Number of subprojects selected by sector"),
                    'labels': sectors,
                    'data': ctx['number_subproject_infrastrutures']['bars'][2]['data'],
                    'sorted': 1,
                    'columnSorted': 1
                }
            ]
            
            
        
        ctx['administrative_level_id'] = self.request.GET.getlist('administrative_level_id[]', [])
        administrative_level_type = self.request.GET.get('administrative_level_type', 'All').title()
        ctx['administrative_level_type'] = "All" if administrative_level_type in ("", "null", "undefined") else administrative_level_type
        ctx['SUB_PROJECT_SECTORS_COLOR'] = SUB_PROJECT_SECTORS_COLOR
        ctx['SUB_PROJECT_STATUS_COLOR_TRANSLATE'] = SUB_PROJECT_STATUS_COLOR_TRANSLATE
        return ctx
    


class DashboardFinancingListView(DashboardSubprojectsMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'components/dashboard_summary_financing.html'
    context_object_name = 'queryset_results'
    
    def get_context_data(self, **kwargs):
        ctx = super(DashboardFinancingListView, self).get_context_data(**kwargs)
        ctx['pie_graphes'] = []
        all_subprojects = ctx['queryset_results']['subprojects']
        sectors = ctx['queryset_results']['sectors']
        ids = ctx['queryset_results']['ald_filter_ids'].copy() + ctx['queryset_results']['administrative_levels_ids'].copy()
        if ids:
            allocations_project = AdministrativeLevelAllocation.objects.filter(
                project_id=1,
                cvd=None,
                administrative_level__id__in=ids,
                administrative_level__type="Canton"
            )
        else:
            allocations_project = AdministrativeLevelAllocation.objects.filter(
                project_id=1,
                cvd=None,
                administrative_level__type="Canton"
            )
        
        #Component 1.1
        financing_components = {}
        for component, component_id in {
            _('Component 1.1'): 2, _('Component 1.2'): 3, _('Component 1.3'): 6
        }.items():
            financing_components[component] = {}
            financing_components[component]['total_amount_subprojects_estimated_cost'] = all_subprojects.filter(component_id=component_id).aggregate(Sum('estimated_cost'))['estimated_cost__sum']
            financing_components[component]['total_amount_subprojects_estimated_cost'] = financing_components[component]['total_amount_subprojects_estimated_cost'] if financing_components[component]['total_amount_subprojects_estimated_cost'] else 0
            
            financing_components[component]['total_amount_subprojects_contract_amount_work_companies'] = all_subprojects.filter(component_id=component_id).aggregate(Sum('contract_amount_work_companies'))['contract_amount_work_companies__sum']
            financing_components[component]['total_amount_subprojects_contract_amount_work_companies'] = financing_components[component]['total_amount_subprojects_contract_amount_work_companies'] if financing_components[component]['total_amount_subprojects_contract_amount_work_companies'] else 0
            
            financing_components[component]['total_allocations_cantons'] = allocations_project.filter(cvd=None, component_id=component_id).aggregate(Sum('amount'))['amount__sum']
            financing_components[component]['total_allocations_cantons'] = financing_components[component]['total_allocations_cantons'] if financing_components[component]['total_allocations_cantons'] else 0
            
            financing_components[component]['total_amount_remaining_after_allocation'] = financing_components[component]['total_allocations_cantons'] - financing_components[component]['total_amount_subprojects_estimated_cost']
            financing_components[component]['total_amount_residual'] = financing_components[component]['total_allocations_cantons'] - financing_components[component]['total_amount_subprojects_contract_amount_work_companies']

            ctx['pie_graphes'].append({
                'type': _("Wording"),
                'type_value_label': _("Amount"),
                'title': _("Amount of infrastructures by status") + f" {component}",
                'labels': [_("Residual"), _("Spent")],
                'data': [financing_components[component]['total_amount_residual'], financing_components[component]['total_amount_subprojects_contract_amount_work_companies']],
                'sorted': 0
            })
            
        ctx['financing_components'] = financing_components
        
        
        ctx['total_amount_subprojects_estimated_cost'] = all_subprojects.aggregate(Sum('estimated_cost'))['estimated_cost__sum']
        ctx['total_amount_subprojects_estimated_cost'] = ctx['total_amount_subprojects_estimated_cost'] if ctx['total_amount_subprojects_estimated_cost'] else 0
        
        ctx['total_amount_subprojects_contract_amount_work_companies'] = all_subprojects.aggregate(Sum('contract_amount_work_companies'))['contract_amount_work_companies__sum']
        ctx['total_amount_subprojects_contract_amount_work_companies'] = ctx['total_amount_subprojects_contract_amount_work_companies'] if ctx['total_amount_subprojects_contract_amount_work_companies'] else 0
        
        ctx['total_allocations_cantons'] = allocations_project.filter(cvd=None).aggregate(Sum('amount'))['amount__sum']
        ctx['total_allocations_cantons'] = ctx['total_allocations_cantons'] if ctx['total_allocations_cantons'] else 0
        
        ctx['total_amount_remaining_after_allocation'] = ctx['total_allocations_cantons'] - ctx['total_amount_subprojects_estimated_cost']
        ctx['total_amount_residual'] = ctx['total_allocations_cantons'] - ctx['total_amount_subprojects_contract_amount_work_companies']
        
        
        ctx['amount_subproject_infrastrutures'] = {
            'title': _("Amount of infrastructures by sector"),
            'labels': sectors,
            'bars': [
                {
                    'label': _("Infrastructure"),
                    'backgroundColor': 'blue',
                    'data': [(elt if elt else 0) for elt in [
                        all_subprojects.filter(subproject_sector=sector).aggregate(Sum('estimated_cost'))['estimated_cost__sum'] for sector in sectors
                    ]]
                }
            ]
        }
        
        ctx['pie_graphes'].append({
            'type': _("Wording"),
            'type_value_label': _("Amount"),
            'title': _("Amount of infrastructures by status"),
            'labels': [_("Residual"), _("Spent")],
            'data': [ctx['total_amount_residual'], ctx['total_amount_subprojects_contract_amount_work_companies']],
            'sorted': 0
        })
        
        ctx['pie_graphes'].append({
            'type': _("Sectors"),
            'type_value_label': _("Amount"),
            'title': _("Amount of infrastructures by sector"),
            'labels': sectors,
            'data': ctx['amount_subproject_infrastrutures']['bars'][0]['data'],
            'sorted': 1,
            'columnSorted': 1
        })

        ctx['administrative_level_id'] = self.request.GET.getlist('administrative_level_id[]', [])
        administrative_level_type = self.request.GET.get('administrative_level_type', 'All').title()
        ctx['administrative_level_type'] = "All" if administrative_level_type in ("", "null", "undefined") else administrative_level_type
        ctx['FINANCING_COLOR'] = FINANCING_COLOR
        ctx['SUB_PROJECT_SECTORS_COLOR'] = SUB_PROJECT_SECTORS_COLOR
        return ctx


class DashboardFinancingListByCantonView(DashboardSubprojectsMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'components/dashboard_summary_financing_by_canton.html'
    context_object_name = 'queryset_results'
    
    def get_context_data(self, **kwargs):
        ctx = super(DashboardFinancingListByCantonView, self).get_context_data(**kwargs)
        all_subprojects = ctx['queryset_results']['subprojects']
        # components = Component.objects.filter(parent__name="Composante 1")
        ids = ctx['queryset_results']['ald_filter_ids'].copy() + ctx['queryset_results']['administrative_levels_ids'].copy()
        if ids:
            allocations_project = AdministrativeLevelAllocation.objects.filter(
                project_id=1,
                cvd=None,
                administrative_level__id__in=ids,
                administrative_level__type="Canton"
            )
        else:
            allocations_project = AdministrativeLevelAllocation.objects.filter(
                project_id=1,
                cvd=None,
                administrative_level__type="Canton"
            )
        allocations_project = AdministrativeLevelAllocation.objects.filter()

        if ids:
            lines = AdministrativeLevelWave.objects.filter(administrative_level__id__in=ids).order_by("administrative_level__name")
            # admls = AdministrativeLevel.objects.filter(type="Canton", id__in=ids).order_by("name")
        else:
            #  admls = AdministrativeLevel.objects.filter(type="Canton").order_by("name")
             lines = AdministrativeLevelWave.objects.all().order_by("administrative_level__name")
        admls = [adl.administrative_level for adl in lines]
        admls_children = [
            (
                adl, 
                allocations_project.filter(
                    administrative_level__id=adl.id
                ),
                ([adl.id] + get_administrative_level_ids_descendants(adl.id, None, []))) for adl in admls
        ]
        
        ctx['amount_cantons_component_1_1'] = {
            'title': _("Presentation of allocations, estimates and expenditure by canton - Component 1.1"),
            'labels': [adl.name for adl in admls],
            'bars': [
                {
                    'label': _("Allocation"),
                    'backgroundColor': 'blue',
                    'data': [(elt if elt else 0) for elt in [
                        adml[1].filter(
                            component_id=2
                        ).aggregate(Sum('amount'))['amount__sum'] for adml in admls_children
                    ]]
                },
                {
                    'label': _("Sub-project estimates"),
                    'backgroundColor': 'red',
                    'data': [(elt if elt else 0) for elt in [
                        all_subprojects.filter(
                            Q(location_subproject_realized__id__in=adml[2]) | 
                            Q(canton__id__in=adml[2]), component_id=2
                        ).aggregate(Sum('estimated_cost'))['estimated_cost__sum'] for adml in admls_children
                    ]]
                },
                {
                    'label': _("Spent"),
                    'backgroundColor': 'green',
                    'data': [(elt if elt else 0) for elt in [
                        all_subprojects.filter(
                            Q(location_subproject_realized__id__in=adml[2]) | 
                            Q(canton__id__in=adml[2]), component_id=2
                        ).aggregate(Sum('contract_amount_work_companies'))['contract_amount_work_companies__sum'] for adml in admls_children
                    ]]
                }
            ]
        }
        
        
        ctx['amount_cantons_component_1_2'] = {
            'title': _("Presentation of allocations, estimates and expenditure by canton - Component 1.2"),
            'labels': [adl.name for adl in admls],
            'bars': [
                {
                    'label': _("Allocation"),
                    'backgroundColor': 'blue',
                    'data': [(elt if elt else 0) for elt in [
                        adml[1].filter(
                            component_id=3
                        ).aggregate(Sum('amount'))['amount__sum'] for adml in admls_children
                    ]]
                },
                {
                    'label': _("Sub-project estimates"),
                    'backgroundColor': 'red',
                    'data': [(elt if elt else 0) for elt in [
                        all_subprojects.filter(
                            Q(location_subproject_realized__id__in=adml[2]) | 
                            Q(canton__id__in=adml[2]), component_id=3
                        ).aggregate(Sum('estimated_cost'))['estimated_cost__sum'] for adml in admls_children
                    ]]
                },
                {
                    'label': _("Spent"),
                    'backgroundColor': 'green',
                    'data': [(elt if elt else 0) for elt in [
                        all_subprojects.filter(
                            Q(location_subproject_realized__id__in=adml[2]) | 
                            Q(canton__id__in=adml[2]), component_id=3
                        ).aggregate(Sum('contract_amount_work_companies'))['contract_amount_work_companies__sum'] for adml in admls_children
                    ]]
                }
            ]
        }
        
        
        ctx['amount_cantons_component_1_3'] = {
            'title': _("Presentation of allocations, estimates and expenditure by canton - Component 1.3"),
            'labels': [adl.name for adl in admls],
            'bars': [
                {
                    'label': _("Allocation"),
                    'backgroundColor': 'blue',
                    'data': [(elt if elt else 0) for elt in [
                        adml[1].filter(
                            component_id=6
                        ).aggregate(Sum('amount'))['amount__sum'] for adml in admls_children
                    ]]
                },
                {
                    'label': _("Sub-project estimates"),
                    'backgroundColor': 'red',
                    'data': [(elt if elt else 0) for elt in [
                        all_subprojects.filter(
                            Q(location_subproject_realized__id__in=adml[2]) | 
                            Q(canton__id__in=adml[2]), component_id=6
                        ).aggregate(Sum('estimated_cost'))['estimated_cost__sum'] for adml in admls_children
                    ]]
                },
                {
                    'label': _("Spent"),
                    'backgroundColor': 'green',
                    'data': [(elt if elt else 0) for elt in [
                        all_subprojects.filter(
                            Q(location_subproject_realized__id__in=adml[2]) | 
                            Q(canton__id__in=adml[2]), component_id=6
                        ).aggregate(Sum('contract_amount_work_companies'))['contract_amount_work_companies__sum'] for adml in admls_children
                    ]]
                }
            ]
        }
        
        
        # ctx['pie_graphes'] = [
        #     {
        #         'type': _("Locality"),
        #         'type_value_label': _("Amount"),
        #         'title': _("Presentation of allocations by canton - Component 1.1"),
        #         'labels': [adl.name for adl in admls],
        #         'data': ctx['amount_cantons_component_1_1']['bars'][0]['data'],
        #         'sorted': 1,
        #         'columnSorted': 1
        #     },
        #     {
        #         'type': _("Locality"),
        #         'type_value_label': _("Amount"),
        #         'title': _("Presentation of allocations by canton - Component 1.2"),
        #         'labels': [adl.name for adl in admls],
        #         'data': ctx['amount_cantons_component_1_2']['bars'][0]['data'],
        #         'sorted': 1,
        #         'columnSorted': 1
        #     },
        #     {
        #         'type': _("Locality"),
        #         'type_value_label': _("Amount"),
        #         'title': _("Presentation of allocations by canton - Component 1.3"),
        #         'labels': [adl.name for adl in admls],
        #         'data': ctx['amount_cantons_component_1_3']['bars'][0]['data'],
        #         'sorted': 1,
        #         'columnSorted': 1
        #     }
        # ]
        
        
        ctx['administrative_level_id'] = self.request.GET.getlist('administrative_level_id[]', [])
        administrative_level_type = self.request.GET.get('administrative_level_type', 'All').title()
        ctx['administrative_level_type'] = "All" if administrative_level_type in ("", "null", "undefined") else administrative_level_type
        
        # ctx['administrative_level_colors'] = {}
        # adl_colors = list(SUB_PROJECT_SECTORS_COLOR.values())*5
        # _admls = admls[:]
        # for i in range(len(_admls)):
        #     try:
        #         ctx['administrative_level_colors'][_admls[i].name] = adl_colors[i]
        #     except:
        #         ctx['administrative_level_colors'][_admls[i].name] = '#000000'
            
        return ctx





"""Modals details"""

class SubprojectsDetailsModalView(DashboardSubprojectsMixin, AJAXRequestMixin, 
                                  LoginRequiredMixin, JSONResponseMixin, generic.ListView):
    id_list = "subproject_list"
    title = _('Subprojects')
    context_object_name = 'queryset_results'
    _obj = None

    
    def get_queryset_search(self, subprojects):
        search = self.request.GET.get("search", None)
        page_number = self.request.GET.get("page", None)
        _len = len(subprojects)
        if search:
            if search == "All":
                return Paginator(subprojects, _len if _len else 1).get_page(page_number)
            search = search.upper()
            return Paginator(subprojects, 100).get_page(page_number)
        else:
            return Paginator(subprojects, _len if _len else 1).get_page(page_number)
        
        
    def get_context_data(self, **kwargs):
        ctx = super(SubprojectsDetailsModalView, self).get_context_data(**kwargs)
        all_subprojects = ctx['queryset_results']['subprojects']
        list_type_search = self.request.GET.get('list_type_search', None)
        list_name_search = self.request.GET.get('list_name_search', None)
        self.id_list = list_type_search
        context = {}
        
        if 'subprojects-' in list_type_search:
            all_subprojects = all_subprojects.filter(subproject_type_designation="Subproject")
            if all_subprojects.exists():
                _sql, _params = all_subprojects.query.get_compiler('default').as_sql()
                
                
                if list_type_search == 'subprojects-number':
                    #all_subprojects = all_subprojects.filter(subproject_type_designation="Subproject")
                    pass
                elif list_type_search == 'subprojects-completed':
                    list_name_search = _("Subprojects completed")
                    final_queryset = all_subprojects.raw(
                        f"""
                        SELECT DISTINCT sub_subp.id, sub_subp.full_title_of_approved_subproject 
                        FROM subprojects_subproject AS sub_subp 
                        LEFT JOIN subprojects_subproject AS sub_infras ON sub_subp.id=sub_infras.link_to_subproject_id 
                        WHERE (sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_COMPLETED_STATUS)}
                            AND (sub_infras.current_status_of_the_site IS NULL OR sub_infras.current_status_of_the_site IN {tuple(STRUCTURE_COMPLETED_STATUS)})) 
                            AND sub_subp.id IN (
                                SELECT sub.id FROM ({_sql}) AS sub 
                            )
                        """, _params
                    )
                    # all_subprojects = all_subprojects.filter(subproject_type_designation="Subproject", current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS)
                    all_subprojects = final_queryset #Subproject.objects.filter(id__in=[p.id for p in final_queryset])
                elif list_type_search == 'subprojects-in-progress':
                    list_name_search = _("Subprojects in progress")
                    final_queryset = all_subprojects.raw(
                        f"""
                        SELECT DISTINCT sub_subp.id, sub_subp.full_title_of_approved_subproject 
                        FROM subprojects_subproject AS sub_subp 
                        LEFT JOIN subprojects_subproject AS sub_infras ON sub_subp.id=sub_infras.link_to_subproject_id 
                        WHERE (((sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_NOT_START_STATUS*2)} 
                            AND sub_infras.current_status_of_the_site IN {tuple(STRUCTURE_COMPLETED_STATUS+STRUCTURE_IN_PROGRESS_STATUS)}) 
                            OR (sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_IN_PROGRESS_STATUS+STRUCTURE_COMPLETED_STATUS)} 
                            AND (sub_infras.current_status_of_the_site IN {tuple(STRUCTURE_NOT_START_STATUS+STRUCTURE_IN_PROGRESS_STATUS)}))
                            OR (sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_IN_PROGRESS_STATUS*2)})) 
                            AND sub_subp.id IN (
                                SELECT sub.id FROM ({_sql}) AS sub 
                            ))
                        """, _params
                    )
                    # all_subprojects = all_subprojects.filter(subproject_type_designation="Subproject", current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS)
                    all_subprojects = final_queryset #Subproject.objects.filter(id__in=[p.id for p in final_queryset])
                elif list_type_search == 'subprojects-not-started':
                    list_name_search = _("Subprojects not start")
                    final_queryset = all_subprojects.raw(
                        f"""
                        SELECT DISTINCT sub_subp.id 
                        FROM subprojects_subproject AS sub_subp 
                        LEFT JOIN subprojects_subproject AS sub_infras ON sub_infras.link_to_subproject_id=sub_subp.id AND sub_infras.subproject_type_designation='Infrastructure' 
                        WHERE (sub_subp.current_status_of_the_site NOT IN {tuple(STRUCTURE_IN_PROGRESS_STATUS+STRUCTURE_COMPLETED_STATUS)} 
                            AND (sub_infras.current_status_of_the_site IS NULL OR sub_infras.current_status_of_the_site NOT IN {tuple(STRUCTURE_IN_PROGRESS_STATUS+STRUCTURE_COMPLETED_STATUS)})) 
                            AND sub_subp.id IN (
                                SELECT sub.id FROM ({_sql}) AS sub 
                            )
                        """, _params
                    )
                    # all_subprojects = all_subprojects.filter(subproject_type_designation="Subproject").exclude(current_status_of_the_site__in=(STRUCTURE_COMPLETED_STATUS+STRUCTURE_IN_PROGRESS_STATUS))
                    all_subprojects = final_queryset #Subproject.objects.filter(id__in=[p.id for p in final_queryset])
                    
        elif list_type_search == 'infrastrutures':
            list_name_search = _("Structures/infrastructures without latrines and fences")
        elif list_type_search == 'infrastruture-completed':
            list_name_search = _("Structures/infrastructures completed (excluding latrines and fences)")
            all_subprojects = all_subprojects.filter(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS)
        elif list_type_search == 'infrastruture-in-progress':
            list_name_search = _("Structures/infrastructures in progress (excluding latrines and fences)")
            all_subprojects = all_subprojects.filter(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS)
        elif list_type_search == 'infrastruture-not-started':
            list_name_search = _("Structures/infrastructures not start (excluding latrines and fences)")
            all_subprojects = all_subprojects.exclude(current_status_of_the_site__in=(STRUCTURE_COMPLETED_STATUS+STRUCTURE_IN_PROGRESS_STATUS))
        
        elif 'infrastrutures-with-latrines-fences' in list_type_search:
            if list_type_search == 'infrastrutures-with-latrines-fences':
                list_name_search = _("Structures/infrastructures with latrines and fences")
            elif list_type_search == 'infrastrutures-with-latrines-fences-completed':
                list_name_search = _("Structures/infrastructures with latrines and fences completed")
                all_subprojects = all_subprojects.filter(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS)
            elif list_type_search == 'infrastrutures-with-latrines-fences-in-progress':
                list_name_search = _("Structures/infrastructures with latrines and fences in progress")
                all_subprojects = all_subprojects.filter(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS)
            elif list_type_search == 'infrastrutures-with-latrines-fences-not-started':
                list_name_search = _("Structures/infrastructures with latrines and fences not start")
                all_subprojects = all_subprojects.exclude(current_status_of_the_site__in=(STRUCTURE_COMPLETED_STATUS+STRUCTURE_IN_PROGRESS_STATUS))
            
            context['total'] = all_subprojects.count()
            # context['total_latrine_blocks'] = all_subprojects.filter(has_latrine_blocs=True).count()
            # context['total_fences'] = all_subprojects.filter(has_fence=True).count()
            context['total_infrastrutures'] = context['total'] #+ context['total_latrine_blocks'] + context['total_fences']
            # list_name_search += f"\
            #     ({context['total_latrine_blocks']}/{context['total_fences']})"
        
        elif 'latrines-and-fences' in list_type_search:
            all_subprojects = all_subprojects.filter(
                # Q(has_latrine_blocs=True) | Q(has_fence=True)
                )
            
            if list_type_search == 'latrines-and-fences':
                list_name_search = _("Latrines and fences")
            elif list_type_search == 'latrines-and-fences-completed':
                list_name_search = _("Latrines and fences completed")
                all_subprojects = all_subprojects.filter(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS)
            elif list_type_search == 'latrines-and-fences-in-progress':
                list_name_search = _("Latrines and fences in progress")
                all_subprojects = all_subprojects.filter(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS)
            elif list_type_search == 'latrines-and-fences-not-started':
                list_name_search = _("Latrines and fences not start")
                all_subprojects = all_subprojects.exclude(current_status_of_the_site__in=(STRUCTURE_COMPLETED_STATUS+STRUCTURE_IN_PROGRESS_STATUS))
            
            
            context['total'] = all_subprojects.count()
            # context['total_latrine_blocks'] = all_subprojects.filter(has_latrine_blocs=True).count()
            # context['total_fences'] = all_subprojects.filter(has_fence=True).count()
            context['total_infrastrutures'] = context['total'] #+ context['total_latrine_blocks'] + context['total_fences']
            # list_name_search += f"\
            #     ({context['total_latrine_blocks']}/{context['total_fences']})"
                
                
        else:
            all_subprojects = []
        if not list_name_search:
            list_name_search = self.title
        
        subprojects = self.get_queryset_search(all_subprojects)
        
        administrative_level_type = self.request.GET.get('administrative_level_type', 'All').title()

        context['subprojects'] = subprojects
        context['administrative_level_id'] = self.request.GET.getlist('administrative_level_id[]', [])
        context['administrative_level_type'] = "All" if administrative_level_type in ("", "null", "undefined") else administrative_level_type
        context['list_type_search'] = list_type_search
        
        context.update(ctx)
        context['title'] = list_name_search
        
        # return self.render_to_json_response(context, safe=False)
        return context