from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from cosomis.mixins import PageMixin, AJAXRequestMixin
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q, Count, Prefetch
from django.db.models import Sum, Max
from django.http import Http404
from collections import defaultdict

from subprojects.models import Subproject, Step, Component, Project
from administrativelevels.models import AdministrativeLevel, CVD
from administrativelevels.functions import (
    get_administrative_level_ids_descendants, get_children_types_administrativelevels,
    get_administrative_level_ids_ascendants, get_administrative_level_id_ascendant,
    get_administrative_level_ids_descendants_with_dict
)
from assignments.models import AssignAdministrativeLevelToFacilitator
from . import forms
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
            villages_ids = [v.id for canton in cantons for v in canton.children]

            # Nombre d'unités géographiques et CVD
            nbr_geographical_unit = sum(canton.get_list_geographical_unit().count() for canton in cantons)
            nbr_cvd = sum(sum(u.get_cvds().count() for u in canton.get_list_geographical_unit()) for canton in cantons)

            # Liste des villages existants filtrés par type "Village"
            villages_ids = list(
                AdministrativeLevel.objects.get_objects_by_general_filtre(self.request, None)
                .filter(id__in=villages_ids, type="Village")
                .values_list('id', flat=True)
            )

            # Organisation des cantons par région
            region_cantons = {}
            for c in cantons:
                if c.parent and c.parent.parent and c.parent.parent.parent:
                    region_name = c.parent.parent.parent.name
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
            subprojects_qs = Subproject.objects.get_objects_by_general_filtre(self.request, None).filter(
                Q(location_subproject_realized__id__in=villages_ids) | Q(canton__id__in=cantons_ids)
            ).get_actifs()

            datas[_("Number of subprojects selected")][count] = subprojects_qs.filter(
                subproject_type_designation__in=["Subproject"]
            ).count()
            datas[_("Number of infrastructures")][count] = subprojects_qs.filter(
                subproject_type_designation__in=["Subproject", "Infrastructure"]
            ).count()

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

        periods_project = PeriodWave.objects.filter(project_id=project_id)
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
            .select_related("administrative_level", "administrative_level__parent")
        )

        count = 0
        for line in lines:
            datas[_("X")][count] = line.name

            # Filtrer les assignations liées à la ligne courante
            assigns = assigns_qs.filter(
                Q(administrative_level=line) |
                Q(administrative_level__parent=line) |
                Q(administrative_level__parent__parent=line) |
                Q(administrative_level__parent__parent__parent=line) |
                Q(administrative_level__parent__parent__parent__parent=line)
            )

            dict_dict = defaultdict(list)

            for assign in assigns:
                for column in columns:
                    if column != "Village":
                        dict_dict[column].extend(
                            get_administrative_level_id_ascendant(assign.administrative_level.id, column)
                        )
                    elif column == "Village" and not dict_dict[column]:
                        dict_dict[column] = list(assigns.values_list("id", flat=True))

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
        components = Component.objects.filter(parent__name="Composante 1")
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
            subprojects = Subproject.objects.get_objects_by_general_filtre(self.request, None).filter(
                Q(location_subproject_realized__id__in=ids) | 
                Q(canton__id__in=ids)
            ).get_actifs()
        else:
            allocations_project = AdministrativeLevelAllocation.objects.filter(
                project_id=project_id,
                cvd=None
            )
            subprojects = Subproject.objects.get_objects_by_general_filtre(self.request, None).get_actifs()
            
        for line in lines:
            if not adl_ids:
                _ids = ([line.administrative_level.id] + get_administrative_level_ids_descendants(line.administrative_level.id, None, [], self.request.session.get('project_id')))
            else:
                _ids = ([line.administrative_level.id] + (id_with_descendants.get(str(line.administrative_level.id)) or []))
            
            allocation_adl_project = allocations_project.filter(
                administrative_level__id=line.administrative_level.id
            )
            subproject_filter_adl_project = subprojects.filter(
                Q(location_subproject_realized__id__in=_ids) | 
                Q(canton__id__in=_ids)
            )
            for component in components:
                subproject_filter = subproject_filter_adl_project.filter(component_id=component.id)

                datas[_("Cantons")][count] = line.administrative_level.name
                datas[_("Component")][count] = component.name

                amount__sum = allocation_adl_project.filter(component_id=component.id).aggregate(Sum('amount'))['amount__sum'] or 0
                subproject_agg = subproject_filter.aggregate(
                    estimated_cost_sum=Sum('estimated_cost'),
                    spent_sum=Sum('contract_amount_work_companies')
                )
                estimated_cost__sum = subproject_agg['estimated_cost_sum'] or 0
                contract_amount_work_companies__sum = subproject_agg['spent_sum'] or 0

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

            amount__sum = allocations_project.filter(component_id=component.id).aggregate(Sum('amount'))['amount__sum'] or 0
            subproject_filter = subprojects.filter(component_id=component.id)            
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
        components = Component.objects.filter(parent__name="Composante 1")
        ids = []
        
        if adl_ids:
            for _id in adl_ids:
                # ids += ([_id] + get_administrative_level_ids_descendants(_id, None, [], self.request.session.get('project_id')))
                ids += ([_id] + (id_with_descendants.get(str(_id)) or []))
            lines = CVD.objects.filter(id__in=[
                obj.cvd.id for obj in AdministrativeLevel.objects.get_objects_by_general_filtre(self.request, None).filter(id__in=ids) if obj.cvd
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
            subprojects = Subproject.objects.get_objects_by_general_filtre(self.request, None).filter(
                Q(location_subproject_realized__id__in=ids) | 
                Q(canton__id__in=ids)
            ).get_actifs()
        else:
            allocations_project = AdministrativeLevelAllocation.objects.filter(
                project_id=project_id,
                administrative_level=None
            )
            subprojects = Subproject.objects.get_objects_by_general_filtre(self.request, None).get_actifs()

        for line in lines:
            _ids = [obj.id for obj in line.get_villages()]
            allocation_adl_project = allocations_project.filter(
                cvd__id=line.id
            )
            subproject_filter_adl_project = subprojects.filter(
                Q(location_subproject_realized__id__in=_ids) | 
                Q(canton__id__in=_ids)
            )
            for component in components:
                datas[_("CVD")][count] = line.name
                datas[_("Component")][count] = component.name

                try:
                    amount__sum = allocation_adl_project.filter(
                        component_id=component.id
                    ).aggregate(Sum('amount'))['amount__sum']

                    datas[_("Allocation") + " FCFA"][count] = amount__sum if amount__sum else ""
                except:
                    datas[_("Allocation") + " FCFA"][count] = 0
                
                subproject_filter = subproject_filter_adl_project.filter(
                        component_id=component.id
                    )
                try:
                    estimated_cost__sum = subproject_filter.aggregate(Sum('estimated_cost'))['estimated_cost__sum']

                    datas[_("Total estimate for subprojects") + " FCFA"][count] = estimated_cost__sum if estimated_cost__sum else ""
                except:
                    datas[_("Total estimate for subprojects") + " FCFA"][count] = 0
                
                try:
                    contract_amount_work_companies__sum = subproject_filter.aggregate(Sum('contract_amount_work_companies'))['contract_amount_work_companies__sum']

                    datas[_("Exact amount spent on subprojects") + " FCFA"][count] = contract_amount_work_companies__sum if contract_amount_work_companies__sum else ""
                except:
                    datas[_("Exact amount spent on subprojects") + " FCFA"][count] = 0
                
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
                component_id=component.id
            ).aggregate(Sum('amount'))['amount__sum']
            datas[_("Allocation") + " FCFA"][count+c] = amount__sum if amount__sum else ""

            subproject_filter = subprojects.filter(component_id=component.id)

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