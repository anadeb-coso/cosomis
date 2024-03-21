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

        subprojects = Subproject.objects.filter()

        sectors = sorted(list(set(list(subprojects.values_list('subproject_sector')))))
        
        if not ald_filter_ids:
            pass
        else:
            subprojects = subprojects.filter(
                Q(location_subproject_realized__id__in=administrative_levels_ids) | 
                Q(canton__id__in=administrative_levels_ids)
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
        ctx['total_latrine_blocks'] = all_subprojects.filter(has_latrine_blocs=True).count()
        ctx['total_fences'] = all_subprojects.filter(has_fence=True).count()
        ctx['total_infrastrutures'] = ctx['total'] + ctx['total_latrine_blocks'] + ctx['total_fences']
        
        ctx['total_subproject_in_progress'] = all_subprojects.filter(subproject_type_designation="Subproject", current_status_of_the_site="En cours").count()
        ctx['total_subproject_completed'] = all_subprojects.filter(subproject_type_designation="Subproject", current_status_of_the_site__in=["Achevé", "Réception technique", "Réception provisoire", "Réception définitive"]).count()
        ctx['total_subproject_not_started'] = ctx['total_subproject'] - (ctx['total_subproject_in_progress'] + ctx['total_subproject_completed'])
        
        ctx['total_infrastruture_in_progress'] = all_subprojects.filter(current_status_of_the_site="En cours").count()
        ctx['total_infrastruture_completed'] = all_subprojects.filter(current_status_of_the_site__in=["Achevé", "Réception technique", "Réception provisoire", "Réception définitive"]).count()
        ctx['total_infrastruture_not_started'] = ctx['total'] - (ctx['total_infrastruture_in_progress'] + ctx['total_infrastruture_completed'])
        
        ctx['total_latrines_in_progress'] = all_subprojects.filter(current_status_of_the_site="En cours", has_latrine_blocs=True).count()
        ctx['total_latrines_completed'] = all_subprojects.filter(current_status_of_the_site__in=["Achevé", "Réception technique", "Réception provisoire", "Réception définitive"], has_latrine_blocs=True).count()
        ctx['total_latrines_not_started'] = ctx['total_latrine_blocks'] - (ctx['total_latrines_in_progress'] + ctx['total_latrines_completed'])
        
        ctx['total_fences_in_progress'] = all_subprojects.filter(current_status_of_the_site="En cours", has_fence=True).count()
        ctx['total_fences_completed'] = all_subprojects.filter(current_status_of_the_site__in=["Achevé", "Réception technique", "Réception provisoire", "Réception définitive"], has_fence=True).count()
        ctx['total_fences_not_started'] = ctx['total_fences'] - (ctx['total_fences_in_progress'] + ctx['total_fences_completed'])
        
        ctx['total_infrastrutures_in_progress'] = ctx['total_infrastruture_in_progress'] + ctx['total_latrines_in_progress'] + ctx['total_fences_in_progress']
        ctx['total_infrastrutures_completed'] = ctx['total_infrastruture_completed'] + ctx['total_latrines_completed'] + ctx['total_fences_completed']
        ctx['total_infrastrutures_not_started'] = ctx['total_infrastruture_not_started'] + ctx['total_latrines_not_started'] + ctx['total_fences_not_started']
        
        ctx['number_subproject_infrastrutures'] = {
            'sectors': sectors,
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
                            all_subprojects.filter(subproject_sector=sector).count() + \
                                all_subprojects.filter(subproject_sector=sector, has_latrine_blocs=True).count() + \
                                    all_subprojects.filter(subproject_sector=sector, has_fence=True).count()
                        ) for sector in sectors
                    ]
                }
            ]
        }
        
        
        ctx['amount_subproject_infrastrutures'] = {
            'sectors': sectors,
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
        
        
        
        ctx['administrative_level_id'] = self.request.GET.getlist('administrative_level_id[]', [])
        administrative_level_type = self.request.GET.get('administrative_level_type', 'All').title()
        ctx['administrative_level_type'] = "All" if administrative_level_type in ("", "null", "undefined") else administrative_level_type
        return ctx
    


class DashboardFinancingListView(DashboardSubprojectsMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'components/dashboard_summary_financing.html'
    context_object_name = 'queryset_results'
    
    def get_context_data(self, **kwargs):
        ctx = super(DashboardFinancingListView, self).get_context_data(**kwargs)
        all_subprojects = ctx['queryset_results']['subprojects']
        sectors = ctx['queryset_results']['sectors']
        # components = Component.objects.filter(parent__name="Composante 1")
        ids = ctx['queryset_results']['ald_filter_ids'].copy() + ctx['queryset_results']['administrative_levels_ids'].copy()
        if ids:
            print("ici")
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
        # allocations_project = AdministrativeLevelAllocation.objects.filter()
        
        ctx['total_amount_subprojects_estimated_cost'] = all_subprojects.aggregate(Sum('estimated_cost'))['estimated_cost__sum']
        ctx['total_amount_subprojects_estimated_cost'] = ctx['total_amount_subprojects_estimated_cost'] if ctx['total_amount_subprojects_estimated_cost'] else 0
        
        ctx['total_allocations_cantons'] = allocations_project.filter(cvd=None).aggregate(Sum('amount'))['amount__sum']
        ctx['total_allocations_cantons'] = ctx['total_allocations_cantons'] if ctx['total_allocations_cantons'] else 0
        
        ctx['total_amount_remaining_after_allocation'] = ctx['total_allocations_cantons'] - ctx['total_amount_subprojects_estimated_cost']
        
        
        
        ctx['amount_subproject_infrastrutures'] = {
            'sectors': sectors,
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
        
        # if ids:
        #     lines = AdministrativeLevelWave.objects.filter(administrative_level__id__in=ids).order_by("administrative_level__name")
        #     # admls = AdministrativeLevel.objects.filter(type="Canton", id__in=ids).order_by("name")
        # else:
        #     #  admls = AdministrativeLevel.objects.filter(type="Canton").order_by("name")
        #      lines = AdministrativeLevelWave.objects.all().order_by("administrative_level__name")
        # admls = [adl.administrative_level for adl in lines]
        # admls_children = [
        #     (
        #         adl, 
        #         allocations_project.filter(
        #             administrative_level__id=adl.id
        #         ),
        #         ([adl.id] + get_administrative_level_ids_descendants(adl.id, None, []))) for adl in admls
        # ]
        
        # ctx['amount_cantons_component_1_1'] = {
        #     'sectors': [adl.name for adl in admls],
        #     'bars': [
        #         {
        #             'label': _("Allocation"),
        #             'backgroundColor': 'blue',
        #             'data': [(elt if elt else 0) for elt in [
        #                 adml[1].filter(
        #                     component_id=2
        #                 ).aggregate(Sum('amount'))['amount__sum'] for adml in admls_children
        #             ]]
        #         },
        #         {
        #             'label': _("Sub-project estimates"),
        #             'backgroundColor': 'red',
        #             'data': [(elt if elt else 0) for elt in [
        #                 all_subprojects.filter(
        #                     Q(location_subproject_realized__id__in=adml[2]) | 
        #                     Q(canton__id__in=adml[2]), component_id=2
        #                 ).aggregate(Sum('estimated_cost'))['estimated_cost__sum'] for adml in admls_children
        #             ]]
        #         },
        #         {
        #             'label': _("Spent"),
        #             'backgroundColor': 'green',
        #             'data': [(elt if elt else 0) for elt in [
        #                 all_subprojects.filter(
        #                     Q(location_subproject_realized__id__in=adml[2]) | 
        #                     Q(canton__id__in=adml[2]), component_id=2
        #                 ).aggregate(Sum('exact_amount_spent'))['exact_amount_spent__sum'] for adml in admls_children
        #             ]]
        #         }
        #     ]
        # }
        
        
        # ctx['amount_cantons_component_1_2'] = {
        #     'sectors': [adl.name for adl in admls],
        #     'bars': [
        #         {
        #             'label': _("Allocation"),
        #             'backgroundColor': 'blue',
        #             'data': [(elt if elt else 0) for elt in [
        #                 adml[1].filter(
        #                     component_id=3
        #                 ).aggregate(Sum('amount'))['amount__sum'] for adml in admls_children
        #             ]]
        #         },
        #         {
        #             'label': _("Sub-project estimates"),
        #             'backgroundColor': 'red',
        #             'data': [(elt if elt else 0) for elt in [
        #                 all_subprojects.filter(
        #                     Q(location_subproject_realized__id__in=adml[2]) | 
        #                     Q(canton__id__in=adml[2]), component_id=3
        #                 ).aggregate(Sum('estimated_cost'))['estimated_cost__sum'] for adml in admls_children
        #             ]]
        #         },
        #         {
        #             'label': _("Spent"),
        #             'backgroundColor': 'green',
        #             'data': [(elt if elt else 0) for elt in [
        #                 all_subprojects.filter(
        #                     Q(location_subproject_realized__id__in=adml[2]) | 
        #                     Q(canton__id__in=adml[2]), component_id=3
        #                 ).aggregate(Sum('exact_amount_spent'))['exact_amount_spent__sum'] for adml in admls_children
        #             ]]
        #         }
        #     ]
        # }
        
        
        # ctx['amount_cantons_component_1_3'] = {
        #     'sectors': [adl.name for adl in admls],
        #     'bars': [
        #         {
        #             'label': _("Allocation"),
        #             'backgroundColor': 'blue',
        #             'data': [(elt if elt else 0) for elt in [
        #                 adml[1].filter(
        #                     component_id=6
        #                 ).aggregate(Sum('amount'))['amount__sum'] for adml in admls_children
        #             ]]
        #         },
        #         {
        #             'label': _("Sub-project estimates"),
        #             'backgroundColor': 'red',
        #             'data': [(elt if elt else 0) for elt in [
        #                 all_subprojects.filter(
        #                     Q(location_subproject_realized__id__in=adml[2]) | 
        #                     Q(canton__id__in=adml[2]), component_id=6
        #                 ).aggregate(Sum('estimated_cost'))['estimated_cost__sum'] for adml in admls_children
        #             ]]
        #         },
        #         {
        #             'label': _("Spent"),
        #             'backgroundColor': 'green',
        #             'data': [(elt if elt else 0) for elt in [
        #                 all_subprojects.filter(
        #                     Q(location_subproject_realized__id__in=adml[2]) | 
        #                     Q(canton__id__in=adml[2]), component_id=6
        #                 ).aggregate(Sum('exact_amount_spent'))['exact_amount_spent__sum'] for adml in admls_children
        #             ]]
        #         }
        #     ]
        # }
        
        
        
        ctx['administrative_level_id'] = self.request.GET.getlist('administrative_level_id[]', [])
        administrative_level_type = self.request.GET.get('administrative_level_type', 'All').title()
        ctx['administrative_level_type'] = "All" if administrative_level_type in ("", "null", "undefined") else administrative_level_type
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
        
        if list_type_search == 'subprojects-number':
            all_subprojects = all_subprojects.filter(subproject_type_designation="Subproject")
        elif list_type_search == 'subprojects-completed':
            list_name_search = _("Subprojects completed")
            all_subprojects = all_subprojects.filter(subproject_type_designation="Subproject", current_status_of_the_site__in=["Achevé", "Réception technique", "Réception provisoire", "Réception définitive"])
        elif list_type_search == 'subprojects-in-progress':
            list_name_search = _("Subprojects in progress")
            all_subprojects = all_subprojects.filter(subproject_type_designation="Subproject", current_status_of_the_site="En cours")
        elif list_type_search == 'subprojects-not-started':
            list_name_search = _("Subprojects not start")
            all_subprojects = all_subprojects.filter(subproject_type_designation="Subproject").exclude(current_status_of_the_site__in=["En cours", "Achevé", "Réception technique", "Réception provisoire", "Réception définitive"])
            
        elif list_type_search == 'infrastrutures':
            list_name_search = _("Structures/infrastructures without latrines and fences")
        elif list_type_search == 'infrastruture-completed':
            list_name_search = _("Structures/infrastructures completed (excluding latrines and fences)")
            all_subprojects = all_subprojects.filter(current_status_of_the_site__in=["Achevé", "Réception technique", "Réception provisoire", "Réception définitive"])
        elif list_type_search == 'infrastruture-in-progress':
            list_name_search = _("Structures/infrastructures in progress (excluding latrines and fences)")
            all_subprojects = all_subprojects.filter(current_status_of_the_site="En cours")
        elif list_type_search == 'infrastruture-not-started':
            list_name_search = _("Structures/infrastructures not start (excluding latrines and fences)")
            all_subprojects = all_subprojects.exclude(current_status_of_the_site__in=["En cours", "Achevé", "Réception technique", "Réception provisoire", "Réception définitive"])
        
        elif 'infrastrutures-with-latrines-fences' in list_type_search:
            if list_type_search == 'infrastrutures-with-latrines-fences':
                list_name_search = _("Structures/infrastructures with latrines and fences")
            elif list_type_search == 'infrastrutures-with-latrines-fences-completed':
                list_name_search = _("Structures/infrastructures with latrines and fences completed")
                all_subprojects = all_subprojects.filter(current_status_of_the_site__in=["Achevé", "Réception technique", "Réception provisoire", "Réception définitive"])
            elif list_type_search == 'infrastrutures-with-latrines-fences-in-progress':
                list_name_search = _("Structures/infrastructures with latrines and fences in progress")
                all_subprojects = all_subprojects.filter(current_status_of_the_site="En cours")
            elif list_type_search == 'infrastrutures-with-latrines-fences-not-started':
                list_name_search = _("Structures/infrastructures with latrines and fences not start")
                all_subprojects = all_subprojects.exclude(current_status_of_the_site__in=["En cours", "Achevé", "Réception technique", "Réception provisoire", "Réception définitive"])
            
            context['total'] = all_subprojects.count()
            context['total_latrine_blocks'] = all_subprojects.filter(has_latrine_blocs=True).count()
            context['total_fences'] = all_subprojects.filter(has_fence=True).count()
            context['total_infrastrutures'] = context['total'] + context['total_latrine_blocks'] + context['total_fences']
            list_name_search += f"\
                ({context['total_latrine_blocks']}/{context['total_fences']})"
                
                
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