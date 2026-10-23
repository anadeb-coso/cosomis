from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from cosomis.mixins import PageMixin, AJAXRequestMixin, ModalListMixin, JSONResponseMixin
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Case, When, IntegerField, Max, Prefetch
from django.db.models.functions import Upper
from django.db.models.query import QuerySet, RawQuerySet
from datetime import datetime
from collections import defaultdict
from django.db import connection
import logging
from django.http import Http404

from subprojects.models import Subproject, Step, Component, Project, SubprojectStep, Level
from administrativelevels.models import AdministrativeLevel
from financial.models.allocation import AdministrativeLevelAllocation
from process_manager.models import AdministrativeLevelWave
from administrativelevels.functions import (
    get_administrative_level_ids_descendants, get_administrative_level_ids_descendants_with_dict,
    get_administrative_level_children_map,
)
from . import forms
from .functions import plain_summary_tables, filter_dashboard_subprojects
from subprojects.forms import SubprojectFilterForm, SearchForm
from cosomis.constants import (
    TYPES_OF_STRUCTURE_COLOR, STRUCTURE_COMPLETED_STATUS, STRUCTURE_IN_PROGRESS_STATUS,
    STRUCTURE_NOT_START_STATUS, SUB_PROJECT_SECTORS_COLOR, OTHER_STRUCUTURES,
    SUB_PROJECT_STATUS_COLOR_TRANSLATE, FINANCING_COLOR, STRUCTURE_PROVISIONAL_ACCEPTANCE_STATUS,
    STRUCTURE_FINAL_ACCEPTANCE_STATUS, TYPES_OF_SUB_PROJECT_COLOR, IN_PROGRESS_RANKING,
    COMPLETED_RANKING
)
from cosomis.views_manage_url_parse import redirect_user_to_login, redirect_to_an_url


def _sql_in(values):
    """Rend une liste Python en fragment SQL `('a', 'b', ...)` pour une clause IN.

    `str(tuple(...))` met des guillemets DOUBLES autour des chaînes contenant
    une apostrophe (repr Python) — PostgreSQL les interprète alors comme des
    identifiants de colonne. Ici : guillemets simples, apostrophes doublées.
    """
    vals = list(values)
    if not vals:
        return "(NULL)"
    return "(" + ", ".join("'" + str(v).replace("'", "''") + "'" for v in vals) + ")"


def _rows_per_subproject(subprojects):
    """Rows to GROUP BY so that each group gets the same total as .count() or
    .aggregate() on `subprojects` filtered to that group: like Django does for
    these on a distinct queryset (joined to the subproject steps by the date
    filters), a distinct `subprojects` is first reduced to one row per subproject."""
    if subprojects.query.distinct:
        return Subproject.objects.filter(pk__in=subprojects.values('pk'))
    return subprojects


def _subprojects_for_display(subprojects):
    """`subprojects` (queryset, raw queryset or list) as a list in the same
    order, with everything the details table reads loaded in a few queries
    (a raw queryset only loads the id: every other field was read with one query)."""
    if isinstance(subprojects, RawQuerySet):
        ids = [subproject.id for subproject in subprojects]
        loaded = Subproject.objects.prefetch_related(*Subproject.location_prefetches()).in_bulk(ids)
        subprojects = [loaded[pk] for pk in ids]
    elif isinstance(subprojects, QuerySet):
        subprojects = list(subprojects.prefetch_related(*Subproject.location_prefetches()))
    else:
        subprojects = list(subprojects)
    Subproject.prefetch_display_data(subprojects)
    return subprojects


class DashboardTemplateView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = 'dashboard_summary.html'
    active_level1 = 'dashboard_summary'
    title = _('Dashboard')
    
    def get_context_data(self, **kwargs):
        ctx = super(DashboardTemplateView, self).get_context_data(**kwargs)
        ctx['hide_content_header'] = True
        ctx['form_adl'] = forms.AdministrativeLevelFilterForm()
        ctx['form_suproject'] = SubprojectFilterForm(False)
        ctx['form_searcht'] = SearchForm()
        return ctx


class DashboardSubprojectsMixin(ModalListMixin):

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
    
    def filter_list_by_delete_empty(self, _list):
        if _list:
            return [elt for elt in _list if elt]
        else:
            return []
    
    def parse_fr_date(self, value):
        if not value:
            return None
        try:
            return datetime.strptime(value.strip(), "%d/%m/%Y").date()
        except ValueError:
            return None

    def get_datas_on_request_get(self):
        ctx = {}

        ctx['administrative_level_id'] = self.request.GET.getlist('administrative_level_id[]', [])
        administrative_level_type = self.request.GET.get('administrative_level_type', 'All').title()
        ctx['subproject_sectors'] = self.filter_list_by_delete_empty(self.request.GET.getlist('id_subproject_sectors[]'))
        ctx['subproject_types'] = self.filter_list_by_delete_empty(self.request.GET.getlist('id_subproject_types[]'))
        ctx['works_type_of_subprojects'] = self.filter_list_by_delete_empty(self.request.GET.getlist('id_works_type_of_subproject[]'))
        ctx['subproject_steps'] = self.filter_list_by_delete_empty(self.request.GET.getlist('id_subproject_step[]'))
        ctx['components_names'] = self.filter_list_by_delete_empty(self.request.GET.getlist('id_components[]'))
        ctx['start_date_raw'] = self.request.GET.get('start_date', None)
        ctx['end_date_raw'] = self.request.GET.get('end_date', None)

        ctx['all_projects'] = self.request.GET.getlist('all_projects[]') if type(self.request.GET.getlist('all_projects[]')) is list and len(self.request.GET.getlist('all_projects[]')) >= 2 else []

        ctx['administrative_level_type'] = "All" if administrative_level_type in ("", "null", "undefined") else administrative_level_type
        
        return ctx
        
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

        id_with_descendants = dict()
        administrative_levels_ids = set()
        # id_with_first_descendants = dict()
        for ald_id in ald_filter_ids:  # si vide, on met 0
            _ids, _ids_with_desc, _id_with_first_desces = get_administrative_level_ids_descendants_with_dict(
                ald_id, administrative_level_type, [], {}, {}, request.session.get('project_id')
            )
            administrative_levels_ids.update(
                _ids
            )
            id_with_descendants.update(**_ids_with_desc)
            # id_with_first_descendants.update(**_id_with_first_desces)

        # --- Filtrage des AdministrativeLevels ---
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

        # --- Subprojects ---
        subprojects = filter_dashboard_subprojects(
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

    # def get_queryset(self):

    #     administrative_level_ids_get = self.request.GET.getlist('administrative_level_id[]', None)
    #     administrative_level_type = self.request.GET.get('administrative_level_type', 'All').title()
        
    #     administrative_level_type = "All" if administrative_level_type in ("", "null", "undefined") else administrative_level_type

    #     ald_filter_ids = []
    #     administrative_levels_ids = []
    #     if not administrative_level_ids_get:
    #         administrative_level_ids_get.append("")
    #     for ald_id in administrative_level_ids_get:
    #         ald_id = 0 if ald_id in ("", "null", "undefined", "All") else ald_id
    #         administrative_levels_ids += get_administrative_level_ids_descendants(
    #             ald_id, administrative_level_type, [], self.request.session.get('project_id')
    #         )
    #         if ald_id:
    #             ald_filter_ids.append(ald_id)

    #     administrative_levels_ids = list(set(administrative_levels_ids))
    #     administrative_levels = [] #AdministrativeLevel.objects.filter(id__in=administrative_levels_ids)
    #     if administrative_level_type == "All":
    #         administrative_levels = AdministrativeLevel.objects.get_objects_by_general_filtre(self.request, None).filter(type="Region").prefetch_related()
    #     elif ald_filter_ids and administrative_level_type != "All":
    #         administrative_levels = AdministrativeLevel.objects.get_objects_by_general_filtre(self.request, None).filter(parent__id__in=ald_filter_ids).prefetch_related()
    #     elif administrative_level_type:
    #         administrative_levels = AdministrativeLevel.objects.get_objects_by_general_filtre(self.request, None).filter(parent__type=administrative_level_type).prefetch_related()
        
    #     if not administrative_levels:
    #         administrative_levels = AdministrativeLevel.objects.get_objects_by_general_filtre(self.request, None).filter(id__in=ald_filter_ids).prefetch_related()

    #     subprojects = Subproject.objects.get_objects_by_general_filtre(self.request, None).prefetch_related().get_actifs()

    #     sectors = sorted(list(set(list(subprojects.values_list('subproject_sector')))))
        
    #     if not ald_filter_ids:
    #         pass
    #     else:
    #         adls = ald_filter_ids + administrative_levels_ids
    #         subprojects = subprojects.filter(
    #             Q(location_subproject_realized__id__in=adls) | 
    #             Q(canton__id__in=adls)
    #         )
    #     administrative_level = administrative_levels.first()

        
    #     return {
    #         'subprojects': subprojects,
    #         'sectors': sorted([s[0] for s in sectors]),
    #         'administrative_level_type': administrative_level.type if administrative_level else "",
    #         'columns_tuples': list(administrative_levels.filter(Q(type=administrative_level.type)if administrative_level else Q()).order_by('name').values_list('id', 'name')),
    #         'ald_filter_ids': ald_filter_ids,
    #         'administrative_levels_ids': administrative_levels_ids
    #     }
    

class DashboardSubprojectsListView(DashboardSubprojectsMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'components/dashboard_summary_subprojects.html'
    context_object_name = 'queryset_results'

    def get_context_data(self, **kwargs):
        ctx = super(DashboardSubprojectsListView, self).get_context_data(**kwargs)
        all_subprojects_include_infrastructures = ctx['queryset_results']['subprojects']
        all_infrastructures = ctx['queryset_results']['subprojects'].filter(number_of_infrastructures=1)
        sectors = ctx['queryset_results']['sectors'].copy()

        # Every count of the cards in one query (one query per count before).
        totals = _rows_per_subproject(all_subprojects_include_infrastructures).aggregate(
            total=Count('id', filter=Q(number_of_infrastructures=1)),
            total_without_link=Count('id', filter=Q(link_to_subproject=None, subproject_type_designation="Subproject")),
            total_subproject=Count('id', filter=Q(subproject_type_designation="Subproject")),
            total_infrastruture=Count('id', filter=Q(number_of_infrastructures=1, subproject_type_designation="Infrastructure")),
            total_infrastruture_in_progress=Count('id', filter=Q(number_of_infrastructures=1, current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS)),
            total_infrastruture_completed=Count('id', filter=Q(number_of_infrastructures=1, current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS)),
        )

        ctx['total'] = totals['total']
        ctx['total_without_link'] = totals['total_without_link']
        ctx['total_subproject'] = totals['total_subproject']
        ctx['total_infrastruture'] = totals['total_infrastruture']
        ctx['total_infrastrutures'] = ctx['total']

        _s = all_subprojects_include_infrastructures.filter(subproject_type_designation="Subproject")

        # Subprojects, infrastructures and costs by sector in one GROUP BY over
        # the same rows as the three GROUP BY it replaces.
        by_sector = (
            all_subprojects_include_infrastructures
            .values('subproject_sector')
            .annotate(
                subprojects=Count('id', filter=Q(subproject_type_designation="Subproject")),
                infrastructures=Count('id', filter=Q(number_of_infrastructures=1)),
                total_estimated_cost=Sum('estimated_cost'),
            )
        )
        subprojects_dict = {}
        infrastructures_dict = {}
        costs_dict = {}
        for entry in by_sector:
            subprojects_dict[entry['subproject_sector']] = entry['subprojects']
            infrastructures_dict[entry['subproject_sector']] = entry['infrastructures']
            costs_dict[entry['subproject_sector']] = entry['total_estimated_cost'] or 0

        if ctx['total_subproject']:  # _s.exists()
            _sql, _params = _s.query.get_compiler('default').as_sql()

            # A subproject (all the rows sharing its joint_subproject_number) is
            # completed when all its rows are, not started when none has started.
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    SELECT
                        COUNT(*) FILTER (WHERE not_completed = 0),
                        COUNT(*) FILTER (WHERE not_not_started = 0)
                    FROM (
                        SELECT
                            SUM((current_status_of_the_site NOT IN {_sql_in(STRUCTURE_COMPLETED_STATUS)})::int) AS not_completed,
                            SUM((current_status_of_the_site NOT IN {_sql_in(STRUCTURE_NOT_START_STATUS*2)})::int) AS not_not_started
                        FROM subprojects_subproject
                        WHERE (infrastructure_deleted IS NULL OR infrastructure_deleted = FALSE) AND id IN (SELECT sub.id FROM ({_sql}) AS sub)
                        GROUP BY joint_subproject_number
                    ) AS by_joint_number
                """, _params)
                ctx['total_subproject_completed'], ctx['total_subproject_not_started'] = cursor.fetchone()

            ctx['total_subproject_in_progress'] = ctx['total_subproject'] - (ctx['total_subproject_not_started'] + ctx['total_subproject_completed'])


            ctx['total_infrastruture_in_progress'] = totals['total_infrastruture_in_progress']
            ctx['total_infrastruture_completed'] = totals['total_infrastruture_completed']
            ctx['total_infrastruture_not_started'] = ctx['total'] - (ctx['total_infrastruture_in_progress'] + ctx['total_infrastruture_completed'])

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
                        'data': [subprojects_dict.get(sector, 0) for sector in sectors]
                    },
                    {
                        'label': _("Infrastructure"),
                        'backgroundColor': 'blue',
                        'data': [infrastructures_dict.get(sector, 0) for sector in sectors]
                    },
                    {
                        'label': _("Infras with latrines/fences"),
                        'backgroundColor': 'green',
                        'data': [infrastructures_dict.get(sector, 0) for sector in sectors]
                    }
                ]
            }


            ctx['amount_subproject_infrastrutures'] = {
                'title': _("Amount of subprojects selected in relation to infrastructure by sector"),
                'labels': sectors,
                'bars': [
                    {
                        'label': _("Infrastructure"),
                        'backgroundColor': 'blue',
                        'data': [costs_dict.get(sector, 0) for sector in sectors]
                    }
                ]
            }


            #Structure Graphe
            type_structures = list(TYPES_OF_SUB_PROJECT_COLOR.keys())
            ctx['type_structures'] = type_structures

            # Structures and completed structures by type of structure, one GROUP BY
            counts_dict = {}
            completed_counts_dict = {}
            for entry in all_infrastructures.values('type_of_subproject').annotate(
                total=Count('id'),
                completed=Count('id', filter=Q(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS)),
            ):
                counts_dict[entry['type_of_subproject']] = entry['total']
                if entry['completed']:
                    completed_counts_dict[entry['type_of_subproject']] = entry['completed']

            # Construction finale des données pour le graphique
            bars_type_structures = [
                {
                    'label': _("Structure"),
                    'backgroundColor': 'blue',
                    'data': [counts_dict.get(ts, 0) for ts in type_structures],
                },
                {
                    'label': _("Completed"),
                    'backgroundColor': 'green',
                    'data': [completed_counts_dict.get(ts, 0) for ts in type_structures],
                }
            ]
            ctx['bars_type_structures'] = bars_type_structures
            ctx['sum_bars_type_structures'] = [sum(elt.get('data')) for elt in bars_type_structures]
            ctx['number_structures_by_type'] = {
                'title': _("Structures by type"),
                'labels': type_structures,
                'bars': [bars_type_structures[0], bars_type_structures[1]]
            }


            #Summary Recap

            # --- Préparer le dictionnaire de datas ---
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

            recap_sectors = [(s or '').upper() for s in sectors]

            # The counts of every (sector, type of structure) in one GROUP BY
            # instead of two queries per sector. The sectors are matched in upper
            # case: an exact `subproject_sector = 'EDUCATION'` matched "Education"
            # on MySQL (case-insensitive collation) but matches nothing on
            # PostgreSQL, which left this table empty.
            recap_by_sector = defaultdict(dict)
            for item in (
                all_subprojects_include_infrastructures
                .annotate(recap_sector=Upper('subproject_sector'))
                .filter(recap_sector__in=recap_sectors)
                .values('recap_sector', 'type_of_subproject')
                .annotate(
                    total_subprojects_selected=Count('id', filter=Q(subproject_type_designation="Subproject")),
                    total_structures_to_build=Count('id', filter=Q(number_of_infrastructures=1)),
                    total_projects_launched=Count('id', filter=Q(number_of_infrastructures=1, current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS)),
                    total_works_completed=Count('id', filter=Q(number_of_infrastructures=1, current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS)),
                    total_provisionally_approved=Count('id', filter=Q(number_of_infrastructures=1, current_status_of_the_site__in=STRUCTURE_PROVISIONAL_ACCEPTANCE_STATUS)),
                    total_finally_accepted=Count('id', filter=Q(number_of_infrastructures=1, current_status_of_the_site__in=STRUCTURE_FINAL_ACCEPTANCE_STATUS)),
                )
            ):
                recap_by_sector[item['recap_sector']][item['type_of_subproject']] = item

            # Completed subprojects of every (sector, type) in one query instead
            # of one query per type of structure.
            completed_by_sector_type = {}
            if any(item['total_subprojects_selected'] for items in recap_by_sector.values() for item in items.values()):
                with connection.cursor() as cursor:
                    cursor.execute(f"""
                        SELECT recap_sector, type_of_subproject, COUNT(*)
                        FROM (
                            SELECT UPPER(subproject_sector) AS recap_sector, type_of_subproject
                            FROM subprojects_subproject
                            WHERE (infrastructure_deleted IS NULL OR infrastructure_deleted = FALSE) AND id IN (SELECT sub.id FROM ({_sql}) AS sub)
                                AND UPPER(subproject_sector) IN {_sql_in(recap_sectors)}
                            GROUP BY UPPER(subproject_sector), type_of_subproject, joint_subproject_number
                            HAVING SUM((current_status_of_the_site NOT IN {_sql_in(STRUCTURE_COMPLETED_STATUS)})::int) = 0
                        ) AS completed_subprojects
                        GROUP BY recap_sector, type_of_subproject
                    """, _params)
                    completed_by_sector_type = {(row[0], row[1]): row[2] for row in cursor.fetchall()}

            count = 0
            lines_to_skip_for_sum = []

            # --- Parcourir chaque secteur ---
            for sector in recap_sectors:
                agg_dict = recap_by_sector.get(sector, {})

                # Récupérer les types distincts de sous-projets dans ce secteur
                types_in_sector = sorted(agg_dict, key=lambda type_name: type_name or '')

                # Nom du secteur dans toutes les colonnes
                for k in datas.keys():
                    datas[k][count] = _(sector)
                count += 1
                count_start = count

                for _type in types_in_sector:
                    data = agg_dict.get(_type, {})
                    datas[_("Types of work")][count] = _type
                    datas[_("Total number of sub-projects selected")][count] = data.get('total_subprojects_selected', 0)
                    datas[_("Total number of structures to be built")][count] = data.get('total_structures_to_build', 0)
                    datas[_("Total number of projects launched")][count] = data.get('total_projects_launched', 0)
                    datas[_("Total number of works completed")][count] = data.get('total_works_completed', 0)
                    datas[_("Total number of provisionally approved structures")][count] = data.get('total_provisionally_approved', 0)
                    datas[_("Total number of works finally accepted")][count] = data.get('total_finally_accepted', 0)
                    datas[_("Total number of sub-projects completed")][count] = completed_by_sector_type.get((sector, _type), 0)

                    count += 1

                # Total par secteur
                datas[_("Types of work")][count] = _(f"Total {sector}")
                for k, v in datas.items():
                    if k not in [_("Types of work"), _("Comments")]:
                        datas[k][count] = sum(list(v.values())[count_start:count])
                        lines_to_skip_for_sum.append(count)
                count += 1

            # --- Total général ---
            datas[_("Types of work")][count] = _("Total")
            for k in datas.keys():
                if k not in [_("Types of work"), _("Comments")]:
                    datas[k][count] = sum([v for i, v in datas[k].items() if isinstance(v, int) and i not in lines_to_skip_for_sum])
            count += 1

            # --- Préparer le contexte ---
            ctx["summary_recap"] = {
                'title': _("Summary of results"),
                'datas': datas,
                'length_loop': range(count),
                'values': list(datas.values())
            }
            ctx["table_class_style"] = 'table table-striped table-secondary table-bordered'
            plain_summary_tables(ctx["summary_recap"])
            #End Summary Recap


            # Structures by sector and type for each status, from one GROUP BY
            # (sector, type) and one query on the subprojects (by joint number),
            # instead of several queries per sector and per type for each status.
            by_sector_type = defaultdict(dict)
            for item in _rows_per_subproject(all_infrastructures).values('subproject_sector', 'type_of_subproject').annotate(
                identified=Count('id'),
                identified_subprojects=Count('id', filter=Q(subproject_type_designation="Subproject")),
                completed=Count('id', filter=Q(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS)),
                in_progress=Count('id', filter=Q(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS)),
                not_start=Count('id', filter=Q(current_status_of_the_site__in=STRUCTURE_NOT_START_STATUS)),
            ):
                by_sector_type[item['subproject_sector']][item['type_of_subproject']] = item

            subprojects_by_status = defaultdict(dict)
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    SELECT
                        subproject_sector,
                        COUNT(*) FILTER (WHERE not_completed = 0),
                        COUNT(*) FILTER (WHERE not_not_started > 0 AND not_completed > 0),
                        COUNT(*) FILTER (WHERE not_not_started = 0)
                    FROM (
                        SELECT
                            subproject_sector,
                            SUM((current_status_of_the_site NOT IN {_sql_in(STRUCTURE_COMPLETED_STATUS)})::int) AS not_completed,
                            SUM((current_status_of_the_site NOT IN {_sql_in(STRUCTURE_NOT_START_STATUS*2)})::int) AS not_not_started
                        FROM subprojects_subproject
                        WHERE (infrastructure_deleted IS NULL OR infrastructure_deleted = FALSE) AND id IN (SELECT sub.id FROM ({_sql}) AS sub)
                        GROUP BY subproject_sector, joint_subproject_number
                    ) AS by_joint_number
                    GROUP BY subproject_sector
                """, _params)
                for sector, completed, in_progress, not_start in cursor.fetchall():
                    subprojects_by_status['completed'][sector] = completed
                    subprojects_by_status['in_progress'][sector] = in_progress
                    subprojects_by_status['not_start'][sector] = not_start

            def build_sector_data(status_key, total_key, subprojects_from_joint_numbers=True):
                """Construit les données par secteur pour un statut donné."""
                data = {}
                for sector in sectors:
                    rows = by_sector_type.get(sector, {})
                    types = {}
                    for t in sorted((t for t, row in rows.items() if row[status_key]), key=lambda type_name: type_name or ''):
                        types[(t or '').capitalize()] = rows[t][status_key]
                    infrastructures_count = sum(row[status_key] for row in rows.values())
                    if subprojects_from_joint_numbers:
                        subprojects_count = subprojects_by_status[status_key].get(sector, 0)
                    else:
                        subprojects_count = sum(row['identified_subprojects'] for row in rows.values())
                    data[sector] = {
                        "types": types,
                        "total": {
                            "subprojects": subprojects_count,
                            "infrastructures": infrastructures_count,
                            "infrastructures_with_latrines_and_fences": infrastructures_count,  # inchangé
                        },
                    }
                data["total"] = total_key
                return data

            ctx["number_subproject_infrastrutures_by_sectors_and_type"] = {
                _("Identified"): build_sector_data('identified', ctx["total_infrastrutures"], subprojects_from_joint_numbers=False),
                _("Completed"): build_sector_data('completed', ctx["total_infrastrutures_completed"]),
                _("In progress"): build_sector_data('in_progress', ctx["total_infrastrutures_in_progress"]),
                _("Not start"): build_sector_data('not_start', ctx["total_infrastrutures_not_started"]),
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

        ctx.update(self.get_datas_on_request_get())

        ctx['SUB_PROJECT_SECTORS_COLOR'] = SUB_PROJECT_SECTORS_COLOR
        ctx['SUB_PROJECT_STATUS_COLOR_TRANSLATE'] = SUB_PROJECT_STATUS_COLOR_TRANSLATE
        return ctx



class DashboardFinancingListView(DashboardSubprojectsMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'components/dashboard_summary_financing.html'
    context_object_name = 'queryset_results'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['pie_graphes'] = []

        all_subprojects = ctx['queryset_results']['subprojects']
        sectors = ctx['queryset_results']['sectors'].copy()
        ids = (ctx['queryset_results']['ald_filter_ids'] + ctx['queryset_results']['administrative_levels_ids']).copy()

        # Filtrer les allocations pour le projet 1
        allocations_filter = dict(project_id=self.request.session.get('project_id'), cvd=None, administrative_level__type="Canton")
        if ids:
            allocations_filter['administrative_level__id__in'] = ids
        allocations_project = AdministrativeLevelAllocation.objects.filter(**allocations_filter)

        # Définir les composants de financement
        components_mapping = { _('Component 1.1'): 2, _('Component 1.2'): 3, _('Component 1.3'): 6 }
        financing_components = {}
        components_ids = [Component.expand_ids([component_id]) for component_id in components_mapping.values()]  # 1.x + sous-composantes

        # The amounts of every component and of all the subprojects in one query,
        # the allocations in another (two queries per component before).
        subprojects_sums = all_subprojects.aggregate(
            total_estimated_cost=Sum('estimated_cost'),
            total_contract_amount=Sum('contract_amount_work_companies'),
            **{
                f'{key}_{i}': Sum(field, filter=Q(component_id__in=_cids))
                for i, _cids in enumerate(components_ids)
                for key, field in (('estimated_cost', 'estimated_cost'), ('contract_amount', 'contract_amount_work_companies'))
            }
        )
        allocations_sums = allocations_project.aggregate(
            total=Sum('amount'),
            **{f'amount_{i}': Sum('amount', filter=Q(component_id__in=_cids)) for i, _cids in enumerate(components_ids)}
        )

        for i, component_label in enumerate(components_mapping):
            total_estimated = subprojects_sums[f'estimated_cost_{i}'] or 0
            total_contract = subprojects_sums[f'contract_amount_{i}'] or 0

            total_allocations = allocations_sums[f'amount_{i}'] or 0

            financing_components[component_label] = {
                'total_amount_subprojects_estimated_cost': total_estimated,
                'total_amount_subprojects_contract_amount_work_companies': total_contract,
                'total_allocations_cantons': total_allocations,
                'total_amount_remaining_after_allocation': total_allocations - total_estimated,
                'total_amount_residual': total_allocations - total_contract
            }

            # Graphique pour chaque composant
            ctx['pie_graphes'].append({
                'type': _("Wording"),
                'type_value_label': _("Amount"),
                'title': _("Amount of infrastructures by status") + f" {component_label}",
                'labels': [_("Residual"), _("Spent")],
                'data': [financing_components[component_label]['total_amount_residual'], total_contract],
                'sorted': 0
            })

        ctx['financing_components'] = financing_components

        # Totaux globaux
        total_estimated = subprojects_sums['total_estimated_cost'] or 0
        total_contract = subprojects_sums['total_contract_amount'] or 0
        total_allocations = allocations_sums['total'] or 0

        ctx.update({
            'total_amount_subprojects_estimated_cost': total_estimated,
            'total_amount_subprojects_contract_amount_work_companies': total_contract,
            'total_allocations_cantons': total_allocations,
            'total_amount_remaining_after_allocation': total_allocations - total_estimated,
            'total_amount_residual': total_allocations - total_contract
        })

        # Montants par secteur (one GROUP BY instead of one query per sector)
        costs_by_sector = dict(
            _rows_per_subproject(all_subprojects).values('subproject_sector')
            .annotate(total=Sum('estimated_cost')).values_list('subproject_sector', 'total')
        )
        sector_data = [costs_by_sector.get(sector) or 0 for sector in sectors]
        ctx['amount_subproject_infrastrutures'] = {
            'title': _("Amount of infrastructures by sector"),
            'labels': sectors,
            'bars': [{'label': _("Infrastructure"), 'backgroundColor': 'blue', 'data': sector_data}]
        }

        # Graphiques globaux
        ctx['pie_graphes'].extend([
            {
                'type': _("Wording"),
                'type_value_label': _("Amount"),
                'title': _("Amount of infrastructures by status"),
                'labels': [_("Residual"), _("Spent")],
                'data': [ctx['total_amount_residual'], ctx['total_amount_subprojects_contract_amount_work_companies']],
                'sorted': 0
            },
            {
                'type': _("Sectors"),
                'type_value_label': _("Amount"),
                'title': _("Amount of infrastructures by sector"),
                'labels': sectors,
                'data': sector_data,
                'sorted': 1,
                'columnSorted': 1
            }
        ])

        # Informations administratives
        # ctx['administrative_level_id'] = self.request.GET.getlist('administrative_level_id[]', [])
        # admin_type = self.request.GET.get('administrative_level_type', 'All').title()
        # ctx['administrative_level_type'] = "All" if admin_type in ("", "null", "undefined") else admin_type
        ctx.update(self.get_datas_on_request_get())

        ctx['FINANCING_COLOR'] = FINANCING_COLOR
        ctx['SUB_PROJECT_SECTORS_COLOR'] = SUB_PROJECT_SECTORS_COLOR

        return ctx

    # def get_context_data(self, **kwargs):
    #     ctx = super(DashboardFinancingListView, self).get_context_data(**kwargs)
    #     ctx['pie_graphes'] = []
    #     all_subprojects = ctx['queryset_results']['subprojects']
    #     sectors = ctx['queryset_results']['sectors']
    #     ids = ctx['queryset_results']['ald_filter_ids'].copy() + ctx['queryset_results']['administrative_levels_ids'].copy()
    #     if ids:
    #         allocations_project = AdministrativeLevelAllocation.objects.filter(
    #             project_id=1,
    #             cvd=None,
    #             administrative_level__id__in=ids,
    #             administrative_level__type="Canton"
    #         )
    #     else:
    #         allocations_project = AdministrativeLevelAllocation.objects.filter(
    #             project_id=1,
    #             cvd=None,
    #             administrative_level__type="Canton"
    #         )
        
    #     #Component 1.1
    #     financing_components = {}
    #     for component, component_id in {
    #         _('Component 1.1'): 2, _('Component 1.2'): 3, _('Component 1.3'): 6
    #     }.items():
    #         financing_components[component] = {}
    #         financing_components[component]['total_amount_subprojects_estimated_cost'] = all_subprojects.filter(component_id=component_id).aggregate(Sum('estimated_cost'))['estimated_cost__sum']
    #         financing_components[component]['total_amount_subprojects_estimated_cost'] = financing_components[component]['total_amount_subprojects_estimated_cost'] if financing_components[component]['total_amount_subprojects_estimated_cost'] else 0
            
    #         financing_components[component]['total_amount_subprojects_contract_amount_work_companies'] = all_subprojects.filter(component_id=component_id).aggregate(Sum('contract_amount_work_companies'))['contract_amount_work_companies__sum']
    #         financing_components[component]['total_amount_subprojects_contract_amount_work_companies'] = financing_components[component]['total_amount_subprojects_contract_amount_work_companies'] if financing_components[component]['total_amount_subprojects_contract_amount_work_companies'] else 0
            
    #         financing_components[component]['total_allocations_cantons'] = allocations_project.filter(cvd=None, component_id=component_id).aggregate(Sum('amount'))['amount__sum']
    #         financing_components[component]['total_allocations_cantons'] = financing_components[component]['total_allocations_cantons'] if financing_components[component]['total_allocations_cantons'] else 0
            
    #         financing_components[component]['total_amount_remaining_after_allocation'] = financing_components[component]['total_allocations_cantons'] - financing_components[component]['total_amount_subprojects_estimated_cost']
    #         financing_components[component]['total_amount_residual'] = financing_components[component]['total_allocations_cantons'] - financing_components[component]['total_amount_subprojects_contract_amount_work_companies']

    #         ctx['pie_graphes'].append({
    #             'type': _("Wording"),
    #             'type_value_label': _("Amount"),
    #             'title': _("Amount of infrastructures by status") + f" {component}",
    #             'labels': [_("Residual"), _("Spent")],
    #             'data': [financing_components[component]['total_amount_residual'], financing_components[component]['total_amount_subprojects_contract_amount_work_companies']],
    #             'sorted': 0
    #         })
            
    #     ctx['financing_components'] = financing_components
        
        
    #     ctx['total_amount_subprojects_estimated_cost'] = all_subprojects.aggregate(Sum('estimated_cost'))['estimated_cost__sum']
    #     ctx['total_amount_subprojects_estimated_cost'] = ctx['total_amount_subprojects_estimated_cost'] if ctx['total_amount_subprojects_estimated_cost'] else 0
        
    #     ctx['total_amount_subprojects_contract_amount_work_companies'] = all_subprojects.aggregate(Sum('contract_amount_work_companies'))['contract_amount_work_companies__sum']
    #     ctx['total_amount_subprojects_contract_amount_work_companies'] = ctx['total_amount_subprojects_contract_amount_work_companies'] if ctx['total_amount_subprojects_contract_amount_work_companies'] else 0
        
    #     ctx['total_allocations_cantons'] = allocations_project.filter(cvd=None).aggregate(Sum('amount'))['amount__sum']
    #     ctx['total_allocations_cantons'] = ctx['total_allocations_cantons'] if ctx['total_allocations_cantons'] else 0
        
    #     ctx['total_amount_remaining_after_allocation'] = ctx['total_allocations_cantons'] - ctx['total_amount_subprojects_estimated_cost']
    #     ctx['total_amount_residual'] = ctx['total_allocations_cantons'] - ctx['total_amount_subprojects_contract_amount_work_companies']
        
        
    #     ctx['amount_subproject_infrastrutures'] = {
    #         'title': _("Amount of infrastructures by sector"),
    #         'labels': sectors,
    #         'bars': [
    #             {
    #                 'label': _("Infrastructure"),
    #                 'backgroundColor': 'blue',
    #                 'data': [(elt if elt else 0) for elt in [
    #                     all_subprojects.filter(subproject_sector=sector).aggregate(Sum('estimated_cost'))['estimated_cost__sum'] for sector in sectors
    #                 ]]
    #             }
    #         ]
    #     }
        
    #     ctx['pie_graphes'].append({
    #         'type': _("Wording"),
    #         'type_value_label': _("Amount"),
    #         'title': _("Amount of infrastructures by status"),
    #         'labels': [_("Residual"), _("Spent")],
    #         'data': [ctx['total_amount_residual'], ctx['total_amount_subprojects_contract_amount_work_companies']],
    #         'sorted': 0
    #     })
        
    #     ctx['pie_graphes'].append({
    #         'type': _("Sectors"),
    #         'type_value_label': _("Amount"),
    #         'title': _("Amount of infrastructures by sector"),
    #         'labels': sectors,
    #         'data': ctx['amount_subproject_infrastrutures']['bars'][0]['data'],
    #         'sorted': 1,
    #         'columnSorted': 1
    #     })

    #     ctx['administrative_level_id'] = self.request.GET.getlist('administrative_level_id[]', [])
    #     administrative_level_type = self.request.GET.get('administrative_level_type', 'All').title()
    #     ctx['administrative_level_type'] = "All" if administrative_level_type in ("", "null", "undefined") else administrative_level_type
    #     ctx['FINANCING_COLOR'] = FINANCING_COLOR
    #     ctx['SUB_PROJECT_SECTORS_COLOR'] = SUB_PROJECT_SECTORS_COLOR
    #     return ctx


class DashboardFinancingListByCantonView(DashboardSubprojectsMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'components/dashboard_summary_financing_by_canton.html'
    context_object_name = 'queryset_results'
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        all_subprojects = ctx['queryset_results']['subprojects']
        ids = (ctx['queryset_results']['ald_filter_ids'] + ctx['queryset_results']['administrative_levels_ids']).copy()

        # Filtrer les allocations pour le projet 1
        allocations_filter = dict(project_id=self.request.session.get('project_id'), cvd=None, administrative_level__type="Canton")
        if ids:
            allocations_filter['administrative_level__id__in'] = ids
        allocations_project = AdministrativeLevelAllocation.objects.filter(**allocations_filter)

        # Récupérer les cantons
        lines = AdministrativeLevelWave.objects.filter(
            administrative_level__id__in=ids
        ).order_by("administrative_level__name") if ids else AdministrativeLevelWave.objects.all().order_by("administrative_level__name")
        lines = list(lines)
        levels = AdministrativeLevel._base_manager.in_bulk({line.administrative_level_id for line in lines})
        admls = [levels.get(line.administrative_level_id) for line in lines]

        # Les administrative levels of each canton (the canton itself only when
        # the dashboard is filtered, as before), the whole tree loaded at once.
        if ctx['queryset_results']['ald_filter_ids']:
            id_with_descendants = ctx['queryset_results']['id_with_descendants']
            admls_descendants = [[adl.id] + (id_with_descendants.get(str(adl.id)) or []) for adl in admls]
        else:
            project_id = self.request.session.get('project_id')
            children_map = get_administrative_level_children_map({adl.id for adl in admls}, project_id)
            admls_descendants = [
                get_administrative_level_ids_descendants(adl.id, None, [], project_id, children_map=children_map)
                for adl in admls
            ]
        lines_by_administrative_level = defaultdict(set)
        for i, descendants in enumerate(admls_descendants):
            for adl_id in descendants:
                lines_by_administrative_level[adl_id].add(i)

        components = [
            (2, _("Presentation of allocations, estimates and expenditure by canton - Component 1.1")),
            (3, _("Presentation of allocations, estimates and expenditure by canton - Component 1.2")),
            (6, _("Presentation of allocations, estimates and expenditure by canton - Component 1.3")),
        ]
        components_ids = [set(Component.expand_ids([component_id])) for component_id, title in components]  # 1.x + sous-composantes

        # Estimates and expenditure of every canton for every component from one
        # read of the subprojects (three queries per canton and component before).
        # With the pk, a distinct queryset still gives one row per subproject.
        estimates = [[None] * len(admls) for c in components]
        spent = [[None] * len(admls) for c in components]
        for pk, location_id, canton_id, component_id, estimated_cost, contract_amount in all_subprojects.values_list(
            'pk', 'location_subproject_realized_id', 'canton_id', 'component_id',
            'estimated_cost', 'contract_amount_work_companies'
        ):
            matched_lines = lines_by_administrative_level.get(location_id, set()) | lines_by_administrative_level.get(canton_id, set())
            if not matched_lines:
                continue
            for k, _cids in enumerate(components_ids):
                if component_id not in _cids:
                    continue
                for i in matched_lines:
                    if estimated_cost is not None:
                        estimates[k][i] = estimated_cost if estimates[k][i] is None else estimates[k][i] + estimated_cost
                    if contract_amount is not None:
                        spent[k][i] = contract_amount if spent[k][i] is None else spent[k][i] + contract_amount

        # Fonction pour construire les données par composant
        def build_component_data(k, title):
            allocations = dict(
                allocations_project.filter(component_id__in=components_ids[k])
                .values('administrative_level_id').annotate(total=Sum('amount'))
                .values_list('administrative_level_id', 'total')
            )
            bars = [
                {
                    'label': _("Allocation"),
                    'backgroundColor': 'blue',
                    'data': [allocations.get(adl.id) or 0 for adl in admls]
                },
                {
                    'label': _("Sub-project estimates"),
                    'backgroundColor': 'red',
                    'data': [total or 0 for total in estimates[k]]
                },
                {
                    'label': _("Spent"),
                    'backgroundColor': 'green',
                    'data': [total or 0 for total in spent[k]]
                }
            ]
            return {
                'title': title,
                'labels': [adl.name for adl in admls],
                'bars': bars
            }

        # Construire les données pour les composants 1.1, 1.2 et 1.3
        ctx['amount_cantons_component_1_1'] = build_component_data(0, components[0][1])
        ctx['amount_cantons_component_1_2'] = build_component_data(1, components[1][1])
        ctx['amount_cantons_component_1_3'] = build_component_data(2, components[2][1])

        # Informations administratives
        # ctx['administrative_level_id'] = self.request.GET.getlist('administrative_level_id[]', [])
        # admin_type = self.request.GET.get('administrative_level_type', 'All').title()
        # ctx['administrative_level_type'] = "All" if admin_type in ("", "null", "undefined") else admin_type
        ctx.update(self.get_datas_on_request_get())

        return ctx


    # def get_context_data(self, **kwargs):
    #     ctx = super(DashboardFinancingListByCantonView, self).get_context_data(**kwargs)
    #     all_subprojects = ctx['queryset_results']['subprojects']
    #     # components = Component.objects.filter(parent__name="Composante 1")
    #     ids = ctx['queryset_results']['ald_filter_ids'].copy() + ctx['queryset_results']['administrative_levels_ids'].copy()
    #     if ids:
    #         allocations_project = AdministrativeLevelAllocation.objects.filter(
    #             project_id=1,
    #             cvd=None,
    #             administrative_level__id__in=ids,
    #             administrative_level__type="Canton"
    #         )
    #     else:
    #         allocations_project = AdministrativeLevelAllocation.objects.filter(
    #             project_id=1,
    #             cvd=None,
    #             administrative_level__type="Canton"
    #         )
    #     allocations_project = AdministrativeLevelAllocation.objects.filter()

    #     if ids:
    #         lines = AdministrativeLevelWave.objects.filter(administrative_level__id__in=ids).order_by("administrative_level__name")
    #         # admls = AdministrativeLevel.objects.filter(type="Canton", id__in=ids).order_by("name")
    #     else:
    #         #  admls = AdministrativeLevel.objects.filter(type="Canton").order_by("name")
    #          lines = AdministrativeLevelWave.objects.all().order_by("administrative_level__name")
    #     admls = [adl.administrative_level for adl in lines]
    #     admls_children = [
    #         (
    #             adl, 
    #             allocations_project.filter(
    #                 administrative_level__id=adl.id
    #             ),
    #             ([adl.id] + get_administrative_level_ids_descendants(adl.id, None, [], self.request.session.get('project_id')))) for adl in admls
    #     ]
        
    #     ctx['amount_cantons_component_1_1'] = {
    #         'title': _("Presentation of allocations, estimates and expenditure by canton - Component 1.1"),
    #         'labels': [adl.name for adl in admls],
    #         'bars': [
    #             {
    #                 'label': _("Allocation"),
    #                 'backgroundColor': 'blue',
    #                 'data': [(elt if elt else 0) for elt in [
    #                     adml[1].filter(
    #                         component_id=2
    #                     ).aggregate(Sum('amount'))['amount__sum'] for adml in admls_children
    #                 ]]
    #             },
    #             {
    #                 'label': _("Sub-project estimates"),
    #                 'backgroundColor': 'red',
    #                 'data': [(elt if elt else 0) for elt in [
    #                     all_subprojects.filter(
    #                         Q(location_subproject_realized__id__in=adml[2]) | 
    #                         Q(canton__id__in=adml[2]), component_id=2
    #                     ).aggregate(Sum('estimated_cost'))['estimated_cost__sum'] for adml in admls_children
    #                 ]]
    #             },
    #             {
    #                 'label': _("Spent"),
    #                 'backgroundColor': 'green',
    #                 'data': [(elt if elt else 0) for elt in [
    #                     all_subprojects.filter(
    #                         Q(location_subproject_realized__id__in=adml[2]) | 
    #                         Q(canton__id__in=adml[2]), component_id=2
    #                     ).aggregate(Sum('contract_amount_work_companies'))['contract_amount_work_companies__sum'] for adml in admls_children
    #                 ]]
    #             }
    #         ]
    #     }
        
        
    #     ctx['amount_cantons_component_1_2'] = {
    #         'title': _("Presentation of allocations, estimates and expenditure by canton - Component 1.2"),
    #         'labels': [adl.name for adl in admls],
    #         'bars': [
    #             {
    #                 'label': _("Allocation"),
    #                 'backgroundColor': 'blue',
    #                 'data': [(elt if elt else 0) for elt in [
    #                     adml[1].filter(
    #                         component_id=3
    #                     ).aggregate(Sum('amount'))['amount__sum'] for adml in admls_children
    #                 ]]
    #             },
    #             {
    #                 'label': _("Sub-project estimates"),
    #                 'backgroundColor': 'red',
    #                 'data': [(elt if elt else 0) for elt in [
    #                     all_subprojects.filter(
    #                         Q(location_subproject_realized__id__in=adml[2]) | 
    #                         Q(canton__id__in=adml[2]), component_id=3
    #                     ).aggregate(Sum('estimated_cost'))['estimated_cost__sum'] for adml in admls_children
    #                 ]]
    #             },
    #             {
    #                 'label': _("Spent"),
    #                 'backgroundColor': 'green',
    #                 'data': [(elt if elt else 0) for elt in [
    #                     all_subprojects.filter(
    #                         Q(location_subproject_realized__id__in=adml[2]) | 
    #                         Q(canton__id__in=adml[2]), component_id=3
    #                     ).aggregate(Sum('contract_amount_work_companies'))['contract_amount_work_companies__sum'] for adml in admls_children
    #                 ]]
    #             }
    #         ]
    #     }
        
        
    #     ctx['amount_cantons_component_1_3'] = {
    #         'title': _("Presentation of allocations, estimates and expenditure by canton - Component 1.3"),
    #         'labels': [adl.name for adl in admls],
    #         'bars': [
    #             {
    #                 'label': _("Allocation"),
    #                 'backgroundColor': 'blue',
    #                 'data': [(elt if elt else 0) for elt in [
    #                     adml[1].filter(
    #                         component_id=6
    #                     ).aggregate(Sum('amount'))['amount__sum'] for adml in admls_children
    #                 ]]
    #             },
    #             {
    #                 'label': _("Sub-project estimates"),
    #                 'backgroundColor': 'red',
    #                 'data': [(elt if elt else 0) for elt in [
    #                     all_subprojects.filter(
    #                         Q(location_subproject_realized__id__in=adml[2]) | 
    #                         Q(canton__id__in=adml[2]), component_id=6
    #                     ).aggregate(Sum('estimated_cost'))['estimated_cost__sum'] for adml in admls_children
    #                 ]]
    #             },
    #             {
    #                 'label': _("Spent"),
    #                 'backgroundColor': 'green',
    #                 'data': [(elt if elt else 0) for elt in [
    #                     all_subprojects.filter(
    #                         Q(location_subproject_realized__id__in=adml[2]) | 
    #                         Q(canton__id__in=adml[2]), component_id=6
    #                     ).aggregate(Sum('contract_amount_work_companies'))['contract_amount_work_companies__sum'] for adml in admls_children
    #                 ]]
    #             }
    #         ]
    #     }
        
        
    #     # ctx['pie_graphes'] = [
    #     #     {
    #     #         'type': _("Locality"),
    #     #         'type_value_label': _("Amount"),
    #     #         'title': _("Presentation of allocations by canton - Component 1.1"),
    #     #         'labels': [adl.name for adl in admls],
    #     #         'data': ctx['amount_cantons_component_1_1']['bars'][0]['data'],
    #     #         'sorted': 1,
    #     #         'columnSorted': 1
    #     #     },
    #     #     {
    #     #         'type': _("Locality"),
    #     #         'type_value_label': _("Amount"),
    #     #         'title': _("Presentation of allocations by canton - Component 1.2"),
    #     #         'labels': [adl.name for adl in admls],
    #     #         'data': ctx['amount_cantons_component_1_2']['bars'][0]['data'],
    #     #         'sorted': 1,
    #     #         'columnSorted': 1
    #     #     },
    #     #     {
    #     #         'type': _("Locality"),
    #     #         'type_value_label': _("Amount"),
    #     #         'title': _("Presentation of allocations by canton - Component 1.3"),
    #     #         'labels': [adl.name for adl in admls],
    #     #         'data': ctx['amount_cantons_component_1_3']['bars'][0]['data'],
    #     #         'sorted': 1,
    #     #         'columnSorted': 1
    #     #     }
    #     # ]
        
        
    #     ctx['administrative_level_id'] = self.request.GET.getlist('administrative_level_id[]', [])
    #     administrative_level_type = self.request.GET.get('administrative_level_type', 'All').title()
    #     ctx['administrative_level_type'] = "All" if administrative_level_type in ("", "null", "undefined") else administrative_level_type
        
    #     # ctx['administrative_level_colors'] = {}
    #     # adl_colors = list(SUB_PROJECT_SECTORS_COLOR.values())*5
    #     # _admls = admls[:]
    #     # for i in range(len(_admls)):
    #     #     try:
    #     #         ctx['administrative_level_colors'][_admls[i].name] = adl_colors[i]
    #     #     except:
    #     #         ctx['administrative_level_colors'][_admls[i].name] = '#000000'
            
    #     return ctx





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
                        # f"""
                        # SELECT DISTINCT sub_subp.id, sub_subp.full_title_of_approved_subproject 
                        # FROM subprojects_subproject AS sub_subp 
                        # LEFT JOIN subprojects_subproject AS sub_infras ON sub_subp.id=sub_infras.link_to_subproject_id 
                        # WHERE (sub_subp.current_status_of_the_site IN {_sql_in(STRUCTURE_COMPLETED_STATUS)}
                        #     AND (sub_infras.current_status_of_the_site IS NULL OR sub_infras.current_status_of_the_site IN {_sql_in(STRUCTURE_COMPLETED_STATUS)})) 
                        #     AND sub_subp.id IN (
                        #         SELECT sub.id FROM ({_sql}) AS sub 
                        #     ) 
                        #     AND (sub_subp.infrastructure_deleted IS NULL OR sub_subp.infrastructure_deleted = 0)
                        #     AND (sub_infras.infrastructure_deleted IS NULL OR sub_infras.infrastructure_deleted = 0)
                        # """, _params
                        f"""
                        SELECT MIN(id) AS id, joint_subproject_number
                        FROM subprojects_subproject
                        WHERE (infrastructure_deleted IS NULL OR infrastructure_deleted = FALSE) AND id IN (SELECT sub.id FROM ({_sql}) AS sub) 
                        GROUP BY joint_subproject_number
                        HAVING SUM((current_status_of_the_site NOT IN {_sql_in(STRUCTURE_COMPLETED_STATUS)})::int) = 0
                        """, _params
                    )
                    # all_subprojects = all_subprojects.filter(subproject_type_designation="Subproject", current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS)
                    all_subprojects = final_queryset #Subproject.objects.filter(id__in=[p.id for p in final_queryset])
                elif list_type_search == 'subprojects-in-progress':
                    list_name_search = _("Subprojects in progress")
                    final_queryset = all_subprojects.raw(
                        # f"""
                        # SELECT DISTINCT sub_subp.id, sub_subp.full_title_of_approved_subproject 
                        # FROM subprojects_subproject AS sub_subp 
                        # LEFT JOIN subprojects_subproject AS sub_infras ON sub_subp.id=sub_infras.link_to_subproject_id 
                        # WHERE (((sub_subp.current_status_of_the_site IN {_sql_in(STRUCTURE_NOT_START_STATUS*2)} 
                        #     AND sub_infras.current_status_of_the_site IN {tuple(STRUCTURE_COMPLETED_STATUS+STRUCTURE_IN_PROGRESS_STATUS)}) 
                        #     OR (sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_IN_PROGRESS_STATUS+STRUCTURE_COMPLETED_STATUS)} 
                        #     AND (sub_infras.current_status_of_the_site IN {tuple(STRUCTURE_NOT_START_STATUS+STRUCTURE_IN_PROGRESS_STATUS)}))
                        #     OR (sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_IN_PROGRESS_STATUS*2)})) 
                        #     AND sub_subp.id IN (
                        #         SELECT sub.id FROM ({_sql}) AS sub 
                        #     )) 
                        #     AND (sub_subp.infrastructure_deleted IS NULL OR sub_subp.infrastructure_deleted = 0)
                        #     AND (sub_infras.infrastructure_deleted IS NULL OR sub_infras.infrastructure_deleted = 0)
                        # """, _params
                        f"""
                           SELECT MIN(id) AS id, joint_subproject_number
                            FROM subprojects_subproject
                            WHERE (infrastructure_deleted IS NULL OR infrastructure_deleted = FALSE) AND id IN (SELECT sub.id FROM ({_sql}) AS sub) 
                            GROUP BY joint_subproject_number
                            HAVING SUM((current_status_of_the_site NOT IN {_sql_in(STRUCTURE_NOT_START_STATUS*2)})::int) > 0
                                AND SUM((current_status_of_the_site NOT IN {_sql_in(STRUCTURE_COMPLETED_STATUS)})::int) > 0
                        """, _params
                    )
                    # all_subprojects = all_subprojects.filter(subproject_type_designation="Subproject", current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS)
                    all_subprojects = final_queryset #Subproject.objects.filter(id__in=[p.id for p in final_queryset])
                elif list_type_search == 'subprojects-not-started':
                    list_name_search = _("Subprojects not start")
                    final_queryset = all_subprojects.raw(
                        # f"""
                        # SELECT DISTINCT sub_subp.id 
                        # FROM subprojects_subproject AS sub_subp 
                        # LEFT JOIN subprojects_subproject AS sub_infras ON sub_infras.link_to_subproject_id=sub_subp.id AND sub_infras.subproject_type_designation='Infrastructure' 
                        # WHERE (sub_subp.current_status_of_the_site NOT IN {tuple(STRUCTURE_IN_PROGRESS_STATUS+STRUCTURE_COMPLETED_STATUS)} 
                        #     AND (sub_infras.current_status_of_the_site IS NULL OR sub_infras.current_status_of_the_site NOT IN {tuple(STRUCTURE_IN_PROGRESS_STATUS+STRUCTURE_COMPLETED_STATUS)})) 
                        #     AND sub_subp.id IN (
                        #         SELECT sub.id FROM ({_sql}) AS sub 
                        #     ) 
                        #     AND (sub_subp.infrastructure_deleted IS NULL OR sub_subp.infrastructure_deleted = 0)
                        #     AND (sub_infras.infrastructure_deleted IS NULL OR sub_infras.infrastructure_deleted = 0)
                        # """, _params
                        f"""
                        SELECT MIN(id) AS id, joint_subproject_number
                        FROM subprojects_subproject
                        WHERE (infrastructure_deleted IS NULL OR infrastructure_deleted = FALSE) AND id IN (SELECT sub.id FROM ({_sql}) AS sub)
                        GROUP BY joint_subproject_number
                        HAVING SUM((current_status_of_the_site NOT IN {_sql_in(STRUCTURE_NOT_START_STATUS*2)})::int) = 0
                        """, _params
                    )
                    # all_subprojects = all_subprojects.filter(subproject_type_designation="Subproject").exclude(current_status_of_the_site__in=(STRUCTURE_COMPLETED_STATUS+STRUCTURE_IN_PROGRESS_STATUS))
                    all_subprojects = final_queryset #Subproject.objects.filter(id__in=[p.id for p in final_queryset])
        else:
            all_subprojects = all_subprojects.filter(number_of_infrastructures=1)
            if list_type_search == 'infrastrutures':
                list_name_search = _("Structures/infrastructures") #_("Structures/infrastructures without latrines and fences")
            elif list_type_search == 'infrastruture-completed':
                list_name_search = _("Structures/infrastructures completed") #_("Structures/infrastructures completed (excluding latrines and fences)")
                all_subprojects = all_subprojects.filter(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS)
            elif list_type_search == 'infrastruture-in-progress':
                list_name_search = _("Structures/infrastructures in progress") #_("Structures/infrastructures in progress (excluding latrines and fences)")
                all_subprojects = all_subprojects.filter(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS)
            elif list_type_search == 'infrastruture-not-started':
                list_name_search = _("Structures/infrastructures not start") #_("Structures/infrastructures not start (excluding latrines and fences)")
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

        subprojects = self.get_queryset_search(_subprojects_for_display(all_subprojects))
        
        administrative_level_type = self.request.GET.get('administrative_level_type', 'All').title()

        context['subprojects'] = subprojects
        # context['administrative_level_id'] = self.request.GET.getlist('administrative_level_id[]', [])
        # context['administrative_level_type'] = "All" if administrative_level_type in ("", "null", "undefined") else administrative_level_type
        context.update(self.get_datas_on_request_get())

        context['list_type_search'] = list_type_search
        
        context.update(ctx)
        context['title'] = list_name_search
        
        # return self.render_to_json_response(context, safe=False)
        return context