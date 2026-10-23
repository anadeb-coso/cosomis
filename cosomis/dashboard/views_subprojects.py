from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from cosomis.mixins import PageMixin, AJAXRequestMixin
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models import Sum, Max
from django.db import connection
import logging
from collections import defaultdict
from django.http import Http404

from subprojects.models import Subproject, Step, Project
from administrativelevels.models import AdministrativeLevel
from administrativelevels.functions import (
    get_administrative_level_ids_descendants, get_administrative_level_ids_descendants_with_dict,
    get_administrative_level_children_map,
)
from . import forms
from subprojects.forms import SubprojectFilterForm, SearchForm
from . import functions
from cosomis.views_manage_url_parse import redirect_user_to_login, redirect_to_an_url
from cosomis.constants import STRUCTURE_COMPLETED_STATUS, STRUCTURE_IN_PROGRESS_STATUS



class DashboardTemplateView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = 'dashboard_subprojects.html'
    active_level1 = 'dashboard_subprojects'
    title = _('Subprojects Dashboard')
    
    def get_context_data(self, **kwargs):
        ctx = super(DashboardTemplateView, self).get_context_data(**kwargs)
        ctx['hide_content_header'] = True
        ctx['form_adl'] = forms.AdministrativeLevelFilterForm()
        ctx['form_suproject'] = SubprojectFilterForm(False)
        ctx['form_searcht'] = SearchForm()
        return ctx


class DashboardSubprojectsMixin:

    table_class_style = 'table-striped table-secondary table-bordered'
    table_thead_class_style = 'bg-primary'

    def dispatch(self, request, *args, **kwargs):
        try:
            if not self.request.user.is_authenticated:
                return redirect_user_to_login(request)
            if not self.request.session.get('project_id'):
                return redirect_to_an_url(request, 'process_manager:list')
        except Exception:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super(DashboardSubprojectsMixin, self).get_context_data(**kwargs)
        ctx.setdefault('table_class_style', self.table_class_style)
        ctx.setdefault('table_thead_class_style', self.table_thead_class_style)
        return ctx

    def render_to_response(self, context, **response_kwargs):
        functions.plain_summary_tables(*context.get('summary', {}).values())
        return super().render_to_response(context, **response_kwargs)

    def get_projects_ids(self):
        """The project of the session, or the list of projects of "show for all
        projects" (all_projects[], as Subproject.objects.get_objects_by_general_filtre())."""
        all_projects = self.request.GET.getlist('all_projects[]')
        if len(all_projects) >= 2:
            return [int(project_id) for project_id in all_projects]
        return self.request.session.get('project_id')

    def get_columns_listes(self, queryset_results):
        """[id, name, ids of the level and of all its descendants] of each column
        (the administrative levels under the filtered ones), the whole tree loaded
        in a few queries."""
        if queryset_results['ald_filter_ids']:
            def get_descendants(column_id):
                return queryset_results['id_with_descendants'].get(str(column_id)) or []
        else:
            project_id = self.get_projects_ids()
            children_map = get_administrative_level_children_map(
                [column[0] for column in queryset_results['columns_tuples'] if column[0] != "All"], project_id
            )

            def get_descendants(column_id):
                if column_id == "All":
                    return get_administrative_level_ids_descendants(column_id, None, [], project_id)
                return get_administrative_level_ids_descendants(column_id, None, [], project_id, children_map=children_map)

        columns_listes = []
        for column in queryset_results['columns_tuples']:
            ids_descendants = get_descendants(column[0])
            columns_listes.append(
                [
                    column[0],
                    column[1],
                    [column[0]] + ids_descendants if column[0] != "All" else ids_descendants
                ]
            )
        return columns_listes

    def get_queryset(self):
        request = self.request

        # --- Récupération des paramètres ---
        administrative_level_ids_get = request.GET.getlist('administrative_level_id[]', [])
        administrative_level_type = request.GET.get('administrative_level_type', 'All').title()

        if administrative_level_type in ("", "null", "undefined"):
            administrative_level_type = "All"

        # --- Normalisation des IDs ---
        ald_filter_ids = [
            int(ald_id) for ald_id in administrative_level_ids_get
            if ald_id not in ("", "null", "undefined", "All")
        ]

        # "Show for all projects": the administrative levels (columns and their
        # descendants) of all the projects, as the subprojects counted.
        projects_ids = self.get_projects_ids()

        id_with_descendants = dict()
        # id_with_first_descendants = dict()
        administrative_levels_ids = set()
        for ald_id in ald_filter_ids:  # si vide, on met 0
            _ids, _ids_with_desc, _id_with_first_desces = get_administrative_level_ids_descendants_with_dict(
                ald_id, administrative_level_type, [], {}, {}, projects_ids
            )
            administrative_levels_ids.update(
                _ids
            )
            id_with_descendants.update(**_ids_with_desc)
            # id_with_first_descendants.update(**_id_with_first_desces)

        # --- Filtrage des AdministrativeLevels ---
        if isinstance(projects_ids, list):
            adl_qs = AdministrativeLevel.objects.filter(administrative_levels_projects__in=projects_ids).distinct()
        else:
            adl_qs = AdministrativeLevel.objects.get_objects_by_general_filtre(request, None)

        if administrative_level_type == "All":
            administrative_levels = adl_qs.filter(type="Region").prefetch_related()
        elif ald_filter_ids:
            administrative_levels = adl_qs.filter(parent__id__in=ald_filter_ids).prefetch_related()
        elif administrative_level_type:
            administrative_levels = adl_qs.filter(parent__type=administrative_level_type).prefetch_related()
        else:
            administrative_levels = adl_qs.none()

        # Si aucun niveau trouvé, on fallback sur les ald_filter_ids
        if not administrative_levels.exists() and ald_filter_ids:
            administrative_levels = adl_qs.filter(id__in=ald_filter_ids).prefetch_related()

        # --- Subprojects --- (status, dates, component, sector, type, works type and all projects filters)
        subprojects = functions.filter_dashboard_subprojects(
            Subproject.objects.get_objects_by_general_filtre(request, None).prefetch_related().get_actifs(), request
        )

        if ald_filter_ids:
            adls = ald_filter_ids + list(administrative_levels_ids)
            subprojects = subprojects.filter(
                Q(location_subproject_realized__id__in=adls) |
                Q(canton__id__in=adls)
            )

        # --- Sectors distincts ---
        sectors = subprojects.values_list('subproject_sector', flat=True).distinct().order_by()

        # --- Administrative level choisi ---
        administrative_level = administrative_levels.first()
        adl_type = administrative_level.type if administrative_level else ""

        # --- Colonnes disponibles ---
        columns_tuples = (
            administrative_levels
            .filter(Q(type=adl_type) if adl_type else Q())
            .order_by('name')
            .values_list('id', 'name')
        )

        return {
            'subprojects': subprojects,
            'sectors': sorted(sectors, key=lambda sector: sector or ''),
            'administrative_level_type': adl_type,
            'columns_tuples': list(columns_tuples),
            'ald_filter_ids': ald_filter_ids,
            'administrative_levels_ids': list(administrative_levels_ids),
            'id_with_descendants': id_with_descendants,
            # 'id_with_first_descendants': id_with_first_descendants
        }
        # administrative_level_ids_get = self.request.GET.getlist('administrative_level_id[]', None)
        # administrative_level_type = self.request.GET.get('administrative_level_type', 'All').title()
        
        # administrative_level_type = "All" if administrative_level_type in ("", "null", "undefined") else administrative_level_type

        # ald_filter_ids = []
        # administrative_levels_ids = []
        # if not administrative_level_ids_get:
        #     administrative_level_ids_get.append("")
        # for ald_id in administrative_level_ids_get:
        #     ald_id = 0 if ald_id in ("", "null", "undefined", "All") else ald_id
        #     administrative_levels_ids += get_administrative_level_ids_descendants(
        #         ald_id, administrative_level_type, [], self.request.session.get('project_id')
        #     )
        #     if ald_id:
        #         ald_filter_ids.append(ald_id)

        # administrative_levels_ids = list(set(administrative_levels_ids))
        # administrative_levels = [] #AdministrativeLevel.objects.filter(id__in=administrative_levels_ids)
        # if administrative_level_type == "All":
        #     administrative_levels = AdministrativeLevel.objects.get_objects_by_general_filtre(self.request, None).filter(type="Region").prefetch_related()
        # elif ald_filter_ids and administrative_level_type != "All":
        #     administrative_levels = AdministrativeLevel.objects.get_objects_by_general_filtre(self.request, None).filter(parent__id__in=ald_filter_ids).prefetch_related()
        # elif administrative_level_type:
        #     administrative_levels = AdministrativeLevel.objects.get_objects_by_general_filtre(self.request, None).filter(parent__type=administrative_level_type).prefetch_related()
        
        # if not administrative_levels:
        #     administrative_levels = AdministrativeLevel.objects.get_objects_by_general_filtre(self.request, None).filter(id__in=ald_filter_ids).prefetch_related()

        # subprojects = Subproject.objects.get_objects_by_general_filtre(self.request, None).prefetch_related().get_objects_by_general_filtre(self.request, None).get_actifs()

        # sectors = sorted(list(set(list(subprojects.values_list('subproject_sector')))))
        
        # if not ald_filter_ids:
        #     pass
        # else:
        #     adls = ald_filter_ids + administrative_levels_ids
        #     subprojects = subprojects.filter(
        #         Q(location_subproject_realized__id__in=adls) | 
        #         Q(canton__id__in=adls)
        #     )
        # administrative_level = administrative_levels.first()

        
        # return {
        #     'subprojects': subprojects,
        #     'sectors': [s[0] for s in sectors],
        #     'administrative_level_type': administrative_level.type if administrative_level else "",
        #     'columns_tuples': list(administrative_levels.filter(Q(type=administrative_level.type)if administrative_level else Q()).order_by('name').values_list('id', 'name')),
        #     'ald_filter_ids': ald_filter_ids,
        #     'administrative_levels_ids': administrative_levels_ids
        # }
    

class DashboardSubprojectsListView(DashboardSubprojectsMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'tracking.html'
    context_object_name = 'queryset_results'
    
    def summary_subprojects_by_sectors_1(self, columns_listes, sectors, all_subprojects, characters_length):
        datas = {
            _("Sectors"): {},
            _("Type"): {}
        }

        # Préparer les colonnes dynamiques
        for _id, col_name, __id in columns_listes:
            datas[col_name] = {}

        datas[_("Total")] = {}

        # Doubler les secteurs pour "Number of subprojects" et "Number of subproject infrastructures"
        sector_pairs = []
        for s in sectors:
            sector_pairs.extend([s, s])

        # The numbers of every (sector, row type, column) from one pass over the
        # subprojects (they were scanned again for every sector and column).
        columns_by_adl = defaultdict(set)
        for index, (_id, col_name, col_ids) in enumerate(columns_listes):
            for adl_id in col_ids:
                columns_by_adl[adl_id].add(index)
        numbers = defaultdict(int)  # (sector, infrastructures row, column index) -> number
        for pk, location_id, canton_id, sector, number_of_infrastructures, designation in all_subprojects.values_list(
            'pk', 'location_subproject_realized_id', 'canton_id', 'subproject_sector',
            'number_of_infrastructures', 'subproject_type_designation'
        ):
            matched_columns = columns_by_adl.get(location_id, set()) | columns_by_adl.get(canton_id, set())
            for index in matched_columns:
                if designation in ["Subproject"]:
                    numbers[(sector, False, index)] += 1
                if number_of_infrastructures == 1 and designation in ["Infrastructure", "Subproject"]:
                    numbers[(sector, True, index)] += 1

        count = 0
        for i, sector in enumerate(sector_pairs):
            datas[_("Sectors")][count] = sector
            datas[_("Type")][count] = _("Number of subproject infrastructures") if (i + 1) % 2 == 0 else _("Number of subprojects")

            number_total = 0
            # Filtrer les sous-projets pertinents pour ce secteur et type
            for index, (_id, col_name, col_ids) in enumerate(columns_listes):
                number = numbers.get((sector, (i + 1) % 2 == 0, index), 0)
                datas[col_name][count] = number
                number_total += number

            datas[_("Total")][count] = number_total
            count += 1

        # Ajouter les lignes "Total"
        total_lines = [
            (_("Total"), _("Number of subprojects")),
            (_("Total"), _("Number of subproject infrastructures")),
            (_("Total"), _("All"))
        ]
        for i, (sector_label, type_label) in enumerate(total_lines):
            datas[_("Sectors")][count + i] = sector_label
            datas[_("Type")][count + i] = type_label

            # Calculer les totaux pour chaque colonne
            for col_name in datas.keys():
                if col_name not in [_("Sectors"), _("Type")]:
                    if i < 2:
                        datas[col_name][count + i] = functions.sum_dict_value(datas[col_name], count, pair=bool(i))
                    else:
                        datas[col_name][count + i] = functions.sum_dict_value(datas[col_name], count, pair=True)

        return {
            'title': _("Number of sub-projects by administrative level and sector"),
            'datas': datas,
            'length_loop': range(0, count + 3),
            'values': list(datas.values())
        }

    # def summary_subprojects_by_sectors_1(self, columns_listes, sectors, all_subprojects, characters_length):
    #     datas = {
    #         _("Sectors"): {},
    #         _("Type"): {}
    #     }
    #     for column in columns_listes:
    #         datas[column[1]] = {}
            
    #     datas[_("Total")] = {}
    #     # datas[_("OBSERVATIONS")] = {}

    #     count = 0
    #     number_toal = 0
    #     _sectors = []
    #     for s in sectors:
    #         _sectors.append(s)
    #         _sectors.append(s)
            
    #     for i in range(len(_sectors)):
    #         datas[_("Sectors")][count] = _sectors[i]
    #         if (i+1)%2 == 0:
    #             datas[_("Type")][count] = _("Number of subproject infrastructures")
    #         else:
    #             datas[_("Type")][count] = _("Number of subprojects")

    #         number_toal = 0
    #         for column in columns_listes:
    #             number = 0
    #             for _subp in all_subprojects:
    #                 if (_subp.location_subproject_realized_id in column[2] or \
    #                     _subp.canton_id in column[2]) and _subp.subproject_sector == _sectors[i] and \
    #                     _subp.subproject_type_designation in (["Infrastructure", "Subproject"] if (i+1)%2 == 0 else ["Subproject"]):
    #                     number += 1
                        
    #             datas[column[1]][count] = number
    #             number_toal += number

    #         datas[_("Total")][count] = number_toal #str(number_toal).rjust(characters_length,'0')
    #         count += 1

    #     datas[_("Sectors")][count] = _("Total")
    #     datas[_("Sectors")][count+1] = _("Total")
    #     datas[_("Sectors")][count+2] = _("Total")
    #     datas[_("Type")][count] = _("Number of subprojects")
    #     datas[_("Type")][count+1] = _("Number of subproject infrastructures")
    #     datas[_("Type")][count+2] = _("All")

    #     # All sum
    #     columns_skip = [
    #         _("Sectors"),
    #         _("Type"),
    #         # _("OBSERVATIONS")
    #     ]
    #     for i in range(3):
    #         for k_data in datas.keys():
    #             _sum = 0
    #             if k_data not in columns_skip:
    #                 _sum = functions.sum_dict_value(datas[k_data], count, pair=bool(i) if i < 2 else True)
    #             if _sum:
    #                 datas[k_data][count+i] = _sum #str(_sum).rjust(characters_length,'0')
    #     # End All sum

    #     return {
    #         'title': _("Number of sub-projects by administrative level and sector"),
    #         'datas': datas,
    #         'length_loop': range(0, count+3),
    #         'values': list(datas.values())
    #     }



    def get_context_data(self, **kwargs):
        ctx = super(DashboardSubprojectsListView, self).get_context_data(**kwargs)
        # subprojects = ctx['queryset_results']['subprojects']
        sectors = ctx['queryset_results']['sectors'].copy()
        columns_listes = self.get_columns_listes(ctx['queryset_results'])
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

        # The numbers and amounts of every sector and column from one pass over
        # the subprojects (two queries per sector, then a scan per column, before).
        columns_by_adl = defaultdict(set)
        for index, column in enumerate(columns_listes):
            for adl_id in column[2]:
                columns_by_adl[adl_id].add(index)
        number_subprojects = defaultdict(int)
        number_infrastructures = defaultdict(int)
        amounts = {}  # (sector, column index) -> estimated cost, added in the subprojects order as before
        for pk, location_id, canton_id, sector, designation, cost in all_subprojects.values_list(
            'pk', 'location_subproject_realized_id', 'canton_id', 'subproject_sector',
            'subproject_type_designation', 'estimated_cost'
        ):
            if designation == "Subproject":
                number_subprojects[sector] += 1
            if designation in ["Infrastructure", "Subproject"]:
                number_infrastructures[sector] += 1
                if cost:
                    for index in columns_by_adl.get(location_id, set()) | columns_by_adl.get(canton_id, set()):
                        amounts[(sector, index)] = amounts.get((sector, index), 0) + cost

        count = 0
        _sectors = sectors

        for i in range(len(_sectors)):
            datas[_("Sectors")][count] = _sectors[i]

            datas[_("Number of subprojects")][count] = number_subprojects[_sectors[i]]
            datas[_("Number of subproject infrastructures")][count] = number_infrastructures[_sectors[i]]

            toal_mount = 0
            for index, column in enumerate(columns_listes):
                estimated_cost = amounts.get((_sectors[i], index), 0)
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
        sectors = ctx['queryset_results']['sectors'].copy()
        columns_listes = self.get_columns_listes(ctx['queryset_results'])
        all_subprojects = ctx['queryset_results']['subprojects']

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
        # The village, canton and region of every row, and the current step of
        # the rows without a level of realization, loaded in a few queries (up to
        # seven queries per subproject before); same order (number, joint number
        # are unique). The history JSON fields, costly to decode, aren't shown.
        all_subprojects = list(
            all_subprojects.order_by('number', 'joint_subproject_number')
            .defer('create_by_user', 'update_by_user', 'delete_by_user', 'users_involved', 'priority')
            .prefetch_related(*Subproject.location_prefetches())
        )
        Subproject.prefetch_display_data(all_subprojects)

        for subproject in all_subprojects:
            datas[_("N°")][count] = subproject.number
            canton = None
            village = subproject.get_village()
            
            try:
                canton = subproject.get_canton()
                datas[_("Region")][count] = canton.parent.parent.parent.name if canton else "-"
            except:
                datas[_("Region")][count] = "-"
            
            
            datas[_("Sites")][count] = village.name if village and village != "CCD" else (f'{canton.name} ({_("Canton")})' if village == "CCD" and canton else "-")

            datas[_("Structures")][count] = (
                subproject.full_title_of_approved_subproject \
                    if subproject.subproject_type_designation_id != "Infrastructure" else \
                    subproject.type_of_subproject_id
            )
            datas[_("Companies")][count] = subproject.name_of_the_awarded_company_works_companies if subproject.name_of_the_awarded_company_works_companies else "-"
            datas[_("Estimated cost") + " FCFA"][count] = subproject.estimated_cost if subproject.estimated_cost else 0
            datas[_("Amount FCFA TTC")][count] = subproject.contract_amount_work_companies if subproject.contract_amount_work_companies else 0
            
            if subproject.current_level_of_physical_realization_of_the_work_percent:
                datas[_("Level of realization") + " %"][count] = int(subproject.current_level_of_physical_realization_of_the_work_percent)
            else:
                step_level = subproject.get_current_subproject_step_and_level_object
                datas[_("Level of realization") + " %"][count] = step_level.percent if step_level and step_level.percent else 0
            
            if subproject.current_level_of_physical_realization_of_the_work_wording:
                datas[_("Physical level")][count] = subproject.current_level_of_physical_realization_of_the_work_wording
            else:
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
        table_title = self.request.GET.get('table_title')
        return {
            'title': table_title if table_title else _("Subprojects by village, sector and step"),
            'datas': datas,
            'length_loop': range(0, count+1),
            'values': list(datas.values())
        }


    def get_context_data(self, **kwargs):
        ctx = super(DashboardSubprojectsSectorsAndStepsListView, self).get_context_data(**kwargs)
        # adls = (ctx['queryset_results']['ald_filter_ids'] + ctx['queryset_results']['administrative_levels_ids']).copy()
        all_subprojects = ctx['queryset_results']['subprojects']
        # all_subprojects = Subproject.objects.get_objects_by_general_filtre(self.request, None).filter(
        #         Q(location_subproject_realized__id__in=adls) | 
        #         Q(canton__id__in=adls)
        #     ).get_actifs()
        
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
        
        count = 0

        # for step in Step.objects.all():
        #     datas[_("Step")][count] = step.__str__()

        #     datas[_("Number")][count] = all_subprojects.filter_by_steps_already_track(Subproject, step_id=step.id).count() #all_subprojects.filter(subprojectstep__step__id=step.id).count() #all_subprojects.filter_by_steps_already_track(Subproject, step_id=step.id).count()
        
        #     count += 1
        rows_label = {
            "not_strated": _("Not started"),
            "in_progress": _("In progress"),
            "completed": _("Completed"),
            "technical_acceptance": _("Technical reception"),
            "provisional_acceptance": _("Provisional reception"),
            "handover_to_the_community": _("Final reception")
        }
        for k, v in rows_label.items():
            datas[_("Step")][count] = v
            count += 1
            
        # With the pk: one row per subproject even when the queryset is distinct.
        statuses = [status for pk, status in all_subprojects.values_list('pk', 'current_status_of_the_site')]
        for current_status_of_the_site in statuses:
            if current_status_of_the_site in STRUCTURE_IN_PROGRESS_STATUS:
                datas[_("Number")][1] = (1 if datas[_("Number")].get(1) == None else datas[_("Number")].get(1) + 1)

            elif current_status_of_the_site in STRUCTURE_COMPLETED_STATUS:
                datas[_("Number")][2] = (1 if datas[_("Number")].get(2) == None else datas[_("Number")].get(2) + 1)
                if current_status_of_the_site == "Réception technique":
                    datas[_("Number")][3] = (1 if datas[_("Number")].get(3) == None else datas[_("Number")].get(3) + 1)
                elif current_status_of_the_site == "Réception provisoire":
                    datas[_("Number")][4] = (1 if datas[_("Number")].get(4) == None else datas[_("Number")].get(4) + 1)
                elif current_status_of_the_site == "Réception définitive":
                    datas[_("Number")][5] = (1 if datas[_("Number")].get(5) == None else datas[_("Number")].get(5) + 1)
            
            else:
                datas[_("Number")][0] = (1 if datas[_("Number")].get(0) == None else datas[_("Number")].get(0) + 1)

        datas[_("Step")][count] = _("Number of infrastructures")
        datas[_("Number")][count] = len(statuses)

#         administrative_levels_ids_str = ', '.join(str(elt) for elt in administrative_levels_ids)
#         count = 0
#         with connection.cursor() as cursor:
#             try:
#                 cursor.execute("""
# SELECT s.wording, COUNT(subp_subp_step.subp_id) FROM subprojects_step s 
# LEFT JOIN (
#     SELECT subp.id subp_id, subp_step.step_id subp_step_step_id FROM subprojects_subprojectstep subp_step 
#     INNER JOIN subprojects_subproject subp ON subp_step.subproject_id=subp.id 
#     WHERE subp.location_subproject_realized_id IN (%s) OR subp.canton_id IN (%s)
#     ) subp_subp_step ON s.id=subp_subp_step.subp_step_step_id 
# GROUP BY s.id
# """ % (administrative_levels_ids_str, administrative_levels_ids_str))
                
#                 for row in cursor.fetchall():
#                     datas[_("Step")][count] = row[0]
#                     datas[_("Number")][count] = row[1]
#                     count += 1
                    
#             except Exception as exc:
#                 logging.exception(exc)


        return {
            'title': _("Number of infrastructures by status"),
            'datas': datas,
            'length_loop': range(0, count+1),
            'values': list(datas.values())
        }
    


    def get_context_data(self, **kwargs):
        ctx = super(DashboardSubprojectsStepsAlreadyTrackListView, self).get_context_data(**kwargs)
        all_subprojects = ctx['queryset_results']['subprojects']
        
        ctx["summary"] = {}

        characters_length = 3
        ctx["summary"]["summary_subprojects_by_steps_already_track"] = {}
        for k, v in self.summary_subprojects_by_steps_already_track(all_subprojects, characters_length, ctx['queryset_results']['administrative_levels_ids'].copy()).items():
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

            
        # Sanitiser en entiers et éviter `IN ()` (erreur de syntaxe SQL, PG et MySQL)
        _ids = [int(e) for e in administrative_levels_ids
                if str(e).strip().lstrip('-').isdigit()]
        administrative_levels_ids_str = ', '.join(str(e) for e in _ids)
        count = 0
        with connection.cursor() as cursor:
          if _ids:
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
        for k, v in self.summary_subprojects_by_current_steps(all_subprojects, characters_length, ctx['queryset_results']['administrative_levels_ids'].copy()).items():
            ctx["summary"]["summary_subprojects_by_current_steps"][k] = v

        ctx["queryset_results"]["administrative_level_type"] = None

        return ctx