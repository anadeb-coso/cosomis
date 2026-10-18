from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.http import Http404
from django.urls import reverse_lazy
from django.contrib import messages
from django.views import generic
from django.conf import settings
from django.contrib.auth.decorators import login_required
from storages.backends.s3boto3 import S3Boto3Storage
from cosomis.mixins import AJAXRequestMixin, PageMixin
from .forms import SubprojectForm, VulnerableGroupForm, SubprojectWithoutLinkHeavyObjectsForm
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, Count, Max
from django.db.models.functions import Coalesce
from django.core.exceptions import PermissionDenied
from datetime import datetime

from cosomis.datatables import (
    DATATABLE_EXPORT_BUTTONS_OPTIONS, DatatableColumn, ServerSideDatatableMixin, get_filter_badges
)
from subprojects.models import Subproject, VulnerableGroup, SubprojectFile, Project, Component
from django import forms
from subprojects import functions as subprojects_functions
from administrativelevels.libraries import download_file
from usermanager.permissions import (
    CDDSpecialistPermissionRequiredMixin, SuperAdminPermissionRequiredMixin,
    AdminPermissionRequiredMixin, InfraPermissionRequiredMixin, EvaluatorPermissionRequiredMixin
    )
from cosomis.constants import (
    SUB_PROJECT_STATUS_COLOR_TRANSLATE, TYPES_OF_SUB_PROJECT_COLOR, SUB_PROJECT_SECTORS_COLOR, 
    STRUCTURE_NOT_START_STATUS, STRUCTURE_IN_PROGRESS_ALL_STATUS, STRUCTURE_COMPLETED_STATUS, 
    STRUCTURE_COMPLETED_ALL_STATUS, STRUCTURE_IN_PROGRESS_STATUS, IMAGE_EXTENSIONS,
    IN_PROGRESS_RANKING, NOT_APPROVED_BY_CORA_RANKING, COMPLETED_RANKING
)
from administrativelevels.functions_adl import get_cascade_villages_ids_by_administrative_level_id
from dashboard.forms import AdministrativeLevelFilterForm, ADMIN_LEVEL_FILTER_LABELS, get_admin_level_filter_fields
from subprojects.forms import SubprojectFilterForm, SearchForm
from assignments.models import AssignAdministrativeLevelToFacilitator
from administrativelevels.models import AdministrativeLevel

class SubprojectMixin:
    subproject = None
    permissions = ('read', 'write')
    has_permission = True

    def get_query_result(self, **kwargs):
        try:
            return Subproject.objects.get(id=kwargs['subproject_id'])
        except Exception as exc:
            raise Http404
        

    def check_permissions(self):
        pass

    def specific_permissions(self):
        user = self.request.user
        if not (
                user.groups.all().exists()
            ):
            raise PermissionDenied
        
    def dispatch(self, request, *args, **kwargs):
        subproject = self.get_query_result(**kwargs)
        try:
            self.subproject = subproject
        except Exception:
            raise Http404

        self.check_permissions()
        if not self.has_permission:
            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context
    

def get_subprojects_search_q(search):
    """Text search of the subprojects/infrastructures lists ("Search in database")."""
    search = search.upper()
    return (
        Q(number__icontains=search) |
        Q(linked_subprojects__number__icontains=search) |
        Q(joint_subproject_number__icontains=search) |
        Q(full_title_of_approved_subproject__icontains=search) |

        # Location
        Q(location_subproject_realized__name__icontains=search) |
        Q(linked_subprojects__location_subproject_realized__name__icontains=search) |
        Q(location_subproject_realized__parent__name__icontains=search) |
        Q(linked_subprojects__location_subproject_realized__parent__name__icontains=search) |
        Q(location_subproject_realized__parent__parent__name__icontains=search) |
        Q(linked_subprojects__location_subproject_realized__parent__parent__name__icontains=search) |
        Q(location_subproject_realized__parent__parent__parent__name__icontains=search) |
        Q(linked_subprojects__location_subproject_realized__parent__parent__parent__name__icontains=search) |
        Q(location_subproject_realized__parent__parent__parent__parent__name__icontains=search) |
        Q(linked_subprojects__location_subproject_realized__parent__parent__parent__parent__name__icontains=search) |
        Q(cvd__name__icontains=search) |
        #canton
        Q(canton__name__icontains=search) |
        Q(linked_subprojects__canton__name__icontains=search) |
        Q(canton__parent__name__icontains=search) |
        Q(linked_subprojects__canton__parent__name__icontains=search) |
        Q(canton__parent__parent__name__icontains=search) |
        Q(linked_subprojects__canton__parent__parent__name__icontains=search) |
        Q(canton__parent__parent__parent__name__icontains=search) |
        Q(linked_subprojects__canton__parent__parent__parent__name__icontains=search) |

        Q(subproject_sector__icontains=search) |
        Q(type_of_subproject__icontains=search) |
        Q(linked_subprojects__type_of_subproject__icontains=search) |
        Q(works_type__icontains=search) |
        Q(linked_subprojects__works_type__icontains=search) |
        Q(facilitator_name__icontains=search)
    )


def get_subproject_region_ordering():
    """Region of the subproject's site (village, or canton for cantonal ones)."""
    return Coalesce(
        'location_subproject_realized__parent__parent__parent__parent__name',
        'canton__parent__parent__parent__name',
    )


SUBPROJECT_LOCATION_RELATED = (
    'location_subproject_realized__parent__parent__parent__parent',
    'canton__parent__parent__parent',
)


class SubprojectDatatableRowsMixin:
    def get_datatable_shared_context(self):
        ctx = super().get_datatable_shared_context()
        user = self.request.user
        ctx['can_edit'] = user.is_superuser or user.groups.filter(name__in=("Admin", "Evaluator", "Infra")).exists()
        return ctx


class SubprojectsListView(PageMixin, LoginRequiredMixin, SubprojectDatatableRowsMixin, ServerSideDatatableMixin, generic.ListView):
    model = Subproject
    template_name = 'subprojects_list.html'
    context_object_name = 'subprojects'
    title = _('Subprojects')
    active_level1 = 'subprojects'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]
    datatable_row_template = 'datatable/subproject_row.html'
    datatable_default_order = ([0, 'asc'],)

    def get_datatable_columns(self):
        return [
            DatatableColumn(_('N°'), ('number', 'joint_subproject_number')),
            DatatableColumn(_('Sites')),
            DatatableColumn(_('Region'), get_subproject_region_ordering()),
            DatatableColumn(_('Project Name'), 'full_title_of_approved_subproject'),
            DatatableColumn(_('Type'), 'type_of_subproject'),
            DatatableColumn(_('Status')),
            DatatableColumn(_('Estimated cost'), 'estimated_cost'),
            DatatableColumn(_('Action'), switchable=False),
        ]

    def get_datatable_queryset(self):
        subprojects = Subproject.objects.get_objects_by_general_filtre(self.request, None).filter(link_to_subproject=None)
        search = self.request.GET.get("search", None)
        if search and search != "All":
            subprojects = subprojects.filter(get_subprojects_search_q(search)).distinct()
        return subprojects.get_actifs().select_related(*SUBPROJECT_LOCATION_RELATED)

    def get_context_data(self, **kwargs):
        ctx = super(SubprojectsListView, self).get_context_data(**kwargs)
        ctx['hide_content_header'] = True
        ctx['search'] = self.request.GET.get("search", None)
        ctx['filter_badges'] = [{'label': _('Search'), 'value': ctx['search']}] if ctx['search'] and ctx['search'] != "All" else []
        ctx['reset_url'] = reverse_lazy('subprojects:list')
        all = Subproject.objects.get_objects_by_general_filtre(self.request, None).get_actifs()
        # ctx['total'] = all.count()
        # ctx['total_without_link'] = all.filter(link_to_subproject=None, subproject_type_designation="Subproject").count()
        ctx['total_subproject'] = all.filter(subproject_type_designation="Subproject").count()
        # ctx['total_infrastruture'] = all.filter(subproject_type_designation="Infrastructure").count()
        # ctx['total_latrine_blocks'] = all.filter(has_latrine_blocs=True).count()
        # ctx['total_fences'] = all.filter(has_fence=True).count()
        ctx['total_infrastrutures'] = all.count() #= ctx['total'] #+ ctx['total_latrine_blocks'] + ctx['total_fences']
        return ctx


class InfrastructuresListView(PageMixin, LoginRequiredMixin, SubprojectDatatableRowsMixin, ServerSideDatatableMixin, generic.ListView):
    model = Subproject
    template_name = 'infrastructures_list.html'
    context_object_name = 'infrastructures'
    title = _('Infrastructures')
    active_level1 = 'infrastructures'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]
    datatable_row_template = 'datatable/infrastructure_row.html'
    datatable_options = DATATABLE_EXPORT_BUTTONS_OPTIONS

    def get_datatable_columns(self):
        return [
            DatatableColumn(_('N°'), ('number', 'joint_subproject_number')),
            DatatableColumn(_('Region'), get_subproject_region_ordering()),
            DatatableColumn(_('Sites')),
            DatatableColumn(_('Project Name'), 'full_title_of_approved_subproject'),
            DatatableColumn(_('Type'), 'type_of_subproject'),
            DatatableColumn(_('Status')),
            DatatableColumn(_('Estimated cost'), 'estimated_cost'),
            DatatableColumn('CT', 'photos_count'),
            DatatableColumn('CV', 'photos_completed_validated_count'),
            DatatableColumn('CIV', 'photos_completed_invalidated_count'),
            DatatableColumn('TV', 'photos_validated_count'),
            DatatableColumn('TIN', 'photos_invalidated_count'),
            DatatableColumn('UR1', 'photos_unreview1_count'),
            DatatableColumn('UR', 'photos_unreview_count'),
            DatatableColumn(_('Action'), switchable=False),
        ]

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
        
    def get_filters_context(self):
        kwargs = dict()

        kwargs["all_projects"] = self.request.session.get('tree_structure_projects_ids') if self.request.GET.get('include_all_projects', 0) in (1, '1') else []

        id_regions = self.filter_list_by_delete_empty(self.request.GET.getlist('region', []))
        id_prefectures = self.filter_list_by_delete_empty(self.request.GET.getlist('prefecture', []))
        id_communes = self.filter_list_by_delete_empty(self.request.GET.getlist('commune', []))
        id_cantons = self.filter_list_by_delete_empty(self.request.GET.getlist('canton', []))
        id_villages = self.filter_list_by_delete_empty(self.request.GET.getlist('village', []))
        subproject_sectors = self.filter_list_by_delete_empty(self.request.GET.getlist('subproject_sectors'))
        subproject_types = self.filter_list_by_delete_empty(self.request.GET.getlist('subproject_types'))
        works_type_of_subprojects = self.filter_list_by_delete_empty(self.request.GET.getlist('works_type_of_subproject'))
        subproject_steps = self.filter_list_by_delete_empty(self.request.GET.getlist('subproject_step'))
        components = self.filter_list_by_delete_empty(self.request.GET.getlist('components'))
        start_date_raw = self.request.GET.get('start_date', None)
        end_date_raw = self.request.GET.get('end_date', None)

        kwargs["id_regions_selected"] = id_regions
        kwargs["id_prefectures_selected"] = id_prefectures
        kwargs["id_communes_selected"] = id_communes
        kwargs["id_cantons_selected"] = id_cantons
        kwargs["id_villages_selected"] = id_villages
        kwargs["subproject_sectors_selected"] = subproject_sectors
        kwargs["subproject_types_selected"] = subproject_types
        kwargs["works_type_of_subproject_selected"] = works_type_of_subprojects
        kwargs["subproject_steps_selected"] = subproject_steps
        kwargs["components_selected"] = components
        kwargs["start_date_raw_selected"] = start_date_raw
        kwargs["end_date_raw_selected"] = end_date_raw
        kwargs["include_all_projects_checked"] = self.request.GET.get('include_all_projects')
        
        adm_queryset = AdministrativeLevel.objects.all()
        kwargs["regions"] = adm_queryset.filter(type=AdministrativeLevel.REGION)

        kwargs["prefectures"] = adm_queryset.filter(type=AdministrativeLevel.PREFECTURE)
        if id_regions:
            kwargs["prefectures"] = kwargs["prefectures"].filter(
                parent__id__in=id_regions
            )

        kwargs["communes"] = adm_queryset.filter(type=AdministrativeLevel.COMMUNE)
        if id_prefectures:
            kwargs["communes"] = kwargs["communes"].filter(
                parent__id__in=id_prefectures
            )
        elif id_regions:
            kwargs["communes"] = kwargs["communes"].filter(
                parent__parent__id__in=id_regions
            )

        kwargs["cantons"] = adm_queryset.filter(type=AdministrativeLevel.CANTON)
        if id_communes:
            kwargs["cantons"] = kwargs["cantons"].filter(
                parent__id__in=id_communes
            )
        elif id_prefectures:
            kwargs["cantons"] = kwargs["cantons"].filter(
                parent__parent__id__in=id_prefectures
            )
        elif id_regions:
            kwargs["cantons"] = kwargs["cantons"].filter(
                parent__parent__parent__id__in=id_regions
            )

        kwargs["villages"] = adm_queryset.filter(type=AdministrativeLevel.VILLAGE)
        if id_cantons:
            kwargs["villages"] = kwargs["villages"].filter(
                parent__id__in=id_cantons
            )
        elif id_communes:
            kwargs["villages"] = kwargs["villages"].filter(
                parent__parent__id__in=id_communes
            )
        elif id_prefectures:
            kwargs["villages"] = kwargs["villages"].filter(
                parent__parent__parent__id__in=id_prefectures
            )
        elif id_regions:
            kwargs["villages"] = kwargs["villages"].filter(
                parent__parent__parent__parent__id__in=id_regions
            )

        return kwargs

    def get_datatable_queryset(self):

        # --- Récupération des paramètres ---
        search = self.request.GET.get("search", None)
        id_regions = self.filter_list_by_delete_empty(self.request.GET.getlist('region', []))
        id_prefectures = self.filter_list_by_delete_empty(self.request.GET.getlist('prefecture', []))
        id_communes = self.filter_list_by_delete_empty(self.request.GET.getlist('commune', []))
        id_cantons = self.filter_list_by_delete_empty(self.request.GET.getlist('canton', []))
        id_villages = self.filter_list_by_delete_empty(self.request.GET.getlist('village', []))
        subproject_sectors = self.filter_list_by_delete_empty(self.request.GET.getlist('subproject_sectors'))
        subproject_types = self.filter_list_by_delete_empty(self.request.GET.getlist('subproject_types'))
        works_type_of_subprojects = self.filter_list_by_delete_empty(self.request.GET.getlist('works_type_of_subproject'))
        subproject_steps = self.filter_list_by_delete_empty(self.request.GET.getlist('subproject_step'))
        components = self.filter_list_by_delete_empty(self.request.GET.getlist('components'))
        start_date_raw = self.request.GET.get('start_date', None)
        end_date_raw = self.request.GET.get('end_date', None)
        include_all_projects_checked = self.request.GET.get('include_all_projects', 0) in (1, '1')

        infrastructures = Subproject.objects.get_actifs()

        all_projects = self.request.session.get('tree_structure_projects_ids') if include_all_projects_checked else []
        infrastructures = infrastructures.filter(projects__in=(
                all_projects if type(all_projects) is list and len(all_projects) >= 2 else [self.request.session.get('project_id')]
            )
        )

        start_date = None
        end_date = None
        liste_villages = []
        type_field = None

        images_filter_query = Q()
        for ext in IMAGE_EXTENSIONS:
            images_filter_query |= Q(subprojectfile__url__icontains=ext)

        file_query_for_subproject = Q()
        for elt in STRUCTURE_COMPLETED_ALL_STATUS:
            file_query_for_subproject |= Q(subprojectfile__subproject_step__wording__icontains=elt)
            file_query_for_subproject |= Q(subprojectfile__name__icontains=elt)
            file_query_for_subproject |= Q(subprojectfile__description__icontains=elt)
        
        if search and search != "All":
            infrastructures = infrastructures.filter(get_subprojects_search_q(search))

        if start_date_raw:
            start_date = self.parse_fr_date(start_date_raw)
        if end_date_raw:
            end_date = self.parse_fr_date(end_date_raw)
        
        if (
            (id_regions and 'All' not in id_regions) or 
            (id_prefectures and 'All' not in id_prefectures) or 
            (id_communes and 'All' not in id_communes) or 
            (id_cantons and 'All' not in id_cantons) or 
            (id_villages and 'All' not in id_villages)
        ):
            if id_villages:
                _ids = id_villages
                type_field = "village"
            elif id_cantons:
                _ids = id_cantons
            elif id_communes:
                _ids = id_communes
            elif id_prefectures:
                _ids = id_prefectures
            elif id_regions:
                _ids = id_regions
                
            if type_field == "village":
                liste_villages = [int(_id) for _id in _ids if _id]
            else:
                _ids = [_id for _id in _ids if _id not in ('All', '')]
                liste_villages += (_ids + get_cascade_villages_ids_by_administrative_level_id(_ids))
        
        if start_date or end_date:
            if not subproject_steps:
                infrastructures = infrastructures.filter(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS)
                
                if start_date and end_date:
                    infrastructures = infrastructures.filter(
                        work_completion_date__range=[start_date, end_date]
                    )
                elif start_date:
                    infrastructures = infrastructures.filter(
                        work_completion_date__gte=start_date
                    )
                else:
                    infrastructures = infrastructures.filter(
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
                    infrastructures = infrastructures.filter(Q(
                        Q(Q(subprojectstep__begin__range=[start_date, end_date]) & q)
                    )).distinct()
                elif start_date:
                    infrastructures = infrastructures.filter(Q(
                        Q(Q(subprojectstep__begin__gte=start_date) & q)
                    )).distinct()
                else:
                    infrastructures = infrastructures.filter(Q(
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
            infrastructures = infrastructures.filter(q)

        if components:
            infrastructures = infrastructures.filter(
                component_id__in=Component.expand_names(components))  # + sous-composantes
        
        if subproject_sectors:
            infrastructures = infrastructures.filter(subproject_sector__in=[elt for elt in subproject_sectors if elt])
        
        if subproject_types:
            infrastructures = infrastructures.filter(type_of_subproject__in=[elt for elt in subproject_types if elt])
            
        if works_type_of_subprojects:
            infrastructures = infrastructures.filter(works_type__in=[elt for elt in works_type_of_subprojects if elt])

        if liste_villages:
            infrastructures = infrastructures.filter(
                Q(location_subproject_realized__id__in=liste_villages) |
                Q(canton__id__in=liste_villages)
            )

        
        # ---------FILES count---------------
        infrastructures = infrastructures.annotate(
            photos_count=Count(
                'subprojectfile',
                filter=Q(
                    Q(subprojectfile__subproject_step__wording__in=STRUCTURE_COMPLETED_STATUS) |
                    Q(subprojectfile__name__in=STRUCTURE_COMPLETED_STATUS) |
                    Q(subprojectfile__description__in=STRUCTURE_COMPLETED_STATUS) |
                    file_query_for_subproject
                ) & images_filter_query,
                distinct=True
            ),
            photos_completed_validated_count=Count(
                'subprojectfile',
                filter=Q(
                    Q(subprojectfile__subproject_step__wording__in=STRUCTURE_COMPLETED_STATUS) |
                    Q(subprojectfile__name__in=STRUCTURE_COMPLETED_STATUS) |
                    Q(subprojectfile__description__in=STRUCTURE_COMPLETED_STATUS) |
                    file_query_for_subproject
                ) & images_filter_query & Q(subprojectfile__validated=True),
                distinct=True
            ),
            photos_completed_invalidated_count=Count(
                'subprojectfile',
                filter=Q(
                    Q(subprojectfile__subproject_step__wording__in=STRUCTURE_COMPLETED_STATUS) |
                    Q(subprojectfile__name__in=STRUCTURE_COMPLETED_STATUS) |
                    Q(subprojectfile__description__in=STRUCTURE_COMPLETED_STATUS) |
                    file_query_for_subproject
                ) & images_filter_query & Q(subprojectfile__validated=False),
                distinct=True
            ),
            photos_validated_count=Count(
                'subprojectfile',
                filter=images_filter_query & Q(subprojectfile__validated=True),
                distinct=True
            ),
            photos_invalidated_count=Count(
                'subprojectfile',
                filter=images_filter_query & Q(subprojectfile__validated=False),
                distinct=True
            ),
            photos_unreview1_count=Count(
                'subprojectfile',
                filter=images_filter_query & Q(subprojectfile__validated=None),
                distinct=True
            ),
            photos_unreview_count=Count(
                'subprojectfile',
                filter=images_filter_query & Q(subprojectfile__review=False),
                distinct=True
            ),
            last_file_updated=Max(
                'subprojectfile__updated_date',
                filter=Q(
                    Q(subprojectfile__subproject_step__wording__in=STRUCTURE_COMPLETED_STATUS) |
                    Q(subprojectfile__name__in=STRUCTURE_COMPLETED_STATUS) |
                    Q(subprojectfile__description__in=STRUCTURE_COMPLETED_STATUS) |
                    file_query_for_subproject
                ) & images_filter_query
            )
        ).order_by('-last_file_updated', 'photos_completed_validated_count', '-photos_completed_invalidated_count', '-photos_invalidated_count', '-photos_unreview_count')
        # ---------End FILES count---------------

        return infrastructures.select_related('link_to_subproject', *SUBPROJECT_LOCATION_RELATED)

    def get_context_data(self, **kwargs):
        ctx = super(InfrastructuresListView, self).get_context_data(**kwargs)
        ctx.update(self.get_filters_context())

        ctx['hide_content_header'] = True

        ctx['search'] = self.request.GET.get("search", None)
        ctx['reset_url'] = reverse_lazy('subprojects:infrastructures_list')

        ctx['form_adl'] = AdministrativeLevelFilterForm(
            has_all=False, 

            regions=ctx.get('regions', []),
            prefectures=ctx.get('prefectures', []),
            communes=ctx.get('communes', []),
            cantons=ctx.get('cantons', []),
            villages=ctx.get('villages', []),

            default_regions=ctx.get('id_regions_selected', []),
            default_prefectures=ctx.get('id_prefectures_selected', []),
            default_communes=ctx.get('id_communes_selected', []),
            default_cantons=ctx.get('id_cantons_selected', []),
            default_villages=ctx.get('id_villages_selected', []),
        )
        
        ctx['form_suproject'] = SubprojectFilterForm(
            has_all=False,

            default_subproject_sectors=ctx.get('subproject_sectors_selected', []), 
            default_subproject_types=ctx.get('subproject_types_selected', []), 
            default_works_type_of_subproject=ctx.get('works_type_of_subproject_selected', []),
            default_subproject_steps=ctx.get('subproject_steps_selected', []), 
            default_components=ctx.get('components_selected', [])
        )
        
        ctx['form_searcht'] = SearchForm(
            default_start_date=ctx.get('start_date_raw_selected', []),
            default_end_date=ctx.get('end_date_raw_selected', [])
        )

        ctx['adm_filter_fields'] = get_admin_level_filter_fields(ctx['form_adl'])
        ctx['filter_badges'] = (
            get_filter_badges(ctx['form_suproject'], {
                'components': _('Component'),
                'subproject_step': _('Status'),
                'subproject_sectors': _('Subproject sector'),
                'subproject_types': _('Type of structure'),
                'works_type_of_subproject': _('Works type'),
            })
            + get_filter_badges(ctx['form_searcht'], {'start_date': _('Start Date'), 'end_date': _('End Date')})
            + get_filter_badges(ctx['form_adl'], ADMIN_LEVEL_FILTER_LABELS)
        )
        if ctx['search'] and ctx['search'] != "All":
            ctx['filter_badges'].append({'label': _('Search'), 'value': ctx['search']})
        if ctx['include_all_projects_checked'] in (1, '1'):
            ctx['filter_badges'].append({
                'label': _('Show for all projects'),
                'value': ', '.join(str(name) for name in self.request.session.get('tree_structure_projects_names') or []),
            })

        return ctx
    

class SubprojectsMapViewPage(generic.TemplateView):

    template_name = 'subprojects_map_page.html'
    title = _('Subprojects')
    active_level1 = 'subprojects'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['access_token'] = settings.MAPBOX_ACCESS_TOKEN
        context['lat'] = settings.DIAGNOSTIC_MAP_LATITUDE
        context['lng'] = settings.DIAGNOSTIC_MAP_LONGITUDE
        context['zoom'] = settings.DIAGNOSTIC_MAP_ZOOM
        context['ws_bound'] = settings.DIAGNOSTIC_MAP_WS_BOUND
        context['en_bound'] = settings.DIAGNOSTIC_MAP_EN_BOUND
        context['country_iso_code'] = settings.DIAGNOSTIC_MAP_ISO_CODE
        context['sub_project_status_color_translation'] = SUB_PROJECT_STATUS_COLOR_TRANSLATE
        context['types_of_sub_project_color'] = TYPES_OF_SUB_PROJECT_COLOR
        context['sectors_of_sub_project_color'] = SUB_PROJECT_SECTORS_COLOR
        context['hide_content_header'] = True
        context['form'] = AdministrativeLevelFilterForm(False)
        context['form_suproject'] = SubprojectFilterForm(False)

        
        context['map_canvas_heigth'] = self.request.GET.get('map-heigth')
        context['map_canvas_width'] = self.request.GET.get('map-width')

        return context

    def render_to_response(self, context, **response_kwargs):
        """
        Return a response, using the `response_class` for this view, with a
        template rendered with the given context.
        Pass response_kwargs to the constructor of the response class.
        """
        response_kwargs.setdefault('content_type', self.content_type)
        return self.response_class(
            request=self.request,
            template=self.get_template_names(),
            context=context,
            using=self.template_engine,
            **response_kwargs
        )
    

class SubprojectsMapWideViewPage(generic.TemplateView):

    template_name = 'subprojects_map_page_wide.html'
    title = _('Subprojects')
    active_level1 = 'subprojects'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['access_token'] = settings.MAPBOX_ACCESS_TOKEN
        context['lat'] = settings.DIAGNOSTIC_MAP_LATITUDE
        context['lng'] = settings.DIAGNOSTIC_MAP_LONGITUDE
        context['zoom'] = settings.DIAGNOSTIC_MAP_ZOOM
        context['ws_bound'] = settings.DIAGNOSTIC_MAP_WS_BOUND
        context['en_bound'] = settings.DIAGNOSTIC_MAP_EN_BOUND
        context['country_iso_code'] = settings.DIAGNOSTIC_MAP_ISO_CODE
        context['sub_project_status_color_translation'] = SUB_PROJECT_STATUS_COLOR_TRANSLATE
        context['types_of_sub_project_color'] = TYPES_OF_SUB_PROJECT_COLOR
        context['hide_content_header'] = True
        context['form'] = AdministrativeLevelFilterForm(False)
        context['form_suproject'] = SubprojectFilterForm(False)
        return context

    def render_to_response(self, context, **response_kwargs):
        """
        Return a response, using the `response_class` for this view, with a
        template rendered with the given context.
        Pass response_kwargs to the constructor of the response class.
        """
        response_kwargs.setdefault('content_type', self.content_type)
        return self.response_class(
            request=self.request,
            template=self.get_template_names(),
            context=context,
            using=self.template_engine,
            **response_kwargs
        )

class SubprojectsMapView(generic.ListView):
    template_name = 'subprojects_map_view.html'
    context_object_name = 'subprojects'
    title = _('Subprojects')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['access_token'] = settings.MAPBOX_ACCESS_TOKEN
        context['lat'] = settings.DIAGNOSTIC_MAP_LATITUDE
        context['lng'] = settings.DIAGNOSTIC_MAP_LONGITUDE
        context['zoom'] = settings.DIAGNOSTIC_MAP_ZOOM
        context['ws_bound'] = settings.DIAGNOSTIC_MAP_WS_BOUND
        context['en_bound'] = settings.DIAGNOSTIC_MAP_EN_BOUND
        context['country_iso_code'] = settings.DIAGNOSTIC_MAP_ISO_CODE
        context['sub_project_status_color_translation'] = SUB_PROJECT_STATUS_COLOR_TRANSLATE
        context['types_of_sub_project_color'] = TYPES_OF_SUB_PROJECT_COLOR
        return context

    def filter_list_by_delete_empty(self, _list):
        if _list:
            return [elt for elt in _list if elt]
        else:
            return []
    
    def get_results(self):
        id_regions = self.filter_list_by_delete_empty(self.request.GET.getlist('id_region[]'))
        id_prefectures = self.filter_list_by_delete_empty(self.request.GET.getlist('id_prefecture[]'))
        id_communes = self.filter_list_by_delete_empty(self.request.GET.getlist('id_commune[]'))
        id_cantons = self.filter_list_by_delete_empty(self.request.GET.getlist('id_canton[]'))
        id_villages = self.filter_list_by_delete_empty(self.request.GET.getlist('id_village[]'))
        subproject_sectors = self.filter_list_by_delete_empty(self.request.GET.getlist('id_subproject_sectors[]'))
        subproject_types = self.filter_list_by_delete_empty(self.request.GET.getlist('id_subproject_types[]'))
        works_type_of_subprojects = self.filter_list_by_delete_empty(self.request.GET.getlist('id_works_type_of_subproject[]'))
        subproject_steps = self.filter_list_by_delete_empty(self.request.GET.getlist('id_subproject_step[]'))
        type_field = self.request.GET.get('type_field')
        _ids = []
        liste_villages = []
        
        if (id_regions or id_prefectures or id_communes or id_cantons or id_villages) and type_field:
            if id_regions and type_field == "region":
                _ids = id_regions
            elif id_prefectures and type_field == "prefecture":
                _ids = id_prefectures
            elif id_communes and type_field == "commune":
                _ids = id_communes
            elif id_cantons and type_field == "canton":
                _ids = id_cantons
            elif id_villages and type_field == "village":
                _ids = id_villages
                
            if type_field == "village":
                liste_villages = [int(_id) for _id in _ids if _id]
            else:
                for _id in _ids:
                    if _id:
                        liste_villages += get_cascade_villages_ids_by_administrative_level_id(_id)
            subprojects = Subproject.objects.get_objects_by_general_filtre(self.request, None).filter(
                Q(location_subproject_realized_id__in=liste_villages) | 
                Q(list_of_villages_crossed_by_the_track_or_electrification__id__in=liste_villages)
            ).get_actifs()
        elif (id_regions or id_prefectures or id_communes or id_cantons or id_villages):
            if id_villages:
                _ids = id_villages
            elif id_cantons:
                _ids = id_cantons
            elif id_communes:
                _ids = id_communes
            elif id_prefectures:
                _ids = id_prefectures
            elif id_regions:
                _ids = id_regions
                
            if type_field == "village":
                liste_villages = [int(_id) for _id in _ids if _id]
            else:
                for _id in _ids:
                    if _id:
                        liste_villages += get_cascade_villages_ids_by_administrative_level_id(_id)
            subprojects = Subproject.objects.get_objects_by_general_filtre(self.request, None).filter(
                Q(location_subproject_realized_id__in=liste_villages) | 
                Q(list_of_villages_crossed_by_the_track_or_electrification__id__in=liste_villages)
            ).get_actifs()

        else:
            subprojects = Subproject.objects.get_objects_by_general_filtre(self.request, None).get_actifs()
        
        if subproject_sectors:
            subprojects = subprojects.filter(subproject_sector__in=[elt for elt in subproject_sectors if elt])
        
        if subproject_types:
            subprojects = subprojects.filter(type_of_subproject__in=[elt for elt in subproject_types if elt])
            
        if works_type_of_subprojects:
            subprojects = subprojects.filter(works_type__in=[elt for elt in works_type_of_subprojects if elt])
        
        # if subproject_steps:
        #     _subprojects = []
        #     for subproject in subprojects:
        #         # subproject_step = subproject.get_current_subproject_step
        #         # if subproject_step:
        #         #     if 'not_started' in subproject_steps and subproject_step.ranking < IN_PROGRESS_RANKING and subproject_step.ranking not in (NOT_APPROVED_BY_CORA_RANKING,):
        #         #         _subprojects.append(subproject)
        #         #     if 'in_progress' in subproject_steps and subproject_step.ranking == IN_PROGRESS_RANKING:
        #         #         _subprojects.append(subproject)
        #         #     if 'completed' in subproject_steps and subproject_step.ranking > IN_PROGRESS_RANKING and subproject_step.ranking not in (ABANDONED_RANKING, INTERRUPTED_RANKING):
        #         #         _subprojects.append(subproject)
        #         subproject_step = subproject.current_status_of_the_site
        #         if subproject_step:
        #             if 'not_started' in subproject_steps and subproject_step == "Identifié":
        #                 _subprojects.append(subproject)
        #             if 'in_progress' in subproject_steps and subproject_step == "En cours":
        #                 _subprojects.append(subproject)
        #             if 'completed' in subproject_steps and subproject_step in ("Achevé", \
        #                     "Réception technique", "Réception provisoire", "Réception définitive"):
        #                 _subprojects.append(subproject)

        #     subprojects = _subprojects
        if subproject_steps:
            q = Q()
            if 'not_started' in subproject_steps:
                q |= Q(current_status_of_the_site__in=STRUCTURE_NOT_START_STATUS)
            if 'in_progress' in subproject_steps:
                q |= Q(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS)
            if 'completed' in subproject_steps:
                q |= Q(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS)
            subprojects = subprojects.filter(q)
            
        return subprojects

    def get_queryset(self):
        return self.get_results()



class SubprojectDetailView(LoginRequiredMixin, generic.DetailView):
    model = Subproject
    template_name = 'subproject.html'
    context_object_name = 'subproject'
    title = _('Subproject')
    active_level1 = 'subprojects'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def get_context_data(self, **kwargs):
        try:
            context = super().get_context_data(**kwargs)
            context['preview_page'] = reverse_lazy('subprojects:list')
            context['object_title'] = _('Subproject Detail').__str__()

            return context
        except:
            raise Http404


class SubprojectCreateView(PageMixin, LoginRequiredMixin, EvaluatorPermissionRequiredMixin, generic.CreateView):
    model = Subproject
    template_name = 'subproject_create.html'
    context_object_name = 'subproject'
    title = _('Create Subproject')
    active_level1 = 'subprojects'
    breadcrumb = [
        {
            'url': reverse_lazy('subprojects:list'),
            'title': _('subprojects')
        },
        {
            'url': '',
            'title': title
        },
    ]
 
    form_class = SubprojectForm # specify the class form to be displayed
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.form_mixin:
            context['form'] = self.form_mixin
        else:
            context['form'] = SubprojectForm()
        return context

    def post(self, request, *args, **kwargs):
        form = SubprojectForm(request.POST)
        if form.is_valid():
            subproject = form.save()
            if subproject.location_subproject_realized and subproject.location_subproject_realized.cvd:
                subproject.cvd = subproject.location_subproject_realized.cvd
            subproject.save(user=self.request.user)
            if subproject.id:
                return redirect('subprojects:detail', pk=subproject.id)
            return redirect('subprojects:list')
        self.form_mixin = form
        return super(SubprojectCreateView, self).get(request, *args, **kwargs)
    

class SubprojectUpdateView(PageMixin, LoginRequiredMixin, InfraPermissionRequiredMixin, generic.UpdateView):
    model = Subproject
    template_name = 'subproject_create.html'
    context_object_name = 'subproject'
    title = _('Update Subproject')
    active_level1 = 'subprojects'
    breadcrumb = [
        {
            'url': reverse_lazy('subprojects:list'),
            'title': _('subprojects')
        },
        {
            'url': '',
            'title': title
        },
    ]
 
    form_class = SubprojectForm # specify the class form to be displayed
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        _object = self.get_object()
        
        if _object.subproject_type_designation == "Infrastructure":
            context['title'] = f"{_('Update the infrastructure')} / {_object.location_subproject_realized.name}" if _object.location_subproject_realized else _('Update the infrastructure')
        elif _object.subproject_type_designation == "Subproject":
            context['title'] = f"{_('Update the subproject')} / {_object.location_subproject_realized.name}" if _object.location_subproject_realized else _('Update the subproject')
        context['breadcrumb'][1]['title'] = context['title']

        if self.form_mixin:
            context['form'] = self.form_mixin
        else:
            context['form'] = SubprojectForm(instance=_object)
        return context
    def post(self, request, *args, **kwargs):
        form = SubprojectForm(request.POST, instance=self.get_object())
        if form.is_valid():
            subproject = form.save()
            if subproject.location_subproject_realized and subproject.location_subproject_realized.cvd:
                subproject.cvd = subproject.location_subproject_realized.cvd
            subproject.save(user=self.request.user)
            return redirect('subprojects:detail', pk=subproject.id)
        self.form_mixin = form
        return super(SubprojectUpdateView, self).get(request, *args, **kwargs)
    

class SubprojectUpdateWithoutLinkHeavyObjectsView(PageMixin, LoginRequiredMixin, InfraPermissionRequiredMixin, generic.UpdateView):
    model = Subproject
    template_name = 'subproject_create.html'
    context_object_name = 'subproject'
    title = _('Update Subproject')
    active_level1 = 'subprojects'
    breadcrumb = [
        {
            'url': reverse_lazy('subprojects:list'),
            'title': _('subprojects')
        },
        {
            'url': '',
            'title': title
        },
    ]
 
    form_class = SubprojectWithoutLinkHeavyObjectsForm # specify the class form to be displayed
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        _object = self.get_object()
        
        if _object.subproject_type_designation == "Infrastructure":
            context['title'] = f"{_('Update the infrastructure')} / {_object.location_subproject_realized.name}" if _object.location_subproject_realized else _('Update the infrastructure')
        elif _object.subproject_type_designation == "Subproject":
            context['title'] = f"{_('Update the subproject')} / {_object.location_subproject_realized.name}" if _object.location_subproject_realized else _('Update the subproject')
        context['breadcrumb'][1]['title'] = context['title']

        if self.form_mixin:
            context['form'] = self.form_mixin
        else:
            context['form'] = SubprojectWithoutLinkHeavyObjectsForm(instance=_object)
        return context
    def post(self, request, *args, **kwargs):
        form = SubprojectWithoutLinkHeavyObjectsForm(request.POST, instance=self.get_object())
        if form.is_valid():
            subproject = form.save()
            if subproject.location_subproject_realized and subproject.location_subproject_realized.cvd:
                subproject.cvd = subproject.location_subproject_realized.cvd
            subproject.save(user=self.request.user)
            return redirect('subprojects:detail', pk=subproject.id)
        self.form_mixin = form
        return super(SubprojectUpdateWithoutLinkHeavyObjectsView, self).get(request, *args, **kwargs)
    
class SubSubprojectCreateView(PageMixin, LoginRequiredMixin, EvaluatorPermissionRequiredMixin, generic.CreateView):
    model = Subproject
    template_name = 'subproject_create.html'
    context_object_name = 'subproject'
    title = _('Create Subproject')
    active_level1 = 'subprojects'
    breadcrumb = [
        {
            'url': reverse_lazy('subprojects:list'),
            'title': _('subprojects')
        },
        {
            'url': '',
            'title': title
        },
    ]
 
    form_class = SubprojectForm # specify the class form to be displayed

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title']= _('Record an infrastructure or a subproject')
        try:
            if self.form_mixin:
                context['form'] = self.form_mixin
            else:
                obj = Subproject.objects.get(id=self.kwargs['subproject_id'])
                list_of_beneficiary_villages = obj.list_of_beneficiary_villages.all()
                if not obj.location_subproject_realized:
                    list_of_beneficiary_villages = []
                    
                obj.id = None
                obj.pk = None
                obj.canton = None
                obj.type_of_subproject = None
                obj.number = None
                obj.estimated_cost = None
                obj.link_to_subproject = Subproject.objects.get(id=self.kwargs['subproject_id'])
                
                context['form'] = SubprojectForm(initial={
                    "list_of_beneficiary_villages": list_of_beneficiary_villages
                }, instance=obj)
        except:
            raise Http404
        
        return context

    def post(self, request, *args, **kwargs):
        form = SubprojectForm(request.POST)
        if form.is_valid():
            subproject = form.save()
            if subproject.location_subproject_realized and subproject.location_subproject_realized.cvd:
                subproject.cvd = subproject.location_subproject_realized.cvd
            subproject.save(user=self.request.user)
            return redirect('subprojects:detail', pk=subproject.link_to_subproject.id)
        self.form_mixin = form
        return super(SubSubprojectCreateView, self).get(request, *args, **kwargs)
    


#============================================Vulnerable Group=========================================================

class VulnerableGroupCreateView(PageMixin, LoginRequiredMixin, generic.CreateView):
    model = VulnerableGroup
    template_name = 'vulnerable_group_create.html'
    context_object_name = 'vulnerable_group'
    title = _('Create Vulnerable Group')
    active_level1 = 'subprojects'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]
 
    form_class = VulnerableGroupForm # specify the class form to be displayed

    def post(self, request, *args, **kwargs):
        form = VulnerableGroupForm(request.POST)
        if form.is_valid():
            vulnerable_group = form.save()
            vulnerable_group.save(user=self.request.user)
            messages.info(request, _("Successfully created"))
            return redirect('subprojects:vulnerable_group_create')
        return super(VulnerableGroupCreateView, self).get(request, *args, **kwargs)


@login_required
def subprojectfile_delete(request, file_id):
    """Function to delete one SubprojectFile"""
    try:
        file = SubprojectFile.objects.get(id=file_id)
        subproject = file.subproject
        if file.principal:
            for image in subproject.get_all_images():
                if image.id != file_id:
                    image.principal = True
                    image.save(user=request.user)
                    break

        file.delete()
        
        messages.info(request, _("Image delete successfully"))
    except Exception as exc:
        raise Http404
    
    return redirect('subprojects:detail', subproject.id)

#============================================Download CSV=========================================================

class DownloadCSVView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    """Class to download subprojects under excel file"""

    template_name = 'components/download_subprojects.html'
    context_object_name = 'Download'
    title = _("Download")
    active_level1 = 'administrative_levels'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def post(self, request, *args, **kwargs):
        file_path = ""
        # try:
        file_path = subprojects_functions.get_subprojects_under_file_excel_or_csv(
            file_type=request.POST.get("file_type"),
            params={"type":request.POST.get("type"), "value_of_type":request.POST.get("value_of_type"),
                    "sector":request.POST.get("sector"), "subproject_type":request.POST.get("subproject_type")}
        )

        # except Exception as exc:
        #     messages.info(request, _("An error has occurred..."))

        if not file_path:
            return redirect('subprojects:list')
        else:
            return download_file.download(
                request, 
                file_path,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    