from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from cosomis.mixins import PageMixin, AJAXRequestMixin
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models import Sum, Max

from subprojects.models import Subproject, Step, Component
from administrativelevels.models import AdministrativeLevel
from administrativelevels.functions import (
    get_administrative_level_ids_descendants, get_children_types_administrativelevels,
    get_administrative_level_ids_ascendants, get_administrative_level_id_ascendant
)
from assignments.models import AssignAdministrativeLevelToFacilitator
from . import forms
from . import functions
from process_manager.models import AdministrativeLevelWave, PeriodWave
from financial.models.allocation import AdministrativeLevelAllocation



class DashboardTemplateView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = 'dashboard_administrativelevels.html'
    active_level1 = 'dashboard_administrativelevels'
    title = _('Administrative levels Dashboard')
    
    def get_context_data(self, **kwargs):
        ctx = super(DashboardTemplateView, self).get_context_data(**kwargs)
        ctx['hide_content_header'] = True
        ctx['form_adl'] = forms.AdministrativeLevelFilterForm()
        return ctx


class DashboardAdministrativeLevelMixin:

    table_class_style = 'table-striped table-secondary table-bordered'
    table_thead_class_style = 'bg-primary'

    def get_context_data(self, **kwargs):
        ctx = super(DashboardAdministrativeLevelMixin, self).get_context_data(**kwargs)
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
                ald_filter_ids.append(int(ald_id))
                
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

        administrative_level = administrative_levels.first()
        
        return {
            'administrative_level_type': administrative_level.type if administrative_level else "",
            'columns_tuples': list(administrative_levels.filter(Q(type=administrative_level.type)if administrative_level else Q()).order_by('name').values_list('id', 'name')),
            'ald_filter_ids': ald_filter_ids,
            'administrative_level_type_choice': administrative_level_type,
        }


class DashboardWaveListView(DashboardAdministrativeLevelMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'tracking.html'
    context_object_name = 'queryset_results'
    table_class_style = 'table-bordered'

    def summary_administrative_level_waves(self, all_administrative_levels_waves, project_id=1):
        datas = {
            _("Wave"): {},
            _("Cantons covered"): {},
            _("Number of villages"): {},
            _("Number of geographic intervention units"): {},
            _("CVD"): {},
            _("Number of subprojects selected"): {},
            _("Number of infrastructures"): {},
        }
        columns_listes = list(all_administrative_levels_waves.order_by('wave__number').values_list('wave__number'))
        waves = []

        for _wave in columns_listes:
            if _wave[0] not in waves:
                waves.append(_wave[0])
        
        administrative_levels_waves_project = all_administrative_levels_waves.filter(project_id=project_id)
        count = 0
        total_cantons = 0
        for wave in waves:
            datas[_("Wave")][count] = wave

            administrative_levels_waves = administrative_levels_waves_project.filter(wave__number=wave)
            
            cantons = []
            for adl_wave in administrative_levels_waves:
                if adl_wave.administrative_level and adl_wave.administrative_level.type == "Canton":
                    cantons.append(adl_wave.administrative_level)

            cantons_ids = []
            villages_ids = []
            nbr_geographical_unit = 0
            nbr_cvd = 0
            for canton in cantons:
                cantons_ids.append(canton.id)
                for village in canton.children:
                    villages_ids.append(village.id)

                units = canton.get_list_geographical_unit()
                nbr_geographical_unit += units.count()

                for u in units:
                    nbr_cvd += u.get_cvds().count()

            _d_cantons = {}
            for c in cantons:
                if c.parent and c.parent.parent and c.parent.parent.parent:
                    if _d_cantons.get(c.parent.parent.parent.name):
                        _d_cantons[c.parent.parent.parent.name].append(c)
                    else:
                        _d_cantons[c.parent.parent.parent.name] = [c]

            cantons_covered_str = ""
            len_d_cantons = len(_d_cantons)
            c = 0
            for region_name, _cantons in _d_cantons.items():
                len_cantons = len(_cantons)
                total_cantons += len_cantons
                cantons_covered_str += f'{_("%(len_cantons)s cantons in the %(region_name)s region") % {"region_name": region_name, "len_cantons": len_cantons}} ({", ".join([c.name for c in _cantons])})'
                c += 1
                if len_d_cantons != c:
                    cantons_covered_str += "\\n"

            datas[_("Cantons covered")][count] = cantons_covered_str

            datas[_("Number of villages")][count] = len(villages_ids)
            datas[_("Number of geographic intervention units")][count] = nbr_geographical_unit
            datas[_("CVD")][count] = nbr_cvd

            subproject_filters = Subproject.objects.filter(
                    Q(location_subproject_realized__id__in=villages_ids) | 
                    Q(canton__id__in=cantons_ids)
                )
            datas[_("Number of subprojects selected")][count] = subproject_filters.filter(
                    subproject_type_designation__in=["Subproject"]
                ).count()
            datas[_("Number of infrastructures")][count] = subproject_filters.filter(
                    subproject_type_designation__in=["Subproject", "Infrastructure"]
                ).count()
            
            count += 1

        # All sum
        datas[_("Wave")][count] = _("Total")
        datas[_("Cantons covered")][count] = total_cantons

        columns_skip = [_("Wave"), _("Cantons covered")]
        for k_data in datas.keys():
            _sum = 0
            if k_data not in columns_skip:
                _sum = functions.sum_dict_value(datas[k_data], count)
            if _sum:
                datas[k_data][count] = _sum
        # End All sum


        return {
            'title': _("Project coverage"),
            'datas': datas,
            'length_loop': range(0, count+1),
            'values': list(datas.values())
        }
    

    def get_context_data(self, **kwargs):
        ctx = super(DashboardWaveListView, self).get_context_data(**kwargs)
        columns_tuples = ctx['queryset_results']['columns_tuples']
        administrative_level_ids_descendants = ctx['queryset_results']['ald_filter_ids'].copy()
        
        for column in columns_tuples:
            _ids_descendants = get_administrative_level_ids_descendants(column[0], None, [])

            administrative_level_ids_descendants += ([column[0]] + _ids_descendants if column[0] != "All" else _ids_descendants)

        all_administrative_levels_waves = AdministrativeLevelWave.objects.filter(
            administrative_level__id__in=administrative_level_ids_descendants
        )

        ctx["summary"] = {}

        ctx["summary"]["summary_administrative_level_waves"] = {}
        for k, v in self.summary_administrative_level_waves(all_administrative_levels_waves).items():
            ctx["summary"]["summary_administrative_level_waves"][k] = v
        
        ctx["queryset_results"]["administrative_level_type"] = None

        return ctx


class DashboardWaveTimesListView(DashboardAdministrativeLevelMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'tracking.html'
    context_object_name = 'queryset_results'
    table_class_style = 'table-bordered'

    def summary_administrative_level_waves_times(self, all_period_wave, project_id=1):
        import locale
        locale.setlocale(locale.LC_TIME, "fr_FR") # french

        datas = {
            (_("Wave"), _("Wave")): {}
        }
        columns_listes = list(all_period_wave.order_by('part').values_list('part', 'wave__number'))
        waves = []
        parts = []
        header1 = [_("Wave")]
        header2 = [_("Wave")]

        for column in columns_listes:
            if column[0] not in parts:
                parts.append(column[0])

            if column[1] not in waves:
                waves.append(column[1])
                
        for part in parts:
            datas[(f'{_("Part")} {part}', _("Start date"))] = {}
            datas[(f'{_("Part")} {part}', _("End date"))] = {}
            header1.append(f'{_("Part")} {part}')
            header1.append(f'{_("Part")} {part}')
            header2.append(_("Start date"))
            header2.append(_("End date"))

        count = 0
        periods_project = PeriodWave.objects.filter(project_id=project_id)
        for wave in waves:
            datas[(_("Wave"), _("Wave"))][count] = f'{_("Wave")} {wave}'
            periods_waves_project = periods_project.filter(wave__number=wave)
            for part in parts:
                try:
                    period = periods_waves_project.get(part=part)
                    datas[(f'{_("Part")} {part}', _("Start date"))][count] = period.begin.strftime("%B %Y").title()
                    
                    datas[(f'{_("Part")} {part}', _("End date"))][count] = period.end.strftime("%B %Y").title()
                except:
                    pass
            count += 1

        return {
            'title': _("Investment cycle deployment time"),
            'datas': datas,
            'length_loop': range(0, count),
            'values': list(datas.values()),
            'headers': {'header1': header1, 'header2': header2} if header1 and header2 else None
        }

    def get_context_data(self, **kwargs):
        ctx = super(DashboardWaveTimesListView, self).get_context_data(**kwargs)
        columns_tuples = ctx['queryset_results']['columns_tuples']
        administrative_level_ids_descendants = ctx['queryset_results']['ald_filter_ids'].copy()
        
        for column in columns_tuples:
            _ids_descendants = get_administrative_level_ids_descendants(column[0], None, [])

            administrative_level_ids_descendants += ([column[0]] + _ids_descendants if column[0] != "All" else _ids_descendants)

        # all_administrative_levels_waves = AdministrativeLevelWave.objects.filter(
        #     administrative_level__id__in=administrative_level_ids_descendants
        # )

        ctx["summary"] = {}

        ctx["summary"]["summary_administrative_level_waves_times"] = {}
        for k, v in self.summary_administrative_level_waves_times(PeriodWave.objects.all()).items():
            ctx["summary"]["summary_administrative_level_waves_times"][k] = v
        
        ctx["queryset_results"]["administrative_level_type"] = None

        return ctx
    



class DashboardSummaryAdministrativeLevelNumberListView(DashboardAdministrativeLevelMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'tracking.html'
    context_object_name = 'queryset_results'
    table_class_style = 'table-bordered'

    def summary_administrative_level_children(self, ald_filter_ids, administrative_level_type, project_id=1):
        datas = {
            _("X"): {},
        }
        
        lines = AdministrativeLevel.objects.filter(
            Q(parent__id__in=ald_filter_ids) if ald_filter_ids else Q(type="Region")
        )
        
        columns = get_children_types_administrativelevels(administrative_level_type)
        for column in columns:
            datas[column] = {}
        

        assigns_activated_a_project = AssignAdministrativeLevelToFacilitator.objects.filter(
                activated=True, project_id=project_id
        )
        
        count = 0
        for line in lines:
            datas[_("X")][count] = line.name
            assigns = assigns_activated_a_project.filter(
                Q(administrative_level__id=line.id, administrative_level__type=line.type) | 
                Q(administrative_level__parent__id=line.id, administrative_level__parent__type=line.type) | 
                Q(administrative_level__parent__parent__id=line.id, administrative_level__parent__parent__type=line.type) | 
                Q(administrative_level__parent__parent__parent__id=line.id, administrative_level__parent__parent__parent__type=line.type) | 
                Q(administrative_level__parent__parent__parent__parent__id=line.id, administrative_level__parent__parent__parent__parent__type=line.type)
            )
            dict_dict = dict()
            for column in columns:
                dict_dict[column] = []

            for assign in assigns:
                for column in columns:
                    if column != "Village":
                        l = get_administrative_level_id_ascendant(assign.administrative_level.id, column)
                        dict_dict[column] += l
                    elif column == "Village" and not dict_dict.get(column):
                        dict_dict[column] = [_id[0] for _id in assigns.values_list('id')]

            for c in dict_dict:
                dict_dict[c] = list(set(dict_dict[c]))

            for column in columns:
                datas[column][count] = len(dict_dict[column])
                    
                
            count += 1

        # All sum
        datas[_("X")][count] = _("Total")
        columns_skip = [_("X")]
        for k_data in datas.keys():
            _sum = 0
            if k_data not in columns_skip:
                _sum = functions.sum_dict_value(datas[k_data], count)
            if _sum:
                datas[k_data][count] = _sum
        # End All sum

        return {
            'title': _("Summary of locations reached"),
            'datas': datas,
            'length_loop': range(0, count+1),
            'values': list(datas.values())
        }

    def get_context_data(self, **kwargs):
        ctx = super(DashboardSummaryAdministrativeLevelNumberListView, self).get_context_data(**kwargs)
        ctx["summary"] = {}

        ctx["summary"]["summary_administrative_level_children"] = {}
        for k, v in self.summary_administrative_level_children(ctx['queryset_results']['ald_filter_ids'].copy(), ctx['queryset_results']['administrative_level_type_choice']).items():
            ctx["summary"]["summary_administrative_level_children"][k] = v

        ctx["queryset_results"]["administrative_level_type"] = None

        return ctx
    



class DashboardSummaryAdministrativeLevelAllocationListView(DashboardAdministrativeLevelMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'tracking.html'
    context_object_name = 'queryset_results'
    table_class_style = 'table-bordered'

    def summary_administrative_level_allocation(self, adl_ids, project_id=1):
        datas = {
            _("Cantons"): {},
            _("Component"): {},
            _("Allocation") + " FCFA": {},
            _("Total estimate for subprojects") + " FCFA": {},
            _("Exact amount spent on subprojects") + " FCFA": {},
            _("Remainder after estimated cost") + " FCFA": {},
            _("Remaining amount") + " FCFA": {},
        }
        components = Component.objects.filter(parent__name="Composante 1")
        subprojects = Subproject.objects.all()
        ids = []
        
        if adl_ids:
            for _id in adl_ids:
                ids += ([_id] + get_administrative_level_ids_descendants(_id, None, []))
            lines = AdministrativeLevelWave.objects.filter(administrative_level__id__in=ids)
        else:
            lines = AdministrativeLevelWave.objects.all()
        
        count = 0
        allocation_project = AdministrativeLevelAllocation.objects.filter(
            project_id=project_id,
            cvd=None
        )
        for line in lines:
            _ids = ([line.administrative_level.id] + get_administrative_level_ids_descendants(line.administrative_level.id, None, []))
            allocation_adl_project = allocation_project.filter(
                administrative_level__id=line.administrative_level.id
            )
            subproject_filter_adl_project = subprojects.filter(
                Q(location_subproject_realized__id__in=_ids) | 
                Q(canton__id__in=_ids)
            )
            for component in components:
                datas[_("Cantons")][count] = line.administrative_level.name
                datas[_("Component")][count] = component.name

                try:
                    amount__sum = allocation_adl_project.filter(
                        component_id=component.id
                    ).aggregate(Sum('amount'))['amount__sum']

                    datas[_("Allocation") + " FCFA"][count] = amount__sum if amount__sum else ""
                except:
                    datas[_("Allocation") + " FCFA"][count] = ""
                
                subproject_filter = subproject_filter_adl_project.filter(
                        component_id=component.id
                    )
                try:
                    estimated_cost__sum = subproject_filter.aggregate(Sum('estimated_cost'))['estimated_cost__sum']

                    datas[_("Total estimate for subprojects") + " FCFA"][count] = estimated_cost__sum if estimated_cost__sum else ""
                except:
                    datas[_("Total estimate for subprojects") + " FCFA"][count] = ""
                
                try:
                    exact_amount_spent__sum = subproject_filter.aggregate(Sum('exact_amount_spent'))['exact_amount_spent__sum']

                    datas[_("Exact amount spent on subprojects") + " FCFA"][count] = exact_amount_spent__sum if exact_amount_spent__sum else ""
                except:
                    datas[_("Exact amount spent on subprojects") + " FCFA"][count] = ""
                
                if datas[_("Allocation") + " FCFA"][count] and datas[_("Total estimate for subprojects") + " FCFA"][count]:
                    datas[_("Remainder after estimated cost") + " FCFA"][count] = datas[_("Allocation") + " FCFA"][count] - datas[_("Total estimate for subprojects") + " FCFA"][count]
                else:
                    datas[_("Remainder after estimated cost") + " FCFA"][count] = datas[_("Allocation") + " FCFA"][count]

                if datas[_("Allocation") + " FCFA"][count] and datas[_("Exact amount spent on subprojects") + " FCFA"][count]:
                    datas[_("Remaining amount") + " FCFA"][count] = datas[_("Allocation") + " FCFA"][count] - datas[_("Exact amount spent on subprojects") + " FCFA"][count]
                else:
                    datas[_("Remaining amount") + " FCFA"][count] = datas[_("Allocation") + " FCFA"][count]
                # except:
                #     pass

                datas[_("Exact amount spent on subprojects") + " FCFA"][count] = 0     
                datas[_("Remaining amount") + " FCFA"][count] = 0        
                
                count += 1

        # All sum
        allocations_cvd = AdministrativeLevelAllocation.objects.filter(
            cvd=None, project_id=project_id
        )
        c = 0
        for component in components:
            datas[_("Cantons")][count+c] = _("Total")
            datas[_("Component")][count+c] = component.name
            amount__sum = allocations_cvd.filter(
                component_id=component.id
            ).aggregate(Sum('amount'))['amount__sum']
            datas[_("Allocation") + " FCFA"][count+c] = amount__sum if amount__sum else ""

            subproject_filter = subprojects.filter(component_id=component.id)

            estimated_cost__sum = subproject_filter.aggregate(Sum('estimated_cost'))['estimated_cost__sum']
            datas[_("Total estimate for subprojects") + " FCFA"][count+c] = estimated_cost__sum if estimated_cost__sum else ""
            
            exact_amount_spent__sum = subproject_filter.aggregate(Sum('exact_amount_spent'))['exact_amount_spent__sum']
            datas[_("Exact amount spent on subprojects") + " FCFA"][count+c] = exact_amount_spent__sum if exact_amount_spent__sum else ""
            
            if datas[_("Allocation") + " FCFA"][count+c] and datas[_("Total estimate for subprojects") + " FCFA"][count+c]:
                datas[_("Remainder after estimated cost") + " FCFA"][count+c] = datas[_("Allocation") + " FCFA"][count+c] - datas[_("Total estimate for subprojects") + " FCFA"][count+c]
            else:
                datas[_("Remainder after estimated cost") + " FCFA"][count+c] = datas[_("Allocation") + " FCFA"][count+c]

            if datas[_("Allocation") + " FCFA"][count+c] and datas[_("Exact amount spent on subprojects") + " FCFA"][count+c]:
                datas[_("Remaining amount") + " FCFA"][count+c] = datas[_("Allocation") + " FCFA"][count+c] - datas[_("Exact amount spent on subprojects") + " FCFA"][count+c]
            else:
                datas[_("Remaining amount") + " FCFA"][count+c] = datas[_("Allocation") + " FCFA"][count+c]
            
            datas[_("Exact amount spent on subprojects") + " FCFA"][count+c] = 0     
            datas[_("Remaining amount") + " FCFA"][count+c] = 0   
        
            
            c += 1
            
        datas[ _("Cantons")][count+c] = _("Total")
        datas[ _("Component")][count+c] = _("All")
        datas[_("Allocation") + " FCFA"][count+c] = AdministrativeLevelAllocation.objects.filter(
                        cvd=None, project_id=project_id
            ).aggregate(Sum('amount'))['amount__sum']
        
        estimated_cost__sum = subprojects.aggregate(Sum('estimated_cost'))['estimated_cost__sum']
        datas[_("Total estimate for subprojects") + " FCFA"][count+c] = estimated_cost__sum if estimated_cost__sum else ""

        exact_amount_spent__sum = subprojects.aggregate(Sum('exact_amount_spent'))['exact_amount_spent__sum']
        datas[_("Exact amount spent on subprojects") + " FCFA"][count+c] = exact_amount_spent__sum if exact_amount_spent__sum else ""
        if datas[_("Allocation") + " FCFA"][count+c] and datas[_("Total estimate for subprojects") + " FCFA"][count+c]:
            datas[_("Remainder after estimated cost") + " FCFA"][count+c] = datas[_("Allocation") + " FCFA"][count+c] - datas[_("Total estimate for subprojects") + " FCFA"][count+c]
        else:
            datas[_("Remainder after estimated cost") + " FCFA"][count+c] = datas[_("Allocation") + " FCFA"][count+c]

        if datas[_("Allocation") + " FCFA"][count+c] and datas[_("Exact amount spent on subprojects") + " FCFA"][count+c]:
            datas[_("Remaining amount") + " FCFA"][count+c] = datas[_("Allocation") + " FCFA"][count+c] - datas[_("Exact amount spent on subprojects") + " FCFA"][count+c]
        else:
            datas[_("Remaining amount") + " FCFA"][count+c] = datas[_("Allocation") + " FCFA"][count+c]

        datas[_("Exact amount spent on subprojects") + " FCFA"][count+c] = 0     
        datas[_("Remaining amount") + " FCFA"][count+c] = 0   

        # columns_skip = [ _("Cantons")]
        # for k_data in datas.keys():
        #     _sum = 0
        #     if k_data not in columns_skip:
        #         _sum = functions.sum_dict_value(datas[k_data], count)
        #     if _sum:
        #         datas[k_data][count+c] = _sum
        # End All sum

        return {
            'title': _("Allocation"),
            'datas': datas,
            'length_loop': range(0, count+c+1),
            'values': list(datas.values())
        }

    def get_context_data(self, **kwargs):
        ctx = super(DashboardSummaryAdministrativeLevelAllocationListView, self).get_context_data(**kwargs)
        # children_ids = [c[0] for c in ctx['queryset_results']['columns_tuples']]


        ctx["summary"] = {}
    
        ctx["summary"]["summary_administrative_level_allocation"] = {}
        for k, v in self.summary_administrative_level_allocation(ctx['queryset_results']['ald_filter_ids'].copy()).items():
            ctx["summary"]["summary_administrative_level_allocation"][k] = v

        ctx["queryset_results"]["administrative_level_type"] = None

        return ctx