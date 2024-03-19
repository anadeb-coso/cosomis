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



class DashboardTemplateView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = 'dashboard_summary.html'
    active_level1 = 'dashboard_summary'
    title = _('Dashboard')
    
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
        
        ctx['total_infrastruture_in_progress'] = all_subprojects.filter(current_status_of_the_site="En cours").count()
        ctx['total_infrastruture_completed'] = all_subprojects.filter(current_status_of_the_site__in=["Achevé", "Réception technique", "Réception provisoire", "Réception définitive"]).count()
        ctx['total_infrastruture_not_started'] = ctx['total'] - (ctx['total_infrastruture_in_progress'] + ctx['total_infrastruture_completed'])
        
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
                {
                    'label': _("Subproject"),
                    'backgroundColor': 'red',
                    'data': [(elt if elt else 0) for elt in [
                        all_subprojects.filter(subproject_type_designation="Subproject", subproject_sector=sector).aggregate(Sum('estimated_cost'))['estimated_cost__sum'] for sector in sectors
                    ]]
                },
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
        
        
        return ctx
    


