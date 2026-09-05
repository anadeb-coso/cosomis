from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from cosomis.mixins import PageMixin, AJAXRequestMixin, ModalListMixin, JSONResponseMixin
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Case, When, IntegerField, Max, Prefetch
from datetime import datetime
from django.db import connection
import logging
from django.http import Http404

from subprojects.models import Subproject, Step, Component, Project, SubprojectStep, Level
from administrativelevels.models import AdministrativeLevel
from financial.models.allocation import AdministrativeLevelAllocation
from process_manager.models import AdministrativeLevelWave
from administrativelevels.functions import get_administrative_level_ids_descendants, get_administrative_level_ids_descendants_with_dict
from . import forms
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
        subproject_sectors = self.filter_list_by_delete_empty(self.request.GET.getlist('id_subproject_sectors[]'))
        subproject_types = self.filter_list_by_delete_empty(self.request.GET.getlist('id_subproject_types[]'))
        works_type_of_subprojects = self.filter_list_by_delete_empty(self.request.GET.getlist('id_works_type_of_subproject[]'))
        subproject_steps = self.filter_list_by_delete_empty(self.request.GET.getlist('id_subproject_step[]'))
        components_names = self.filter_list_by_delete_empty(self.request.GET.getlist('id_components[]'))
        start_date_raw = request.GET.get('start_date', None)
        end_date_raw = request.GET.get('end_date', None)
        
        start_date = None
        end_date = None

        if start_date_raw:
            start_date = self.parse_fr_date(start_date_raw)
        if end_date_raw:
            end_date = self.parse_fr_date(end_date_raw)


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
        subprojects = Subproject.objects.get_objects_by_general_filtre(request, None).prefetch_related().get_actifs()

        if start_date or end_date:
            if not subproject_steps:
                subprojects = subprojects.filter(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS)
                
                if start_date and end_date:
                    subprojects = subprojects.filter(
                        work_completion_date__range=[start_date, end_date]
                    )
                elif start_date:
                    subprojects = subprojects.filter(
                        work_completion_date__gte=start_date
                    )
                else:
                    subprojects = subprojects.filter(
                        work_completion_date__lte=end_date
                    )
                
            else:
                q = Q()
                if 'not_started' in subproject_steps:
                    q |= Q(subprojectstep__ranking__gte=0, subprojectstep__ranking__lt=IN_PROGRESS_RANKING)
                if 'in_progress' in subproject_steps:
                    if start_date and end_date:
                        q |= Q(subprojectstep__ranking__gte=IN_PROGRESS_RANKING, subprojectstep__ranking__lt=IN_PROGRESS_RANKING, subprojectstep__level__begin__range=[start_date, end_date])
                    elif start_date:
                        q |= Q(subprojectstep__ranking__gte=IN_PROGRESS_RANKING, subprojectstep__ranking__lt=IN_PROGRESS_RANKING, subprojectstep__level__begin__gte=start_date)
                    else:
                        q |= Q(subprojectstep__ranking__gte=IN_PROGRESS_RANKING, subprojectstep__ranking__lt=IN_PROGRESS_RANKING, subprojectstep__level__begin__lte=end_date)
                if 'completed' in subproject_steps:
                    q |= Q(subprojectstep__ranking__gte=COMPLETED_RANKING)

                if start_date and end_date:
                    subprojects = subprojects.filter(Q(
                        Q(Q(subprojectstep__begin__range=[start_date, end_date]) & q)
                    )).distinct()
                elif start_date:
                    subprojects = subprojects.filter(Q(
                        Q(Q(subprojectstep__begin__gte=start_date) & q)
                    )).distinct()
                else:
                    subprojects = subprojects.filter(Q(
                        Q(Q(subprojectstep__begin__lte=end_date) & q)
                    )).distinct()

        elif subproject_steps:
            q = Q()
            if 'not_started' in subproject_steps:
                q |= Q(current_status_of_the_site__in=STRUCTURE_NOT_START_STATUS)
            if 'in_progress' in subproject_steps:
                q |= Q(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS)
            if 'completed' in subproject_steps:
                q |= Q(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS)
            subprojects = subprojects.filter(q)

        if components_names:
            subprojects = subprojects.filter(
                component_id__in=Component.expand_names(components_names))
        
        if subproject_sectors:
            subprojects = subprojects.filter(subproject_sector__in=[elt for elt in subproject_sectors if elt])
        
        if subproject_types:
            subprojects = subprojects.filter(type_of_subproject__in=[elt for elt in subproject_types if elt])
            
        if works_type_of_subprojects:
            subprojects = subprojects.filter(works_type__in=[elt for elt in works_type_of_subprojects if elt])

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
            'sectors': sorted(list(sectors)),
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
        
        ctx['total'] = all_infrastructures.count()
        ctx['total_without_link'] = all_subprojects_include_infrastructures.filter(link_to_subproject=None, subproject_type_designation="Subproject").count()
        ctx['total_subproject'] = all_subprojects_include_infrastructures.filter(subproject_type_designation="Subproject").count()
        ctx['total_infrastruture'] = all_infrastructures.filter(subproject_type_designation="Infrastructure").count()
        # ctx['total_latrine_blocks'] = all_subprojects.filter(has_latrine_blocs=True).count()
        # ctx['total_number_latrine_blocks'] = all_subprojects.filter(has_latrine_blocs=True).aggregate(Sum('number_of_latrine_blocks'))['number_of_latrine_blocks__sum']
        # ctx['total_number_latrine_blocks'] = ctx['total_number_latrine_blocks'] if ctx['total_number_latrine_blocks'] else 0
        # ctx['total_fences'] = all_subprojects.filter(has_fence=True).count()
        ctx['total_infrastrutures'] = ctx['total'] # + ctx['total_latrine_blocks'] + ctx['total_fences']
        
        # ctx['total_subproject_in_progress'] = all_subprojects.filter(subproject_type_designation="Subproject", current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS).count()
        # ctx['total_subproject_completed'] = all_subprojects.filter(subproject_type_designation="Subproject", current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).count()
                
        _s = all_subprojects_include_infrastructures.filter(subproject_type_designation="Subproject")

        # Compter tous les Subprojects par secteur
        subprojects_by_sector = (
            _s
            .values("subproject_sector")
            .annotate(total=Count("id"))
        )
        subprojects_dict = {entry['subproject_sector']: entry['total'] for entry in subprojects_by_sector}

        # stats = all_subprojects_include_infrastructures.values("subproject_type_designation").annotate(total=Count("id"))

        infrastructures_stats = all_infrastructures.values("subproject_sector").annotate(total=Count("id"))
        infrastructures_dict = {entry['subproject_sector']: entry['total'] for entry in infrastructures_stats}


        # Somme des coûts par secteur
        costs_by_sector = (
            all_subprojects_include_infrastructures
            .values('subproject_sector')
            .annotate(total_estimated_cost=Sum('estimated_cost'))
        )
        costs_dict = {entry['subproject_sector']: entry['total_estimated_cost'] or 0 for entry in costs_by_sector}



        # Get SQL representation of the first filter's queryset
        if _s.exists():
            _sql, _params = _s.query.get_compiler('default').as_sql()
            # Use the SQL representation in the raw query for the second filter
            # final_queryset = _s.raw(
            #     # f"""
            #     # SELECT DISTINCT sub_subp.id, sub_subp.full_title_of_approved_subproject 
            #     # FROM subprojects_subproject AS sub_subp 
            #     # LEFT JOIN subprojects_subproject AS sub_infras ON sub_subp.id=sub_infras.link_to_subproject_id 
            #     # WHERE (((sub_subp.current_status_of_the_site IN {_sql_in(STRUCTURE_NOT_START_STATUS*2)} 
            #     #     AND sub_infras.current_status_of_the_site IN {tuple(STRUCTURE_COMPLETED_STATUS+STRUCTURE_IN_PROGRESS_STATUS)}) 
            #     #     OR (sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_IN_PROGRESS_STATUS+STRUCTURE_COMPLETED_STATUS)} 
            #     #     AND sub_infras.current_status_of_the_site IN {tuple(STRUCTURE_NOT_START_STATUS+STRUCTURE_IN_PROGRESS_STATUS)})
            #     #     OR (sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_IN_PROGRESS_STATUS*2)})) 
            #     #     AND sub_subp.id IN (
            #     #         SELECT sub.id FROM ({_sql}) AS sub 
            #     #     )) 
            #     #     AND (sub_subp.infrastructure_deleted IS NULL OR sub_subp.infrastructure_deleted = 0)
            #     #     AND (sub_infras.infrastructure_deleted IS NULL OR sub_infras.infrastructure_deleted = 0)
            #     # """, _params
            #     f"""
            #     SELECT MIN(id) AS id, joint_subproject_number
            #     FROM subprojects_subproject
            #     WHERE (infrastructure_deleted IS NULL OR infrastructure_deleted = FALSE) AND id IN (SELECT sub.id FROM ({_sql}) AS sub) 
            #     GROUP BY joint_subproject_number
            #     HAVING SUM((current_status_of_the_site NOT IN {_sql_in(STRUCTURE_NOT_START_STATUS*2)})::int) > 0
            #     AND SUM((current_status_of_the_site NOT IN {_sql_in(STRUCTURE_COMPLETED_STATUS)})::int) > 0
            #     """, _params
            # )
            
            # ctx['total_subproject_in_progress'] = len(final_queryset)


            final_queryset = _s.raw(
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
            ctx['total_subproject_completed'] = len(final_queryset)


            final_queryset = _s.raw(
                f"""
                SELECT MIN(id) AS id, joint_subproject_number
                FROM subprojects_subproject
                WHERE (infrastructure_deleted IS NULL OR infrastructure_deleted = FALSE) AND id IN (SELECT sub.id FROM ({_sql}) AS sub)
                GROUP BY joint_subproject_number
                HAVING SUM((current_status_of_the_site NOT IN {_sql_in(STRUCTURE_NOT_START_STATUS*2)})::int) = 0         
                """, _params
            )
            ctx['total_subproject_not_started'] = len(final_queryset)
            # ctx['total_subproject_not_started'] = ctx['total_subproject'] - (ctx['total_subproject_in_progress'] + ctx['total_subproject_completed'])
            

            ctx['total_subproject_in_progress'] = ctx['total_subproject'] - (ctx['total_subproject_not_started'] + ctx['total_subproject_completed'])
            
            
            ctx['total_infrastruture_in_progress'] = all_infrastructures.filter(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS).count()
            ctx['total_infrastruture_completed'] = all_infrastructures.filter(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).count()
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
                        # [
                        #     (
                        #         all_subprojects.filter(subproject_sector=sector).count() #+ \
                        #             # all_subprojects.filter(subproject_sector=sector, has_latrine_blocs=True).count() + \
                        #             #     all_subprojects.filter(subproject_sector=sector, has_fence=True).count()
                        #     ) for sector in sectors
                        # ]
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
                        'data': [costs_dict.get(sector, 0) for sector in sectors]
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
            type_structures = list(TYPES_OF_SUB_PROJECT_COLOR.keys())
            ctx['type_structures'] = type_structures

            # Préparer un dictionnaire pour tous les statuts
            status_map = {
                # "Not start": ~Q(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS + STRUCTURE_IN_PROGRESS_STATUS),
                # "In progress": Q(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS),
                "Completed": Q(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS),
            }

            # Comptes et classes totales par type de structure #.filter(number_of_classrooms__isnull=False)
            all_counts = all_infrastructures.values('type_of_subproject') \
                .annotate(
                    total=Count('id')
                    # ,
                    # total_classrooms=Sum('number_of_classrooms')
                )

            # Conversion en dictionnaires pour accès rapide
            counts_dict = {entry['type_of_subproject']: entry['total'] for entry in all_counts}
            # classrooms_dict = {entry['type_of_subproject']: entry['total_classrooms'] or 0 for entry in all_counts}

            # Comptes par statut
            status_counts_dict = {}
            # status_classrooms_dict = {}

            for label, q_filter in status_map.items():
                qs_count = all_infrastructures.filter(q_filter).values('type_of_subproject')\
                    .annotate(total=Count('id')
                )
                # qs_classrooms = all_infrastructures.filter(q_filter & Q(number_of_classrooms__isnull=False)).values('type_of_subproject')\
                #     .annotate(total_classrooms=Sum('number_of_classrooms')
                # )
                
                status_counts_dict[label] = {entry['type_of_subproject']: entry['total'] for entry in qs_count}
                # status_classrooms_dict[label] = {entry['type_of_subproject']: entry['total_classrooms'] or 0 for entry in qs_classrooms}

            # Construction finale des données pour le graphique
            bars_type_structures = [
                {
                    'label': _("Structure"),
                    'backgroundColor': 'blue',
                    'data': [counts_dict.get(ts, 0) for ts in type_structures],
                    # 'classrooms': [classrooms_dict.get(ts, 0) for ts in type_structures]
                },
                # {
                #     'label': _("Not start"),
                #     'backgroundColor': 'red',
                #     'data': [status_counts_dict["Not start"].get(ts, 0) for ts in type_structures],
                #     # 'classrooms': [status_classrooms_dict["Not start"].get(ts, 0) for ts in type_structures]
                # },
                # {
                #     'label': _("In progress"),
                #     'backgroundColor': 'purple',
                #     'data': [status_counts_dict["In progress"].get(ts, 0) for ts in type_structures],
                #     # 'classrooms': [status_classrooms_dict["In progress"].get(ts, 0) for ts in type_structures]
                # },
                {
                    'label': _("Completed"),
                    'backgroundColor': 'green',
                    'data': [status_counts_dict["Completed"].get(ts, 0) for ts in type_structures],
                    # 'classrooms': [status_classrooms_dict["Completed"].get(ts, 0) for ts in type_structures]
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

            count = 0
            lines_to_skip_for_sum = []

            # --- Parcourir chaque secteur ---
            for sector in [s.upper() for s in sectors]:
                all_subprojects_sector = all_subprojects_include_infrastructures.filter(subproject_sector=sector)

                # Récupérer les types distincts de sous-projets dans ce secteur
                types_in_sector = sorted(all_subprojects_sector.values_list('type_of_subproject', flat=True).distinct())
                
                # Nom du secteur dans toutes les colonnes
                for k in datas.keys():
                    datas[k][count] = _(sector)
                count += 1
                count_start = count

                # Pré-annoter tous les counts pour éviter les multiples requêtes
                aggregated = (
                    all_subprojects_sector
                    .values('type_of_subproject')
                    .annotate(
                        total_subprojects_selected=Count('id', filter=Q(subproject_type_designation="Subproject")),
                        total_structures_to_build=Count('id', filter=Q(number_of_infrastructures=1)),
                        total_projects_launched=Count('id', filter=Q(number_of_infrastructures=1, current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS)),
                        total_works_completed=Count('id', filter=Q(number_of_infrastructures=1, current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS)),
                        total_provisionally_approved=Count('id', filter=Q(number_of_infrastructures=1, current_status_of_the_site__in=STRUCTURE_PROVISIONAL_ACCEPTANCE_STATUS)),
                        total_finally_accepted=Count('id', filter=Q(number_of_infrastructures=1, current_status_of_the_site__in=STRUCTURE_FINAL_ACCEPTANCE_STATUS)),
                        total_classrooms=Sum('number_of_classrooms', filter=Q(number_of_infrastructures=1, number_of_classrooms__isnull=False))
                    )
                )

                agg_dict = {item['type_of_subproject']: item for item in aggregated}

                for _type in types_in_sector:
                    data = agg_dict.get(_type, {})
                    datas[_("Types of work")][count] = _type
                    datas[_("Total number of sub-projects selected")][count] = data.get('total_subprojects_selected', 0)
                    datas[_("Total number of structures to be built")][count] = data.get('total_structures_to_build', 0)
                    datas[_("Total number of projects launched")][count] = data.get('total_projects_launched', 0)
                    datas[_("Total number of works completed")][count] = data.get('total_works_completed', 0)
                    datas[_("Total number of provisionally approved structures")][count] = data.get('total_provisionally_approved', 0)
                    datas[_("Total number of works finally accepted")][count] = data.get('total_finally_accepted', 0)

                    # Calcul spécifique des sub-projects complets (raw SQL)
                    qs_sub = all_subprojects_sector.filter(type_of_subproject=_type, subproject_type_designation="Subproject")
                    if qs_sub.exists():
                        subquery_sql, params = qs_sub.query.get_compiler('default').as_sql()
                        final_qs = qs_sub.raw(
                            # f"""
                            # SELECT DISTINCT sub_subp.id, sub_subp.full_title_of_approved_subproject
                            # FROM subprojects_subproject AS sub_subp
                            # LEFT JOIN subprojects_subproject AS sub_infras ON sub_subp.id = sub_infras.link_to_subproject_id
                            # WHERE (sub_subp.current_status_of_the_site IN {_sql_in(STRUCTURE_COMPLETED_STATUS)}
                            #     AND (sub_infras.current_status_of_the_site IS NULL OR sub_infras.current_status_of_the_site IN {_sql_in(STRUCTURE_COMPLETED_STATUS)}))
                            #     AND sub_subp.id IN (SELECT sub.id FROM ({subquery_sql}) AS sub) 
                            #     AND (sub_subp.infrastructure_deleted IS NULL OR sub_subp.infrastructure_deleted = 0)
                            #     AND (sub_infras.infrastructure_deleted IS NULL OR sub_infras.infrastructure_deleted = 0)
                            # """, params
                            f"""
                            SELECT MIN(id) AS id, joint_subproject_number
                            FROM subprojects_subproject
                            WHERE (infrastructure_deleted IS NULL OR infrastructure_deleted = FALSE) AND id IN (SELECT sub.id FROM ({subquery_sql}) AS sub) 
                            GROUP BY joint_subproject_number
                            HAVING SUM((current_status_of_the_site NOT IN {_sql_in(STRUCTURE_COMPLETED_STATUS)})::int) = 0
                            """, params
                        )
                        datas[_("Total number of sub-projects completed")][count] = len(final_qs)
                    else:
                        datas[_("Total number of sub-projects completed")][count] = 0

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
            #End Summary Recap
            
            
            def get_types_count(qs, sector, status_filter=None):
                """Retourne un dictionnaire {type: count} pour un secteur donné."""
                sector_qs = qs.filter(subproject_sector=sector)
                if status_filter:
                    sector_qs = sector_qs.filter(current_status_of_the_site__in=status_filter)

                return {
                    t.capitalize(): sector_qs.filter(type_of_subproject=t).count()
                    for t in sorted(sector_qs.values_list("type_of_subproject", flat=True).distinct())
                }


            def get_totals(qs, sector, status_filter=None, raw_sql=None, raw_params=None):
                """Retourne les totaux pour un secteur donné."""
                sector_qs = qs.filter(subproject_sector=sector)
                if status_filter:
                    sector_qs = sector_qs.filter(current_status_of_the_site__in=status_filter)

                subprojects_count = (
                    len(qs.raw(raw_sql, raw_params + (sector,))) if raw_sql
                    else sector_qs.filter(subproject_type_designation="Subproject").count()
                )

                infrastructures_count = sector_qs.count()
                return {
                    "subprojects": subprojects_count,
                    "infrastructures": infrastructures_count,
                    "infrastructures_with_latrines_and_fences": infrastructures_count,  # inchangé
                }


            def build_sector_data(base_qs, sectors, status_filter, total_key, raw_sql=None, raw_params=None):
                """Construit les données par secteur pour un statut donné."""
                return {
                    **{
                        sector: {
                            "types": get_types_count(base_qs, sector, status_filter),
                            "total": get_totals(base_qs, sector, status_filter, raw_sql, raw_params),
                        }
                        for sector in sectors
                    },
                    "total": total_key,
                }

            ctx["number_subproject_infrastrutures_by_sectors_and_type"] = {
                _("Identified"): build_sector_data(
                    base_qs=all_infrastructures,
                    sectors=sectors,
                    status_filter=None,
                    total_key=ctx["total_infrastrutures"],
                ),
                _("Completed"): build_sector_data(
                    base_qs=all_infrastructures,
                    sectors=sectors,
                    status_filter=STRUCTURE_COMPLETED_STATUS,
                    total_key=ctx["total_infrastrutures_completed"],
                    raw_sql=f"""
                    SELECT MIN(id) AS id, joint_subproject_number
                    FROM subprojects_subproject
                    WHERE (infrastructure_deleted IS NULL OR infrastructure_deleted = FALSE) AND id IN (SELECT sub.id FROM ({_sql}) AS sub) AND subproject_sector=%s 
                    GROUP BY joint_subproject_number
                    HAVING SUM((current_status_of_the_site NOT IN {_sql_in(STRUCTURE_COMPLETED_STATUS)})::int) = 0
                    """,
                    # f"""
                    #     SELECT DISTINCT sub_subp.id, sub_subp.full_title_of_approved_subproject 
                    #     FROM subprojects_subproject AS sub_subp 
                    #     LEFT JOIN subprojects_subproject AS sub_infras 
                    #         ON sub_subp.id=sub_infras.link_to_subproject_id 
                    #     WHERE (sub_subp.current_status_of_the_site IN {_sql_in(STRUCTURE_COMPLETED_STATUS)}
                    #         AND (sub_infras.current_status_of_the_site IS NULL 
                    #         OR sub_infras.current_status_of_the_site IN {_sql_in(STRUCTURE_COMPLETED_STATUS)})) 
                    #         AND sub_subp.id IN (SELECT sub.id FROM ({_sql}) AS sub) 
                    #         AND sub_subp.subproject_sector=%s 
                    #         AND (sub_subp.infrastructure_deleted IS NULL OR sub_subp.infrastructure_deleted = 0)
                    #         AND (sub_infras.infrastructure_deleted IS NULL OR sub_infras.infrastructure_deleted = 0)
                    # """,
                    raw_params=_params,
                ),
                _("In progress"): build_sector_data(
                    base_qs=all_infrastructures,
                    sectors=sectors,
                    status_filter=STRUCTURE_IN_PROGRESS_STATUS,
                    total_key=ctx["total_infrastrutures_in_progress"],
                    raw_sql=f"""
                    SELECT MIN(id) AS id, joint_subproject_number
                    FROM subprojects_subproject
                    WHERE (infrastructure_deleted IS NULL OR infrastructure_deleted = FALSE) AND id IN (SELECT sub.id FROM ({_sql}) AS sub) AND subproject_sector=%s
                    GROUP BY joint_subproject_number
                    HAVING SUM((current_status_of_the_site NOT IN {_sql_in(STRUCTURE_NOT_START_STATUS*2)})::int) > 0
                        AND SUM((current_status_of_the_site NOT IN {_sql_in(STRUCTURE_COMPLETED_STATUS)})::int) > 0
                    """,
                    # f"""
                    #     SELECT DISTINCT sub_subp.id, sub_subp.full_title_of_approved_subproject 
                    #     FROM subprojects_subproject AS sub_subp 
                    #     LEFT JOIN subprojects_subproject AS sub_infras 
                    #         ON sub_subp.id=sub_infras.link_to_subproject_id 
                    #     WHERE (((sub_subp.current_status_of_the_site IN {_sql_in(STRUCTURE_NOT_START_STATUS*2)} 
                    #         AND sub_infras.current_status_of_the_site IN {tuple(STRUCTURE_COMPLETED_STATUS+STRUCTURE_IN_PROGRESS_STATUS)}) 
                    #         OR (sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_IN_PROGRESS_STATUS+STRUCTURE_COMPLETED_STATUS)} 
                    #         AND sub_infras.current_status_of_the_site IN {tuple(STRUCTURE_NOT_START_STATUS+STRUCTURE_IN_PROGRESS_STATUS)})
                    #         OR (sub_subp.current_status_of_the_site IN {tuple(STRUCTURE_IN_PROGRESS_STATUS*2)})) 
                    #         AND sub_subp.id IN (SELECT sub.id FROM ({_sql}) AS sub) 
                    #         AND sub_subp.subproject_sector=%s) 
                    #         AND (sub_subp.infrastructure_deleted IS NULL OR sub_subp.infrastructure_deleted = 0)
                    #         AND (sub_infras.infrastructure_deleted IS NULL OR sub_infras.infrastructure_deleted = 0)
                    # """,
                    raw_params=_params,
                ),
                _("Not start"): build_sector_data(
                    base_qs=all_infrastructures,
                    sectors=sectors,
                    status_filter=STRUCTURE_NOT_START_STATUS,
                    total_key=ctx["total_infrastrutures_not_started"],
                    raw_sql=f"""
                        SELECT MIN(id) AS id, joint_subproject_number
                        FROM subprojects_subproject
                        WHERE (infrastructure_deleted IS NULL OR infrastructure_deleted = FALSE) AND id IN (SELECT sub.id FROM ({_sql}) AS sub) AND subproject_sector=%s 
                        GROUP BY joint_subproject_number
                        HAVING SUM((current_status_of_the_site NOT IN {_sql_in(STRUCTURE_NOT_START_STATUS*2)})::int) = 0
                    """,
                    # f"""
                    #     SELECT DISTINCT sub_subp.id 
                    #     FROM subprojects_subproject AS sub_subp 
                    #     LEFT JOIN subprojects_subproject AS sub_infras 
                    #         ON sub_infras.link_to_subproject_id=sub_subp.id 
                    #         AND sub_infras.subproject_type_designation='Infrastructure' 
                    #     WHERE (sub_subp.current_status_of_the_site NOT IN {tuple(STRUCTURE_IN_PROGRESS_STATUS+STRUCTURE_COMPLETED_STATUS)} 
                    #         AND (sub_infras.current_status_of_the_site IS NULL 
                    #         OR sub_infras.current_status_of_the_site NOT IN {tuple(STRUCTURE_IN_PROGRESS_STATUS+STRUCTURE_COMPLETED_STATUS)})) 
                    #         AND sub_subp.id IN (SELECT sub.id FROM ({_sql}) AS sub) 
                    #         AND sub_subp.subproject_sector=%s 
                    #         AND (sub_subp.infrastructure_deleted IS NULL OR sub_subp.infrastructure_deleted = 0)
                    #         AND (sub_infras.infrastructure_deleted IS NULL OR sub_infras.infrastructure_deleted = 0)
                    # """,
                    raw_params=_params,
                ),
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
            
            
        
        # ctx['administrative_level_id'] = self.request.GET.getlist('administrative_level_id[]', [])
        # administrative_level_type = self.request.GET.get('administrative_level_type', 'All').title()
        # ctx['subproject_sectors'] = self.filter_list_by_delete_empty(self.request.GET.getlist('id_subproject_sectors[]'))
        # ctx['subproject_types'] = self.filter_list_by_delete_empty(self.request.GET.getlist('id_subproject_types[]'))
        # ctx['works_type_of_subprojects'] = self.filter_list_by_delete_empty(self.request.GET.getlist('id_works_type_of_subproject[]'))
        # ctx['subproject_steps'] = self.filter_list_by_delete_empty(self.request.GET.getlist('id_subproject_step[]'))
        # ctx['components_names'] = self.filter_list_by_delete_empty(self.request.GET.getlist('id_components[]'))
        # ctx['start_date_raw'] = self.request.GET.get('start_date', None)
        # ctx['end_date_raw'] = self.request.GET.get('end_date', None)

        # ctx['all_projects'] = self.request.GET.getlist('all_projects[]') if type(self.request.GET.getlist('all_projects[]')) is list and len(self.request.GET.getlist('all_projects[]')) >= 2 else []

        # ctx['administrative_level_type'] = "All" if administrative_level_type in ("", "null", "undefined") else administrative_level_type

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

        for component_label, component_id in components_mapping.items():
            _cids = Component.expand_ids([component_id])  # 1.x + sous-composantes
            comp_qs = all_subprojects.filter(component_id__in=_cids)

            # Agrégation des montants en une seule passe
            agg = comp_qs.aggregate(
                estimated_cost=Sum('estimated_cost'),
                contract_amount=Sum('contract_amount_work_companies')
            )
            total_estimated = agg['estimated_cost'] or 0
            total_contract = agg['contract_amount'] or 0

            total_allocations = allocations_project.filter(component_id__in=_cids).aggregate(Sum('amount'))['amount__sum'] or 0

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
        agg_total = all_subprojects.aggregate(
            total_estimated_cost=Sum('estimated_cost'),
            total_contract_amount=Sum('contract_amount_work_companies')
        )
        total_estimated = agg_total['total_estimated_cost'] or 0
        total_contract = agg_total['total_contract_amount'] or 0
        total_allocations = allocations_project.aggregate(Sum('amount'))['amount__sum'] or 0

        ctx.update({
            'total_amount_subprojects_estimated_cost': total_estimated,
            'total_amount_subprojects_contract_amount_work_companies': total_contract,
            'total_allocations_cantons': total_allocations,
            'total_amount_remaining_after_allocation': total_allocations - total_estimated,
            'total_amount_residual': total_allocations - total_contract
        })

        # Montants par secteur
        sector_data = [
            all_subprojects.filter(subproject_sector=sector).aggregate(Sum('estimated_cost'))['estimated_cost__sum'] or 0
            for sector in sectors
        ]
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
        
        admls = [adl.administrative_level for adl in lines]

        # Préparer les enfants et allocations
        admls_children = [
            (
                adl,
                allocations_project.filter(administrative_level__id=adl.id),
                [adl.id] + (ctx['queryset_results']['id_with_descendants'].copy().get(str(adl.id)) or []) if ctx['queryset_results']['ald_filter_ids'] else get_administrative_level_ids_descendants(adl.id, None, [], self.request.session.get('project_id'))
            )
            for adl in admls
        ]

        # Fonction pour construire les données par composant
        def build_component_data(component_id, title):
            _cids = Component.expand_ids([component_id])  # 1.x + sous-composantes
            bars = [
                {
                    'label': _("Allocation"),
                    'backgroundColor': 'blue',
                    'data': [
                        adml_alloc.filter(component_id__in=_cids).aggregate(total=Sum('amount'))['total'] or 0
                        for _, adml_alloc, _ in admls_children
                    ]
                },
                {
                    'label': _("Sub-project estimates"),
                    'backgroundColor': 'red',
                    'data': [
                        all_subprojects.filter(
                            Q(location_subproject_realized__id__in=descendants) | Q(canton__id__in=descendants),
                            component_id__in=_cids
                        ).aggregate(total=Sum('estimated_cost'))['total'] or 0
                        for _, _, descendants in admls_children
                    ]
                },
                {
                    'label': _("Spent"),
                    'backgroundColor': 'green',
                    'data': [
                        all_subprojects.filter(
                            Q(location_subproject_realized__id__in=descendants) | Q(canton__id__in=descendants),
                            component_id__in=_cids
                        ).aggregate(total=Sum('contract_amount_work_companies'))['total'] or 0
                        for _, _, descendants in admls_children
                    ]
                }
            ]
            return {
                'title': title,
                'labels': [adl.name for adl, _, _ in admls_children],
                'bars': bars
            }

        # Construire les données pour les composants 1.1, 1.2 et 1.3
        ctx['amount_cantons_component_1_1'] = build_component_data(2, _("Presentation of allocations, estimates and expenditure by canton - Component 1.1"))
        ctx['amount_cantons_component_1_2'] = build_component_data(3, _("Presentation of allocations, estimates and expenditure by canton - Component 1.2"))
        ctx['amount_cantons_component_1_3'] = build_component_data(6, _("Presentation of allocations, estimates and expenditure by canton - Component 1.3"))

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
        
        subprojects = self.get_queryset_search(all_subprojects)
        
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