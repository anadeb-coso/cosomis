from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from cosomis.mixins import PageMixin, AJAXRequestMixin
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q, Count, Prefetch
from django.db.models import Sum, Max
from django.http import Http404
from django.utils.formats import number_format
from collections import defaultdict

from subprojects.models import Subproject, Step, Component, Project
from administrativelevels.models import AdministrativeLevel, CVD, GeographicalUnit
from administrativelevels.functions import (
    get_administrative_level_ids_descendants, get_children_types_administrativelevels,
    get_administrative_level_ids_ascendants, get_administrative_level_id_ascendant,
    get_administrative_level_ids_descendants_with_dict, get_administrative_level_children_map
)
from assignments.models import AssignAdministrativeLevelToFacilitator
from . import forms
from subprojects.forms import SubprojectFilterForm, SearchForm
from . import functions
from process_manager.models import AdministrativeLevelWave, PeriodWave
from financial.models.allocation import AdministrativeLevelAllocation
from cosomis.views_manage_url_parse import redirect_user_to_login, redirect_to_an_url



class DashboardTemplateView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = 'dashboard_administrativelevels.html'
    active_level1 = 'dashboard_administrativelevels'
    title = _('Administrative levels Dashboard')
    
    def get_context_data(self, **kwargs):
        ctx = super(DashboardTemplateView, self).get_context_data(**kwargs)
        ctx['hide_content_header'] = True
        ctx['form_adl'] = forms.AdministrativeLevelFilterForm()
        ctx['form_suproject'] = SubprojectFilterForm(False)
        ctx['form_searcht'] = SearchForm()
        return ctx


class DashboardAdministrativeLevelMixin(LoginRequiredMixin):

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
        ctx = super(DashboardAdministrativeLevelMixin, self).get_context_data(**kwargs)
        ctx.setdefault('table_class_style', self.table_class_style)
        ctx.setdefault('table_thead_class_style', self.table_thead_class_style)
        return ctx

    def render_to_response(self, context, **response_kwargs):
        functions.plain_summary_tables(*context.get('summary', {}).values())
        return super().render_to_response(context, **response_kwargs)

    def get_filtered_subprojects(self):
        """The active subprojects of the project (of all the projects when "show
        for all projects" is checked) matching the subproject filters (status,
        dates, component, sector, type of structure, works type)."""
        return functions.filter_dashboard_subprojects(
            Subproject.objects.get_objects_by_general_filtre(self.request, None).get_actifs(), self.request
        )
    
    def get_queryset(self):

        administrative_level_ids_get = self.request.GET.getlist('administrative_level_id[]', None)
        administrative_level_type = self.request.GET.get('administrative_level_type', 'All').title()
        
        administrative_level_type = "All" if administrative_level_type in ("", "null", "undefined") else administrative_level_type
        
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
        #         ald_filter_ids.append(int(ald_id))
                
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

        # --- Normalisation des IDs ---
        ald_filter_ids = [
            int(ald_id) for ald_id in administrative_level_ids_get
            if ald_id not in ("", "null", "undefined", "All")
        ]
        id_with_descendants = dict()
        # id_with_first_descendants = dict()
        administrative_levels_ids = set()
        for ald_id in ald_filter_ids:  # si vide, on met 0
            _ids, _ids_with_desc, _id_with_first_desc = get_administrative_level_ids_descendants_with_dict(
                ald_id, administrative_level_type, [], {}, {}, self.request.session.get('project_id')
            )
            administrative_levels_ids.update(
                _ids
            )
            id_with_descendants.update(**_ids_with_desc)
            # id_with_first_descendants.update(**_id_with_first_desc)
            
        if not ald_filter_ids:
            administrative_levels_ids = set(AdministrativeLevel.objects.filter(administrative_levels_projects__in=[self.request.session.get('project_id')]).values_list('id', flat=True))
        
        # --- Filtrage des AdministrativeLevels ---
        adl_qs = AdministrativeLevel.objects.get_objects_by_general_filtre(self.request, None)

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


        administrative_level = administrative_levels.first()
        
        return {
            'administrative_level_type': administrative_level.type if administrative_level else "",
            'columns_tuples': list(administrative_levels.filter(Q(type=administrative_level.type)if administrative_level else Q()).order_by('name').values_list('id', 'name')),
            'ald_filter_ids': ald_filter_ids,
            'administrative_level_type_choice': administrative_level_type,
            'administrative_levels_ids': administrative_levels_ids,
            'id_with_descendants': id_with_descendants,
            # 'id_with_first_descendants': id_with_first_descendants
        }


class DashboardWaveListView(DashboardAdministrativeLevelMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'tracking.html'
    context_object_name = 'queryset_results'
    table_class_style = 'table-bordered'

    def summary_administrative_level_waves(self, all_administrative_levels_waves, project_id):
        datas = {
            _("Wave"): {},
            _("Cantons covered"): {},
            _("Number of villages"): {},
            _("Number of geographic intervention units"): {},
            _("CVD"): {},
            _("Number of subprojects selected"): {},
            _("Number of infrastructures"): {},
        }

        # Filtrer les vagues du projet
        # project_wave_qs = all_administrative_levels_waves.filter(
        #     project_id=project_id,
        #     administrative_level__administrative_levels_projects__in=[self.request.session.get('project_id')]
        # )

        # Liste des vagues
        # waves = all_administrative_levels_waves.order_by('wave__number').values_list('wave__number', flat=True).distinct()

        total_cantons = 0

        # What the loop reads for each wave, loaded once for all the waves
        # (several queries per canton and per geographical unit before).
        all_cantons_ids = {
            adl.id for adls in all_administrative_levels_waves.values() for adl in adls if adl and adl.type == "Canton"
        }
        children_by_canton = defaultdict(list)  # canton.children
        for parent_id, child_id in AdministrativeLevel.objects.filter(parent_id__in=all_cantons_ids).values_list('parent_id', 'id'):
            children_by_canton[parent_id].append(child_id)
        project_villages_ids = set(
            AdministrativeLevel.objects.get_objects_by_general_filtre(self.request, None)
            .filter(parent_id__in=all_cantons_ids, type="Village")
            .values_list('id', flat=True)
        )
        units_by_canton = dict(
            GeographicalUnit.objects.filter(canton_id__in=all_cantons_ids)
            .values('canton_id').annotate(n=Count('id')).values_list('canton_id', 'n')
        )
        cvds_by_canton = dict(
            CVD.objects.filter(geographical_unit__canton_id__in=all_cantons_ids)
            .values('geographical_unit__canton_id').annotate(n=Count('id')).values_list('geographical_unit__canton_id', 'n')
        )
        region_names = {
            canton.id: canton.parent.parent.parent.name
            for canton in AdministrativeLevel._base_manager.filter(id__in=all_cantons_ids).select_related('parent__parent__parent')
            if canton.parent and canton.parent.parent and canton.parent.parent.parent
        }
        # With the pk: one row per subproject even when the date filters make the
        # queryset distinct.
        subprojects_locations = [
            (location_id, canton_id, designation)
            for pk, location_id, canton_id, designation in self.get_filtered_subprojects().values_list(
                'pk', 'location_subproject_realized_id', 'canton_id', 'subproject_type_designation'
            )
        ]

        # for count, wave in enumerate(waves):
        count = -1
        for wave, adls in all_administrative_levels_waves.items():
            count += 1
            datas[_("Wave")][count] = wave

            adl_waves = adls #all_administrative_levels_waves.filter(wave__number=wave)
            # cantons = [adl_wave.administrative_level for adl_wave in adl_waves
            #         if adl_wave.administrative_level and adl_wave.administrative_level.type == "Canton"]
            cantons = [adl_wave for adl_wave in adl_waves if adl_wave and adl_wave.type == "Canton"]

            cantons_ids = [canton.id for canton in cantons]

            # Nombre d'unités géographiques et CVD
            nbr_geographical_unit = sum(units_by_canton.get(canton.id, 0) for canton in cantons)
            nbr_cvd = sum(cvds_by_canton.get(canton.id, 0) for canton in cantons)

            # Liste des villages existants filtrés par type "Village"
            villages_ids = {
                village_id for canton in cantons for village_id in children_by_canton.get(canton.id, [])
                if village_id in project_villages_ids
            }

            # Organisation des cantons par région
            region_cantons = {}
            for c in cantons:
                if c.id in region_names:
                    region_name = region_names[c.id]
                    region_cantons.setdefault(region_name, []).append(c)

            cantons_covered_str = ""
            for i, (region_name, _cantons) in enumerate(region_cantons.items()):
                len_cantons = len(_cantons)
                total_cantons += len_cantons
                cantons_covered_str += f'{_("%(len_cantons)s cantons in the %(region_name)s region") % {"region_name": region_name, "len_cantons": len_cantons}} ({", ".join(c.name for c in _cantons)})'
                if i < len(region_cantons) - 1:
                    cantons_covered_str += "\\n"

            datas[_("Cantons covered")][count] = cantons_covered_str
            datas[_("Number of villages")][count] = len(villages_ids)
            datas[_("Number of geographic intervention units")][count] = nbr_geographical_unit
            datas[_("CVD")][count] = nbr_cvd

            # Subprojects et infrastructures
            cantons_ids = set(cantons_ids)
            wave_subprojects = [
                designation for location_id, canton_id, designation in subprojects_locations
                if location_id in villages_ids or canton_id in cantons_ids
            ]

            datas[_("Number of subprojects selected")][count] = sum(
                1 for designation in wave_subprojects if designation in ["Subproject"]
            )
            datas[_("Number of infrastructures")][count] = sum(
                1 for designation in wave_subprojects if designation in ["Subproject", "Infrastructure"]
            )

        # Totaux
        datas[_("Wave")][count + 1] = _("Total")
        datas[_("Cantons covered")][count + 1] = total_cantons
        columns_skip = [_("Wave"), _("Cantons covered")]
        for key, value in datas.items():
            if key not in columns_skip:
                datas[key][count + 1] = sum(value.get(i, 0) for i in range(count + 1))

        return {
            'title': _("Project coverage"),
            'datas': datas,
            'length_loop': range(count + 2),
            'values': list(datas.values())
        }

    # def summary_administrative_level_waves(self, all_administrative_levels_waves, project_id=1):
    #     datas = {
    #         _("Wave"): {},
    #         _("Cantons covered"): {},
    #         _("Number of villages"): {},
    #         _("Number of geographic intervention units"): {},
    #         _("CVD"): {},
    #         _("Number of subprojects selected"): {},
    #         _("Number of infrastructures"): {},
    #     }
    #     columns_listes = list(all_administrative_levels_waves.order_by('wave__number').values_list('wave__number'))
    #     waves = []

    #     for _wave in columns_listes:
    #         if _wave[0] not in waves:
    #             waves.append(_wave[0])
        
    #     administrative_levels_waves_project = all_administrative_levels_waves.filter(project_id=project_id, administrative_level__administrative_levels_projects__in=[self.request.session.get('project_id')])
    #     count = 0
    #     total_cantons = 0
        
    #     for wave in waves:
    #         datas[_("Wave")][count] = wave

    #         administrative_levels_waves = administrative_levels_waves_project.filter(wave__number=wave, administrative_level__administrative_levels_projects__in=[self.request.session.get('project_id')])
            
    #         cantons = [adl_wave.administrative_level for adl_wave in administrative_levels_waves if adl_wave.administrative_level and adl_wave.administrative_level.type == "Canton"]
    #         # for adl_wave in administrative_levels_waves:
    #         #     if adl_wave.administrative_level and adl_wave.administrative_level.type == "Canton":
    #         #         cantons.append(adl_wave.administrative_level)

    #         cantons_ids = []
    #         villages_ids = []
    #         nbr_geographical_unit = 0
    #         nbr_cvd = 0
    #         for canton in cantons:
    #             cantons_ids.append(canton.id)
    #             villages_ids += [village.id for village in canton.children]
    #             # for village in canton.children:
    #             #         villages_ids.append(village.id)

    #             units = canton.get_list_geographical_unit()
    #             nbr_geographical_unit += units.count() 

    #             nbr_cvd += sum([u.get_cvds().count() for u in units])
    #             # for u in units:
    #             #     nbr_cvd += u.get_cvds().count()
            
    #         villages_ids = [a.id for a in AdministrativeLevel.objects.get_objects_by_general_filtre(self.request, None).filter(id__in=villages_ids, type="Village")]
            
    #         _d_cantons = {}
    #         for c in cantons:
    #             if c.parent and c.parent.parent and c.parent.parent.parent:
    #                 if _d_cantons.get(c.parent.parent.parent.name):
    #                     _d_cantons[c.parent.parent.parent.name].append(c)
    #                 else:
    #                     _d_cantons[c.parent.parent.parent.name] = [c]

    #         cantons_covered_str = ""
    #         len_d_cantons = len(_d_cantons)
    #         c = 0
    #         for region_name, _cantons in _d_cantons.items():
    #             len_cantons = len(_cantons)
    #             total_cantons += len_cantons
    #             cantons_covered_str += f'{_("%(len_cantons)s cantons in the %(region_name)s region") % {"region_name": region_name, "len_cantons": len_cantons}} ({", ".join([c.name for c in _cantons])})'
    #             c += 1
    #             if len_d_cantons != c:
    #                 cantons_covered_str += "\\n"

    #         datas[_("Cantons covered")][count] = cantons_covered_str

    #         datas[_("Number of villages")][count] = len(villages_ids)
    #         datas[_("Number of geographic intervention units")][count] = nbr_geographical_unit
    #         datas[_("CVD")][count] = nbr_cvd

    #         subproject_filters = Subproject.objects.get_objects_by_general_filtre(self.request, None).filter(
    #                 Q(location_subproject_realized__id__in=villages_ids) | 
    #                 Q(canton__id__in=cantons_ids)
    #             ).get_actifs()
    #         datas[_("Number of subprojects selected")][count] = subproject_filters.filter(
    #                 subproject_type_designation__in=["Subproject"]
    #             ).count()
    #         datas[_("Number of infrastructures")][count] = subproject_filters.filter(
    #                 subproject_type_designation__in=["Subproject", "Infrastructure"]
    #             ).count()
            
    #         count += 1

    #     # All sum
    #     datas[_("Wave")][count] = _("Total")
    #     datas[_("Cantons covered")][count] = total_cantons

    #     columns_skip = [_("Wave"), _("Cantons covered")]
    #     for k_data in datas.keys():
    #         _sum = 0
    #         if k_data not in columns_skip:
    #             _sum = functions.sum_dict_value(datas[k_data], count)
    #         if _sum:
    #             datas[k_data][count] = _sum
    #     # End All sum


    #     return {
    #         'title': _("Project coverage"),
    #         'datas': datas,
    #         'length_loop': range(0, count+1),
    #         'values': list(datas.values())
    #     }
    
    def get_context_data(self, **kwargs):
        ctx = super(DashboardWaveListView, self).get_context_data(**kwargs)
        administrative_level_ids_descendants = set(ctx['queryset_results']['ald_filter_ids'] + list(ctx['queryset_results']['administrative_levels_ids'])).copy()
        project_id = self.request.session.get('project_id')
        all_administrative_levels_waves = AdministrativeLevelWave.objects.filter(
            project_id=project_id,
            administrative_level__id__in=list(administrative_level_ids_descendants),
            administrative_level__administrative_levels_projects__in=[project_id]
        ).distinct()
        grouped = defaultdict(list)

        for alw in all_administrative_levels_waves.select_related("wave", "administrative_level").order_by('wave__number'):
            grouped[alw.wave.number].append(alw.administrative_level)

        ctx["summary"] = {
            "summary_administrative_level_waves": self.summary_administrative_level_waves(
                grouped,
                project_id
            )
        }

        ctx["queryset_results"]["administrative_level_type"] = None
        return ctx

    # def get_context_data(self, **kwargs):
    #     ctx = super(DashboardWaveListView, self).get_context_data(**kwargs)
    #     columns_tuples = ctx['queryset_results']['columns_tuples']
    #     administrative_level_ids_descendants = ctx['queryset_results']['ald_filter_ids'].copy()
        
    #     for column in columns_tuples:
    #         _ids_descendants = get_administrative_level_ids_descendants(column[0], None, [], self.request.session.get('project_id'))

    #         administrative_level_ids_descendants += ([column[0]] + _ids_descendants if column[0] != "All" else _ids_descendants)

    #     all_administrative_levels_waves = AdministrativeLevelWave.objects.filter(
    #         administrative_level__id__in=administrative_level_ids_descendants, 
    #         administrative_level__administrative_levels_projects__in=[self.request.session.get('project_id')]
    #     )

    #     ctx["summary"] = {}

    #     ctx["summary"]["summary_administrative_level_waves"] = {}
    #     for k, v in self.summary_administrative_level_waves(all_administrative_levels_waves, self.request.session.get('project_id')).items():
    #         ctx["summary"]["summary_administrative_level_waves"][k] = v
        
    #     ctx["queryset_results"]["administrative_level_type"] = None

    #     return ctx


class DashboardWaveTimesListView(DashboardAdministrativeLevelMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'tracking.html'
    context_object_name = 'queryset_results'
    table_class_style = 'table-bordered'

    def summary_administrative_level_waves_times(self, all_period_wave, project_id=1):
        import locale
        locale.setlocale(locale.LC_TIME, "fr_FR")  # French locale

        datas = {(_("Wave"), _("Wave")): {}}
        header1 = [_("Wave")]
        header2 = [_("Wave")]

        # Extraire les parts et waves distincts
        columns_list = list(all_period_wave.order_by('part').values_list('part', 'wave__number'))
        parts = sorted({col[0] for col in columns_list})
        waves = sorted({col[1] for col in columns_list})

        # Préparer les colonnes pour chaque part
        for part in parts:
            for label in [_("Start date"), _("End date")]:
                datas[(f'{_("Part")} {part}', label)] = {}
                header1.append(f'{_("Part")} {part}')
                header2.append(label)

        periods_project = PeriodWave.objects.filter(project_id=project_id).prefetch_related('wave')
        periods_map = {(p.wave.number, p.part): p for p in periods_project}

        for idx, wave in enumerate(waves):
            datas[(_("Wave"), _("Wave"))][idx] = f'{_("Wave")} {wave}'
            for part in parts:
                period = periods_map.get((wave, part))
                if period:
                    datas[(f'{_("Part")} {part}', _("Start date"))][idx] = period.begin.strftime("%B %Y").title()
                    datas[(f'{_("Part")} {part}', _("End date"))][idx] = period.end.strftime("%B %Y").title()

        return {
            'title': _("Investment cycle deployment time"),
            'datas': datas,
            'length_loop': range(len(waves)),
            'values': list(datas.values()),
            'headers': {'header1': header1, 'header2': header2}
        }

    # def summary_administrative_level_waves_times(self, all_period_wave, project_id=1):
    #     import locale
    #     locale.setlocale(locale.LC_TIME, "fr_FR") # french

    #     datas = {
    #         (_("Wave"), _("Wave")): {}
    #     }
    #     columns_listes = list(all_period_wave.order_by('part').values_list('part', 'wave__number'))
    #     waves = []
    #     parts = []
    #     header1 = [_("Wave")]
    #     header2 = [_("Wave")]

    #     for column in columns_listes:
    #         if column[0] not in parts:
    #             parts.append(column[0])

    #         if column[1] not in waves:
    #             waves.append(column[1])
                
    #     for part in parts:
    #         datas[(f'{_("Part")} {part}', _("Start date"))] = {}
    #         datas[(f'{_("Part")} {part}', _("End date"))] = {}
    #         header1.append(f'{_("Part")} {part}')
    #         header1.append(f'{_("Part")} {part}')
    #         header2.append(_("Start date"))
    #         header2.append(_("End date"))

    #     count = 0
    #     periods_project = PeriodWave.objects.filter(project_id=project_id)
    #     for wave in waves:
    #         datas[(_("Wave"), _("Wave"))][count] = f'{_("Wave")} {wave}'
    #         periods_waves_project = periods_project.filter(wave__number=wave)
    #         for part in parts:
    #             try:
    #                 period = periods_waves_project.get(part=part)
    #                 datas[(f'{_("Part")} {part}', _("Start date"))][count] = period.begin.strftime("%B %Y").title()
                    
    #                 datas[(f'{_("Part")} {part}', _("End date"))][count] = period.end.strftime("%B %Y").title()
    #             except:
    #                 pass
    #         count += 1

    #     return {
    #         'title': _("Investment cycle deployment time"),
    #         'datas': datas,
    #         'length_loop': range(0, count),
    #         'values': list(datas.values()),
    #         'headers': {'header1': header1, 'header2': header2} if header1 and header2 else None
    #     }

    def get_context_data(self, **kwargs):
        ctx = super(DashboardWaveTimesListView, self).get_context_data(**kwargs)
        administrative_level_ids_descendants = set(ctx['queryset_results']['ald_filter_ids'] + list(ctx['queryset_results']['administrative_levels_ids'])).copy()

        ctx["summary"] = {
            "summary_administrative_level_waves_times": self.summary_administrative_level_waves_times(
                PeriodWave.objects.filter(project_id=self.request.session.get('project_id')),
                project_id=self.request.session.get('project_id')
            )
        }

        ctx["queryset_results"]["administrative_level_type"] = None
        return ctx

    # def get_context_data(self, **kwargs):
    #     ctx = super(DashboardWaveTimesListView, self).get_context_data(**kwargs)
    #     columns_tuples = ctx['queryset_results']['columns_tuples']
    #     administrative_level_ids_descendants = ctx['queryset_results']['ald_filter_ids'].copy()
        
    #     for column in columns_tuples:
    #         _ids_descendants = get_administrative_level_ids_descendants(column[0], None, [], self.request.session.get('project_id'))

    #         administrative_level_ids_descendants += ([column[0]] + _ids_descendants if column[0] != "All" else _ids_descendants)

    #     # all_administrative_levels_waves = AdministrativeLevelWave.objects.filter(
    #     #     administrative_level__id__in=administrative_level_ids_descendants
    #     # )

    #     ctx["summary"] = {}

    #     ctx["summary"]["summary_administrative_level_waves_times"] = {}
    #     for k, v in self.summary_administrative_level_waves_times(PeriodWave.objects.all(), self.request.session.get('project_id')).items():
    #         ctx["summary"]["summary_administrative_level_waves_times"][k] = v
        
    #     ctx["queryset_results"]["administrative_level_type"] = None

    #     return ctx
    


class DashboardSummaryAdministrativeLevelNumberListView(
    DashboardAdministrativeLevelMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView
): 
    template_name = 'tracking.html'
    context_object_name = 'queryset_results'
    table_class_style = 'table-bordered'

    def summary_administrative_level_children(self, ald_filter_ids, administrative_level_type, id_with_descendants, project_id=1):
        # Initialisation des données
        datas = {_("X"): {}}

        # Récupérer tous les niveaux administratifs pertinents
        lines = (
            AdministrativeLevel.objects
            .get_objects_by_general_filtre(self.request, None)
            .filter(Q(parent__id__in=ald_filter_ids) if ald_filter_ids else Q(type="Region"))
            .select_related("parent")   # optimisation
        )

        # Colonnes (types d’unités enfant)
        columns = get_children_types_administrativelevels(administrative_level_type)
        for column in columns:
            datas[column] = {}

        # Précharger toutes les assignations du projet
        assigns_qs = (
            AssignAdministrativeLevelToFacilitator.objects
            .filter(project_id=project_id, activated=True)
        )

        # Parent and type of every administrative level, to find in memory the
        # levels above an assignment (several queries per assignment and per
        # column before, through get_administrative_level_id_ascendant).
        parents_and_types = {
            adl_id: (parent_id, adl_type)
            for adl_id, parent_id, adl_type in AdministrativeLevel._base_manager.values_list('id', 'parent_id', 'type')
        }

        def get_ascendants(adl_id):
            """adl_id and its 4 levels above, as matched by the filter
            administrative_level(__parent)*=line."""
            ascendants = [adl_id]
            for i in range(4):
                parent_id = parents_and_types.get(ascendants[-1], (None, None))[0]
                if parent_id is None:
                    break
                ascendants.append(parent_id)
            return ascendants

        def get_ascendant_of_type(adl_id, parent_type):
            """Same result as get_administrative_level_id_ascendant()."""
            for ascendant_id in get_ascendants(adl_id)[1:]:
                if parents_and_types.get(ascendant_id, (None, None))[1] == parent_type:
                    return [ascendant_id]
            return []

        all_assigns = [
            (assign_id, adl_id, get_ascendants(adl_id))
            for assign_id, adl_id in assigns_qs.values_list("id", "administrative_level_id")
            if adl_id is not None
        ]

        count = 0
        for line in lines:
            datas[_("X")][count] = line.name

            # Filtrer les assignations liées à la ligne courante
            assigns = [(assign_id, adl_id) for assign_id, adl_id, ascendants in all_assigns if line.id in ascendants]

            dict_dict = defaultdict(list)

            for assign_id, adl_id in assigns:
                for column in columns:
                    if column != "Village":
                        dict_dict[column].extend(get_ascendant_of_type(adl_id, column))
                    elif column == "Village" and not dict_dict[column]:
                        dict_dict[column] = [_assign_id for _assign_id, _adl_id in assigns]

            # Supprimer doublons
            for c in dict_dict:
                dict_dict[c] = list(set(dict_dict[c]))

            # Enregistrer les longueurs dans datas
            for column in columns:
                datas[column][count] = len(dict_dict[column])

            count += 1

        # Ligne "Total"
        datas[_("X")][count] = _("Total")
        for column, values in datas.items():
            if column != _("X"):
                total = sum(v for k, v in values.items() if k != count)
                if total:
                    datas[column][count] = total

        return {
            "title": _("Summary of locations reached"),
            "datas": datas,
            "length_loop": range(count + 1),
            "values": list(datas.values())
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["summary"] = {"summary_administrative_level_children": {}}

        queryset_results = ctx["queryset_results"]
        summary = self.summary_administrative_level_children(
            queryset_results["ald_filter_ids"].copy(),
            str(queryset_results["administrative_level_type_choice"]),
            queryset_results["id_with_descendants"].copy(),
            self.request.session.get("project_id"),
        )

        ctx["summary"]["summary_administrative_level_children"].update(summary)
        ctx["queryset_results"]["administrative_level_type"] = None
        return ctx
# class DashboardSummaryAdministrativeLevelNumberListView(DashboardAdministrativeLevelMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
#     template_name = 'tracking.html'
#     context_object_name = 'queryset_results'
#     table_class_style = 'table-bordered'

#     def summary_administrative_level_children(self, ald_filter_ids, administrative_level_type, project_id=1):
#         datas = {
#             _("X"): {},
#         }
        
#         lines = AdministrativeLevel.objects.get_objects_by_general_filtre(self.request, None).filter(
#             Q(parent__id__in=ald_filter_ids) if ald_filter_ids else Q(type="Region")
#         )
        
#         columns = get_children_types_administrativelevels(administrative_level_type)
#         for column in columns:
#             datas[column] = {}
        

#         assigns_activated_a_project = AssignAdministrativeLevelToFacilitator.objects.filter(
#                 project_id=project_id
#         ).prefetch_related()
        
#         count = 0
#         for line in lines:
#             datas[_("X")][count] = line.name
#             assigns = assigns_activated_a_project.filter(
#                 Q(administrative_level__id=line.id) | 
#                 Q(administrative_level__parent__id=line.id) | 
#                 Q(administrative_level__parent__parent__id=line.id) | 
#                 Q(administrative_level__parent__parent__parent__id=line.id) | 
#                 Q(administrative_level__parent__parent__parent__parent__id=line.id)
#             )
#             dict_dict = dict()
#             for column in columns:
#                 dict_dict[column] = []

#             for assign in assigns:
#                 for column in columns:
#                     if column != "Village":
#                         l = get_administrative_level_id_ascendant(assign.administrative_level.id, column)
#                         dict_dict[column] += l
#                     elif column == "Village" and not dict_dict.get(column):
#                         dict_dict[column] = [_id[0] for _id in assigns.values_list('id')]

#             for c in dict_dict:
#                 dict_dict[c] = list(set(dict_dict[c]))

#             for column in columns:
#                 datas[column][count] = len(dict_dict[column])
                    
                
#             count += 1

#         # All sum
#         datas[_("X")][count] = _("Total")
#         columns_skip = [_("X")]
#         for k_data in datas.keys():
#             _sum = 0
#             if k_data not in columns_skip:
#                 _sum = functions.sum_dict_value(datas[k_data], count)
#             if _sum:
#                 datas[k_data][count] = _sum
#         # End All sum

#         return {
#             'title': _("Summary of locations reached"),
#             'datas': datas,
#             'length_loop': range(0, count+1),
#             'values': list(datas.values())
#         }

#     def get_context_data(self, **kwargs):
#         ctx = super(DashboardSummaryAdministrativeLevelNumberListView, self).get_context_data(**kwargs)
#         ctx["summary"] = {}

#         ctx["summary"]["summary_administrative_level_children"] = {}
#         for k, v in self.summary_administrative_level_children(ctx['queryset_results']['ald_filter_ids'].copy(), ctx['queryset_results']['administrative_level_type_choice'], self.request.session.get('project_id')).items():
#             ctx["summary"]["summary_administrative_level_children"][k] = v

#         ctx["queryset_results"]["administrative_level_type"] = None

#         return ctx
    



class DashboardSummaryAdministrativeLevelAllocationListView(DashboardAdministrativeLevelMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'tracking.html'
    context_object_name = 'queryset_results'
    table_class_style = 'table-bordered'

    def summary_administrative_level_allocation(self, adl_ids, id_with_descendants, project_id=1):
        datas = {
            _("Cantons"): {},
            _("Component"): {},
            _("Allocation") + " FCFA": {},
            _("Total estimate for subprojects") + " FCFA": {},
            _("Exact amount spent on subprojects") + " FCFA": {},
            _("Remainder after estimated cost") + " FCFA": {},
            _("Remaining amount") + " FCFA": {},
        }
        # __iexact : PostgreSQL est sensible à la casse (données = "COMPOSANTE 1"),
        # MySQL (utf8mb4_general_ci) ne l'était pas.
        components = Component.objects.filter(parent__name__iexact="Composante 1")
        ids = []
        
        if adl_ids:
            for _id in adl_ids:
                # ids += ([_id] + get_administrative_level_ids_descendants(_id, None, [], self.request.session.get('project_id')))
                ids += ([_id] + (id_with_descendants.get(str(_id)) or []))
            lines = AdministrativeLevelWave.objects.filter(administrative_level__id__in=ids, project_id=self.request.session.get('project_id')).distinct()
        else:
            lines = AdministrativeLevelWave.objects.filter(project_id=self.request.session.get('project_id')).distinct()
        
        count = 0
        if ids:
            allocations_project = AdministrativeLevelAllocation.objects.filter(
                project_id=project_id,
                cvd=None,
                administrative_level__id__in=ids
            )
            subprojects = self.get_filtered_subprojects().filter(
                Q(location_subproject_realized__id__in=ids) | 
                Q(canton__id__in=ids)
            )
        else:
            allocations_project = AdministrativeLevelAllocation.objects.filter(
                project_id=project_id,
                cvd=None
            )
            subprojects = self.get_filtered_subprojects()
            
        # Loaded once for every line (several queries per line and component before)
        components = list(components)
        components_ids = {component.id: set(component.self_and_descendant_ids) for component in components}
        lines = list(lines)
        levels = AdministrativeLevel._base_manager.in_bulk({line.administrative_level_id for line in lines})
        lines_levels = [levels.get(line.administrative_level_id) for line in lines]
        if not adl_ids:
            children_map = get_administrative_level_children_map({adl.id for adl in lines_levels}, self.request.session.get('project_id'))
        allocations_by_level_component = {
            (adl_id, component.id): amount
            for component in components
            for adl_id, amount in allocations_project.filter(component_id__in=components_ids[component.id])
            .values('administrative_level_id').annotate(total=Sum('amount')).values_list('administrative_level_id', 'total')
        }
        subprojects_amounts = [  # with the pk: one row per subproject even on a distinct queryset
            row[1:] for row in subprojects.values_list(
                'pk', 'location_subproject_realized_id', 'canton_id', 'component_id', 'estimated_cost', 'contract_amount_work_companies'
            )
        ]

        for line, line_level in zip(lines, lines_levels):
            if not adl_ids:
                _ids = ([line_level.id] + get_administrative_level_ids_descendants(line_level.id, None, [], self.request.session.get('project_id'), children_map=children_map))
            else:
                _ids = ([line_level.id] + (id_with_descendants.get(str(line_level.id)) or []))
            _ids = set(_ids)

            line_subprojects = [
                (component_id, estimated_cost, contract_amount)
                for location_id, canton_id, component_id, estimated_cost, contract_amount in subprojects_amounts
                if location_id in _ids or canton_id in _ids
            ]
            for component in components:
                datas[_("Cantons")][count] = line_level.name
                datas[_("Component")][count] = component.name

                amount__sum = allocations_by_level_component.get((line_level.id, component.id)) or 0
                estimated_cost__sum = None
                contract_amount_work_companies__sum = None
                for component_id, estimated_cost, contract_amount in line_subprojects:
                    if component_id in components_ids[component.id]:
                        if estimated_cost is not None:
                            estimated_cost__sum = estimated_cost if estimated_cost__sum is None else estimated_cost__sum + estimated_cost
                        if contract_amount is not None:
                            contract_amount_work_companies__sum = contract_amount if contract_amount_work_companies__sum is None else contract_amount_work_companies__sum + contract_amount
                estimated_cost__sum = estimated_cost__sum or 0
                contract_amount_work_companies__sum = contract_amount_work_companies__sum or 0

                datas[_("Allocation") + " FCFA"][count] = amount__sum
                datas[_("Total estimate for subprojects") + " FCFA"][count] = estimated_cost__sum
                datas[_("Exact amount spent on subprojects") + " FCFA"][count] = contract_amount_work_companies__sum
                
                datas[_("Remainder after estimated cost") + " FCFA"][count] = amount__sum - estimated_cost__sum
                datas[_("Remaining amount") + " FCFA"][count] = amount__sum - contract_amount_work_companies__sum
                
                count += 1

        # All sum
        
        c = 0
        for component in components:
            datas[_("Cantons")][count+c] = _("Total")
            datas[_("Component")][count+c] = component.name

            amount__sum = allocations_project.filter(component_id__in=components_ids[component.id]).aggregate(Sum('amount'))['amount__sum'] or 0
            subproject_filter = subprojects.filter(component_id__in=components_ids[component.id])
            subproject_agg = subproject_filter.aggregate(
                estimated_cost_sum=Sum('estimated_cost'),
                spent_sum=Sum('contract_amount_work_companies')
            )
            estimated_cost__sum = subproject_agg['estimated_cost_sum'] or 0
            contract_amount_work_companies__sum = subproject_agg['spent_sum'] or 0

            datas[_("Allocation") + " FCFA"][count+c] = amount__sum
            datas[_("Total estimate for subprojects") + " FCFA"][count+c] = estimated_cost__sum
            datas[_("Exact amount spent on subprojects") + " FCFA"][count+c] = contract_amount_work_companies__sum
            
            datas[_("Remainder after estimated cost") + " FCFA"][count+c] = amount__sum - estimated_cost__sum
            datas[_("Remaining amount") + " FCFA"][count+c] = amount__sum - contract_amount_work_companies__sum
            
            
            c += 1
            
        datas[ _("Cantons")][count+c] = _("Total")
        datas[ _("Component")][count+c] = _("All")
        

        amount__sum = allocations_project.aggregate(Sum('amount'))['amount__sum'] or 0
        subproject_agg = subprojects.aggregate(
            estimated_cost_sum=Sum('estimated_cost'),
            spent_sum=Sum('contract_amount_work_companies')
        )
        estimated_cost__sum = subproject_agg['estimated_cost_sum'] or 0
        contract_amount_work_companies__sum = subproject_agg['spent_sum'] or 0

        datas[_("Allocation") + " FCFA"][count+c] = amount__sum
        datas[_("Total estimate for subprojects") + " FCFA"][count+c] = estimated_cost__sum
        datas[_("Exact amount spent on subprojects") + " FCFA"][count+c] = contract_amount_work_companies__sum
        
        datas[_("Remainder after estimated cost") + " FCFA"][count+c] = amount__sum - estimated_cost__sum
        datas[_("Remaining amount") + " FCFA"][count+c] = amount__sum - contract_amount_work_companies__sum

        # End All sum

        table_title = self.request.GET.get('table_title')
        return {
            'title': table_title if table_title else _("Allocation"),
            'datas': datas,
            'length_loop': range(0, count+c+1),
            'values': list(datas.values())
        }

    def get_context_data(self, **kwargs):
        ctx = super(DashboardSummaryAdministrativeLevelAllocationListView, self).get_context_data(**kwargs)
        # children_ids = [c[0] for c in ctx['queryset_results']['columns_tuples']]


        ctx["summary"] = {}
    
        ctx["summary"]["summary_administrative_level_allocation"] = {}
        for k, v in self.summary_administrative_level_allocation(ctx['queryset_results']['ald_filter_ids'].copy(), ctx['queryset_results']['id_with_descendants'].copy(), self.request.session.get('project_id')).items():
            ctx["summary"]["summary_administrative_level_allocation"][k] = v

        ctx["queryset_results"]["administrative_level_type"] = None

        return ctx
    


class DashboardSummaryCVDAllocationListView(DashboardAdministrativeLevelMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'tracking.html'
    context_object_name = 'queryset_results'
    table_class_style = 'table-bordered'

    def summary_cvd_allocation(self, adl_ids, id_with_descendants, project_id=1):

        datas = {
            _("CVD"): {},
            _("Component"): {},
            _("Allocation") + " FCFA": {},
            _("Total estimate for subprojects") + " FCFA": {},
            _("Exact amount spent on subprojects") + " FCFA": {},
            _("Remainder after estimated cost") + " FCFA": {},
            _("Remaining amount") + " FCFA": {},
        }
        # __iexact : PostgreSQL est sensible à la casse (données = "COMPOSANTE 1"),
        # MySQL (utf8mb4_general_ci) ne l'était pas.
        components = Component.objects.filter(parent__name__iexact="Composante 1")
        ids = []
        
        if adl_ids:
            for _id in adl_ids:
                # ids += ([_id] + get_administrative_level_ids_descendants(_id, None, [], self.request.session.get('project_id')))
                ids += ([_id] + (id_with_descendants.get(str(_id)) or []))
            lines = CVD.objects.filter(id__in=[
                cvd_id for cvd_id in AdministrativeLevel.objects.get_objects_by_general_filtre(self.request, None).filter(id__in=ids).values_list('cvd_id', flat=True) if cvd_id
            ])
        else:
            lines = CVD.objects.all()
        
        count = 0
        if ids:
            allocations_project = AdministrativeLevelAllocation.objects.filter(
                project_id=project_id,
                cvd__id__in=[obj.id for obj in lines],
                administrative_level=None
            )
            subprojects = self.get_filtered_subprojects().filter(
                Q(location_subproject_realized__id__in=ids) | 
                Q(canton__id__in=ids)
            )
        else:
            allocations_project = AdministrativeLevelAllocation.objects.filter(
                project_id=project_id,
                administrative_level=None
            )
            subprojects = self.get_filtered_subprojects()

        # Loaded once for every CVD (several queries per CVD and component before)
        components = list(components)
        components_ids = {component.id: set(component.self_and_descendant_ids) for component in components}
        lines = list(lines)
        villages_by_cvd = defaultdict(set)  # line.get_villages()
        for cvd_id, village_id in AdministrativeLevel.objects.filter(cvd_id__in=[line.id for line in lines]).values_list('cvd_id', 'id'):
            villages_by_cvd[cvd_id].add(village_id)
        allocations_by_cvd_component = {
            (cvd_id, component.id): amount
            for component in components
            for cvd_id, amount in allocations_project.filter(component_id__in=components_ids[component.id])
            .values('cvd_id').annotate(total=Sum('amount')).values_list('cvd_id', 'total')
        }
        subprojects_amounts = [  # with the pk: one row per subproject even on a distinct queryset
            row[1:] for row in subprojects.values_list(
                'pk', 'location_subproject_realized_id', 'canton_id', 'component_id', 'estimated_cost', 'contract_amount_work_companies'
            )
        ]

        for line in lines:
            _ids = villages_by_cvd.get(line.id, set())
            line_subprojects = [
                (component_id, estimated_cost, contract_amount)
                for location_id, canton_id, component_id, estimated_cost, contract_amount in subprojects_amounts
                if location_id in _ids or canton_id in _ids
            ]
            for component in components:
                datas[_("CVD")][count] = line.name
                datas[_("Component")][count] = component.name

                amount__sum = allocations_by_cvd_component.get((line.id, component.id))
                datas[_("Allocation") + " FCFA"][count] = amount__sum if amount__sum else ""

                estimated_cost__sum = None
                contract_amount_work_companies__sum = None
                for component_id, estimated_cost, contract_amount in line_subprojects:
                    if component_id in components_ids[component.id]:
                        if estimated_cost is not None:
                            estimated_cost__sum = estimated_cost if estimated_cost__sum is None else estimated_cost__sum + estimated_cost
                        if contract_amount is not None:
                            contract_amount_work_companies__sum = contract_amount if contract_amount_work_companies__sum is None else contract_amount_work_companies__sum + contract_amount

                datas[_("Total estimate for subprojects") + " FCFA"][count] = estimated_cost__sum if estimated_cost__sum else ""
                datas[_("Exact amount spent on subprojects") + " FCFA"][count] = contract_amount_work_companies__sum if contract_amount_work_companies__sum else ""
                
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

                # datas[_("Exact amount spent on subprojects") + " FCFA"][count] = 0     
                # datas[_("Remaining amount") + " FCFA"][count] = 0        
                
                count += 1

        # All sum
        
        c = 0
        for component in components:
            datas[_("CVD")][count+c] = _("Total")
            datas[_("Component")][count+c] = component.name
            amount__sum = allocations_project.filter(
                component_id__in=components_ids[component.id]
            ).aggregate(Sum('amount'))['amount__sum']
            datas[_("Allocation") + " FCFA"][count+c] = amount__sum if amount__sum else ""

            subproject_filter = subprojects.filter(component_id__in=components_ids[component.id])

            estimated_cost__sum = subproject_filter.aggregate(Sum('estimated_cost'))['estimated_cost__sum']
            datas[_("Total estimate for subprojects") + " FCFA"][count+c] = estimated_cost__sum if estimated_cost__sum else ""
            
            contract_amount_work_companies__sum = subproject_filter.aggregate(Sum('contract_amount_work_companies'))['contract_amount_work_companies__sum']
            datas[_("Exact amount spent on subprojects") + " FCFA"][count+c] = contract_amount_work_companies__sum if contract_amount_work_companies__sum else ""
            
            if datas[_("Allocation") + " FCFA"][count+c] and datas[_("Total estimate for subprojects") + " FCFA"][count+c]:
                datas[_("Remainder after estimated cost") + " FCFA"][count+c] = datas[_("Allocation") + " FCFA"][count+c] - datas[_("Total estimate for subprojects") + " FCFA"][count+c]
            else:
                datas[_("Remainder after estimated cost") + " FCFA"][count+c] = datas[_("Allocation") + " FCFA"][count+c]

            if datas[_("Allocation") + " FCFA"][count+c] and datas[_("Exact amount spent on subprojects") + " FCFA"][count+c]:
                datas[_("Remaining amount") + " FCFA"][count+c] = datas[_("Allocation") + " FCFA"][count+c] - datas[_("Exact amount spent on subprojects") + " FCFA"][count+c]
            else:
                datas[_("Remaining amount") + " FCFA"][count+c] = datas[_("Allocation") + " FCFA"][count+c]
            
            # datas[_("Exact amount spent on subprojects") + " FCFA"][count+c] = 0     
            # datas[_("Remaining amount") + " FCFA"][count+c] = 0   
        
            
            c += 1
            
        datas[ _("CVD")][count+c] = _("Total")
        datas[ _("Component")][count+c] = _("All")
        datas[_("Allocation") + " FCFA"][count+c] = allocations_project.aggregate(Sum('amount'))['amount__sum']
        
        estimated_cost__sum = subprojects.aggregate(Sum('estimated_cost'))['estimated_cost__sum']
        datas[_("Total estimate for subprojects") + " FCFA"][count+c] = estimated_cost__sum if estimated_cost__sum else ""

        contract_amount_work_companies__sum = subprojects.aggregate(Sum('contract_amount_work_companies'))['contract_amount_work_companies__sum']
        datas[_("Exact amount spent on subprojects") + " FCFA"][count+c] = contract_amount_work_companies__sum if contract_amount_work_companies__sum else ""
        if datas[_("Allocation") + " FCFA"][count+c] and datas[_("Total estimate for subprojects") + " FCFA"][count+c]:
            datas[_("Remainder after estimated cost") + " FCFA"][count+c] = datas[_("Allocation") + " FCFA"][count+c] - datas[_("Total estimate for subprojects") + " FCFA"][count+c]
        else:
            datas[_("Remainder after estimated cost") + " FCFA"][count+c] = datas[_("Allocation") + " FCFA"][count+c]

        if datas[_("Allocation") + " FCFA"][count+c] and datas[_("Exact amount spent on subprojects") + " FCFA"][count+c]:
            datas[_("Remaining amount") + " FCFA"][count+c] = datas[_("Allocation") + " FCFA"][count+c] - datas[_("Exact amount spent on subprojects") + " FCFA"][count+c]
        else:
            datas[_("Remaining amount") + " FCFA"][count+c] = datas[_("Allocation") + " FCFA"][count+c]

        # datas[_("Exact amount spent on subprojects") + " FCFA"][count+c] = 0     
        # datas[_("Remaining amount") + " FCFA"][count+c] = 0   


        table_title = self.request.GET.get('table_title')
        return {
            'title': table_title if table_title else _("Allocation"),
            'datas': datas,
            'length_loop': range(0, count+c+1),
            'values': list(datas.values())
        }

    def get_context_data(self, **kwargs):
        ctx = super(DashboardSummaryCVDAllocationListView, self).get_context_data(**kwargs)

        ctx["summary"] = {}
    
        ctx["summary"]["summary_administrative_level_allocation_cvd"] = {}
        for k, v in self.summary_cvd_allocation(ctx['queryset_results']['ald_filter_ids'].copy(), ctx['queryset_results']['id_with_descendants'].copy(), self.request.session.get('project_id')).items():
            ctx["summary"]["summary_administrative_level_allocation_cvd"][k] = v

        ctx["queryset_results"]["administrative_level_type"] = None

        return ctx



class DashboardBeneficiaryVillagesListView(DashboardAdministrativeLevelMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    """Villages and CVD that benefited from subprojects or not, in the
    administrative levels chosen, for the subprojects matching the filters.

    A village benefited directly when a subproject was carried out in it (site,
    or village crossed by a track or an electrification), indirectly through
    its CVD when its CVD has a subproject, indirectly through the list of
    beneficiary villages of a subproject otherwise. A CVD benefited directly
    when it has a subproject (attached to it or carried out in one of its
    villages), indirectly when one of its villages is a beneficiary village of
    a subproject. Each village and CVD is counted once, in the first case that
    applies."""
    template_name = 'tracking.html'
    context_object_name = 'queryset_results'
    table_class_style = 'table-bordered'

    def get_projects_ids(self):
        # Same projects as Subproject.objects.get_objects_by_general_filtre()
        all_projects = self.request.GET.getlist('all_projects[]')
        return all_projects if len(all_projects) >= 2 else [self.request.session.get('project_id')]

    def get_villages(self, ald_filter_ids):
        villages = AdministrativeLevel.objects.filter(
            type=AdministrativeLevel.VILLAGE, administrative_levels_projects__in=self.get_projects_ids()
        )
        if ald_filter_ids:
            villages = villages.filter(
                Q(id__in=ald_filter_ids) |
                Q(parent__id__in=ald_filter_ids) |
                Q(parent__parent__id__in=ald_filter_ids) |
                Q(parent__parent__parent__id__in=ald_filter_ids) |
                Q(parent__parent__parent__parent__id__in=ald_filter_ids)
            )
        return list(
            villages.distinct().select_related('parent__parent__parent__parent', 'cvd').order_by(
                'parent__parent__parent__parent__name', 'parent__parent__parent__name', 'parent__parent__name',
                'parent__name', 'name', 'pk'
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        villages = self.get_villages(ctx['queryset_results']['ald_filter_ids'])

        # The subprojects of the filters, wherever they are: a subproject carried
        # out outside the chosen area can list one of its villages as beneficiary.
        subprojects_ids = self.get_filtered_subprojects().values('pk')
        sites = defaultdict(set)  # village -> subprojects carried out in it
        cvd_subprojects = defaultdict(set)  # CVD -> its subprojects
        for pk, location_id, cvd_id in Subproject.objects.filter(pk__in=subprojects_ids).values_list(
            'pk', 'location_subproject_realized_id', 'cvd_id'
        ):
            if location_id:
                sites[location_id].add(pk)
            if cvd_id:
                cvd_subprojects[cvd_id].add(pk)
        for pk, village_id in Subproject.list_of_villages_crossed_by_the_track_or_electrification.through.objects.filter(
            subproject_id__in=subprojects_ids
        ).values_list('subproject_id', 'administrativelevel_id'):
            sites[village_id].add(pk)
        beneficiaries = defaultdict(set)  # village -> subprojects listing it as beneficiary
        for pk, village_id in Subproject.list_of_beneficiary_villages.through.objects.filter(
            subproject_id__in=subprojects_ids
        ).values_list('subproject_id', 'administrativelevel_id'):
            beneficiaries[village_id].add(pk)
        # The subprojects carried out in a village belong to its CVD too.
        for village_id, cvd_id in AdministrativeLevel.objects.filter(id__in=list(sites), cvd__isnull=False).values_list('id', 'cvd_id'):
            cvd_subprojects[cvd_id].update(sites[village_id])

        def cvd_name(cvd):
            # CVD.get_name() queries the villages of the CVD only when it has no name
            return cvd.name if cvd.name else cvd.get_name()

        DIRECT, THROUGH_CVD, THROUGH_LIST = 'direct', 'cvd', 'list'
        village_labels = {
            DIRECT: _("Direct (site of a subproject)"),
            THROUGH_CVD: _("Indirect (through the CVD)"),
            THROUGH_LIST: _("Indirect (list of beneficiary villages)"),
        }

        def village_benefit(village):
            if sites.get(village.id):
                return DIRECT
            if village.cvd_id and cvd_subprojects.get(village.cvd_id):
                return THROUGH_CVD
            if beneficiaries.get(village.id):
                return THROUGH_LIST
            return None

        def location_columns(datas, row, canton):
            commune = canton.parent if canton else None
            prefecture = commune.parent if commune else None
            region = prefecture.parent if prefecture else None
            datas[_("Region")][row] = region.name if region else "-"
            datas[_("Prefecture")][row] = prefecture.name if prefecture else "-"
            datas[_("Commune")][row] = commune.name if commune else "-"
            datas[_("Canton")][row] = canton.name if canton else "-"

        # --- Villages ---
        beneficiary_villages = {
            _("Region"): {}, _("Prefecture"): {}, _("Commune"): {}, _("Canton"): {}, _("CVD"): {}, _("Village"): {},
            _("Benefit"): {},
            _("Subprojects carried out in the village"): {},
            _("Subprojects of the CVD"): {},
            _("Subprojects listing the village as beneficiary"): {},
        }
        not_beneficiary_villages = {
            _("Region"): {}, _("Prefecture"): {}, _("Commune"): {}, _("Canton"): {}, _("CVD"): {}, _("Village"): {},
        }
        villages_numbers = {DIRECT: 0, THROUGH_CVD: 0, THROUGH_LIST: 0, None: 0}
        villages_by_cvd = defaultdict(list)
        count = not_count = 0
        for village in villages:
            benefit = village_benefit(village)
            villages_numbers[benefit] += 1
            if village.cvd_id:
                villages_by_cvd[village.cvd_id].append(village)
            if benefit:
                datas, row = beneficiary_villages, count
                count += 1
                datas[_("Benefit")][row] = village_labels[benefit]
                datas[_("Subprojects carried out in the village")][row] = len(sites.get(village.id, ()))
                datas[_("Subprojects of the CVD")][row] = len(cvd_subprojects.get(village.cvd_id, ())) if village.cvd_id else 0
                datas[_("Subprojects listing the village as beneficiary")][row] = len(beneficiaries.get(village.id, ()))
            else:
                datas, row = not_beneficiary_villages, not_count
                not_count += 1
            location_columns(datas, row, village.parent)
            datas[_("CVD")][row] = cvd_name(village.cvd) if village.cvd else "-"
            datas[_("Village")][row] = village.name

        # --- CVD (those of the villages listed) ---
        cvds = list(
            CVD.objects.filter(id__in=list(villages_by_cvd))
            .select_related('headquarters_village__parent__parent__parent__parent')
        )
        all_villages_by_cvd = defaultdict(list)  # every village of the CVD
        for cvd_id, village_id, village_name in AdministrativeLevel.objects.filter(
            cvd_id__in=[cvd.id for cvd in cvds]
        ).values_list('cvd_id', 'id', 'name'):
            all_villages_by_cvd[cvd_id].append((village_id, village_name))
        cvd_labels = {
            DIRECT: _("Direct (subproject of the CVD)"),
            THROUGH_LIST: _("Indirect (list of beneficiary villages)"),
        }

        def cvd_benefit(cvd):
            if cvd_subprojects.get(cvd.id):
                return DIRECT
            if any(beneficiaries.get(village_id) for village_id, village_name in all_villages_by_cvd[cvd.id]):
                return THROUGH_LIST
            return None

        def cvd_canton(cvd):
            # CVD.get_canton(), with a village already loaded
            if cvd.headquarters_village:
                return cvd.headquarters_village.parent
            return villages_by_cvd[cvd.id][0].parent

        def location_key(canton):
            names = []
            level = canton
            for i in range(4):
                names.insert(0, level.name if level else "")
                level = level.parent if level else None
            return names

        cvds_numbers = {DIRECT: 0, THROUGH_LIST: 0, None: 0}
        cvds_rows = []
        for cvd in cvds:
            benefit = cvd_benefit(cvd)
            cvds_numbers[benefit] += 1
            canton = cvd_canton(cvd)
            cvds_rows.append((location_key(canton) + [cvd_name(cvd), cvd.pk], canton, cvd, benefit))
        cvds_rows.sort(key=lambda row: row[0])  # region, prefecture, commune, canton, CVD as the villages

        beneficiary_cvds = {
            _("Region"): {}, _("Prefecture"): {}, _("Commune"): {}, _("Canton"): {}, _("CVD"): {},
            _("Benefit"): {},
            _("Number of villages"): {},
            _("Villages where subprojects were carried out"): {},
            _("Subprojects of the CVD"): {},
        }
        not_beneficiary_cvds = {
            _("Region"): {}, _("Prefecture"): {}, _("Commune"): {}, _("Canton"): {}, _("CVD"): {},
            _("Number of villages"): {},
        }
        count = not_count = 0
        for sort_key, canton, cvd, benefit in cvds_rows:
            if benefit:
                datas, row = beneficiary_cvds, count
                count += 1
                datas[_("Benefit")][row] = cvd_labels[benefit]
                datas[_("Villages where subprojects were carried out")][row] = sum(
                    1 for village_id, village_name in all_villages_by_cvd[cvd.id] if sites.get(village_id)
                )
                datas[_("Subprojects of the CVD")][row] = len(cvd_subprojects.get(cvd.id, ()))
            else:
                datas, row = not_beneficiary_cvds, not_count
                not_count += 1
            location_columns(datas, row, canton)
            datas[_("CVD")][row] = sort_key[4]
            datas[_("Number of villages")][row] = len(all_villages_by_cvd[cvd.id])

        # --- Numbers ---
        def percent(number, total):
            # number_format() truncates the decimals: round first
            return "%s %%" % number_format(round(100 * number / total, 1), 1) if total else "-"

        total_villages = len(villages)
        total_cvds = len(cvds)
        villages_beneficiaries = total_villages - villages_numbers[None]
        cvds_beneficiaries = total_cvds - cvds_numbers[None]
        numbers_rows = [
            (_("Direct beneficiaries (site of a subproject)"), villages_numbers[DIRECT], cvds_numbers[DIRECT]),
            (_("Indirect beneficiaries through their CVD"), villages_numbers[THROUGH_CVD], None),
            (_("Indirect beneficiaries through the list of beneficiary villages"), villages_numbers[THROUGH_LIST], cvds_numbers[THROUGH_LIST]),
            (_("Total beneficiaries"), villages_beneficiaries, cvds_beneficiaries),
            (_("Not beneficiaries"), villages_numbers[None], cvds_numbers[None]),
            (_("Total"), total_villages, total_cvds),
        ]
        numbers = {_("Beneficiaries"): {}, _("Villages"): {}, _("% of villages"): {}, _("CVD"): {}, _("% of CVD"): {}}
        for row, (label, villages_number, cvds_number) in enumerate(numbers_rows):
            numbers[_("Beneficiaries")][row] = label
            numbers[_("Villages")][row] = villages_number
            numbers[_("% of villages")][row] = percent(villages_number, total_villages)
            numbers[_("CVD")][row] = cvds_number if cvds_number is not None else "-"
            numbers[_("% of CVD")][row] = percent(cvds_number, total_cvds) if cvds_number is not None else "-"

        def table(title, datas, length):
            return {'title': title, 'datas': datas, 'length_loop': range(length), 'values': list(datas.values())}

        ctx["summary"] = {
            "summary_beneficiary_villages_numbers": table(
                _("Villages and CVD that benefited from subprojects"), numbers, len(numbers_rows)
            ),
            "summary_beneficiary_villages": table(
                _("Villages that benefited from subprojects"), beneficiary_villages, villages_beneficiaries
            ),
            "summary_not_beneficiary_villages": table(
                _("Villages that did not benefit from subprojects"), not_beneficiary_villages, villages_numbers[None]
            ),
            "summary_beneficiary_cvds": table(
                _("CVD that benefited from subprojects"), beneficiary_cvds, cvds_beneficiaries
            ),
            "summary_not_beneficiary_cvds": table(
                _("CVD that did not benefit from subprojects"), not_beneficiary_cvds, cvds_numbers[None]
            ),
        }
        ctx["queryset_results"]["administrative_level_type"] = None
        return ctx
