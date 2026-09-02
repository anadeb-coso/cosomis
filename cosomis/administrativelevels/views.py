from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.views.generic import DetailView, TemplateView, ListView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from cosomis.constants import OBSTACLES_FOCUS_GROUP, GOALS_FOCUS_GROUP
from cosomis.mixins import PageMixin
from django.http import Http404
import pandas as pd
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum

from administrativelevels.models import AdministrativeLevel, GeographicalUnit, CVD
from administrativelevels.libraries import convert_file_to_dict, download_file
from administrativelevels import functions as administrativelevels_functions
from subprojects.models import VillageObstacle, VillageGoal, VillagePriority, Component
from .forms import GeographicalUnitForm, CVDForm, AdministrativeLevelForm
from usermanager.permissions import (
    CDDSpecialistPermissionRequiredMixin, SuperAdminPermissionRequiredMixin,
    AdminPermissionRequiredMixin, AccountantPermissionRequiredMixin
    )
from administrativelevels import functions_cvd as cvd_functions
from administrativelevels.functions import (
    get_administrative_level_ids_descendants,
)
from administrativelevels.functions_cvd import save_cvd_instead_of_csv_file_datas_in_db
from administrativelevels.functions_adl import get_cascade_villages_ids_by_administrative_level_id
from financial import function_allocation
from financial.models.allocation import AdministrativeLevelAllocation
from dashboard.forms import AdministrativeLevelFilterForm


class VillageDetailView(PageMixin, LoginRequiredMixin, DetailView):
    """Class to present the detail page of one village"""

    model = AdministrativeLevel
    template_name = 'village_detail.html'
    context_object_name = 'village'
    title = _('Village')
    active_level1 = 'administrative_levels'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]
    
    def get_context_data(self, **kwargs):
        context = super(VillageDetailView, self).get_context_data(**kwargs)
        if context.get("object") and context.get("object").type == "Village" : # Verify if the administrativeLevel type is Village
            return context
        raise Http404


class AdministrativeLevelDetailView(PageMixin, LoginRequiredMixin, DetailView):
    """Class to present the detail page of one village"""

    model = AdministrativeLevel
    template_name = 'village_detail.html'
    context_object_name = 'village'
    title = _('Village')
    active_level1 = 'administrative_levels'
    # breadcrumb = [
    #     {
    #         'url': '',
    #         'title': title
    #     },
    # ]
    
    def get_context_data(self, **kwargs):
        context = super(AdministrativeLevelDetailView, self).get_context_data(**kwargs)
        _type = self.request.GET.get("type", context['object'].type)
        self.template_name = (_type.lower() if _type.lower() in ('village', 'canton') else "administrativelevel") + "_detail.html"
        context['context_object_name'] = _type
        context['title'] = _type
        context['hide_content_header'] = True
        context['administrativelevel_profile'] = context['object']
        # context['breadcrumb'] = [
        #     {
        #         'url': '',
        #         'title': _type
        #     },
        # ]
        return context

        
class AdministrativeLevelCreateView(PageMixin, LoginRequiredMixin, AdminPermissionRequiredMixin, CreateView):
    model = AdministrativeLevel
    template_name = 'administrativelevel_create.html'
    context_object_name = 'administrativelevel'
    title = _('Create Administrative level')
    active_level1 = 'administrative_levels'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]
    def get_parent(self, type: str):
        parent = None
        if type == "Prefecture":
            parent = "Region"
        elif type == "Commune":
            parent = "Prefecture"
        elif type == "Canton":
            parent = "Commune"
        elif type == "Village":
            parent = "Canton"
        return parent

    form_class = AdministrativeLevelForm # specify the class form to be displayed
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = AdministrativeLevelForm(self.get_parent(self.request.GET.get("type")))
        return context
    
    def post(self, request, *args, **kwargs):
        form = AdministrativeLevelForm(self.get_parent(self.request.GET.get("type")), request.POST)
        if form.is_valid():
            instance = form.save()
            if instance.area_status:
                instance.cascade_area_status()
            return redirect('administrativelevels:list')
        return super(AdministrativeLevelCreateView, self).get(request, *args, **kwargs)


class AdministrativeLevelUpdateView(PageMixin, LoginRequiredMixin, AdminPermissionRequiredMixin, UpdateView):
    model = AdministrativeLevel
    template_name = 'administrativelevel_create.html'
    context_object_name = 'administrativelevel'
    title = _('Update Administrative level')
    active_level1 = 'administrative_levels'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]
    def get_parent(self, type: str):
        parent = None
        if type == "Prefecture":
            parent = "Region"
        elif type == "Commune":
            parent = "Prefecture"
        elif type == "Canton":
            parent = "Commune"
        elif type == "Village":
            parent = "Canton"
        return parent

    form_class = AdministrativeLevelForm # specify the class form to be displayed
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = AdministrativeLevelForm(self.get_parent(self.request.GET.get("type")), instance=self.get_object())
        return context
    
    def post(self, request, *args, **kwargs):
        form = AdministrativeLevelForm(self.get_parent(self.request.GET.get("type")), request.POST, instance=self.get_object())
        if form.is_valid():
            instance = form.save()
            if instance.area_status:
                instance.cascade_area_status()
            return redirect('administrativelevels:list')
        return super(AdministrativeLevelUpdateView, self).get(request, *args, **kwargs)
    

class UploadCSVView(PageMixin, LoginRequiredMixin, AdminPermissionRequiredMixin, TemplateView):
    """Class to upload and save the administrativelevels"""

    template_name = 'upload.html'
    context_object_name = 'Upload'
    title = _("Upload")
    active_level1 = 'administrative_levels'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def post(self, request, *args, **kwargs):
        datas = {}
        redirect_path = 'administrativelevels:list'
        _type = request.POST.get('_type')
        if _type in ("priority", "subproject"):
            """Upload priorities by csv"""
            redirect_path = "administrativelevels:priorities_priorities"
            try:
                datas = convert_file_to_dict.conversion_file_xlsx_merger_to_dict(
                    request.FILES.get('file'), request.POST.get('sheet_name'),
                    columns_fillna= ["Canton", "Villages", "Sous-projets prioritaire de la sous-composante 1.3 (Besoins des jeunes)"]
                    )
            except pd.errors.ParserError as exc:
                datas = convert_file_to_dict.conversion_file_csv_merger_to_dict(
                    request.FILES.get('file'), request.POST.get('sheet_name'),
                    columns_fillna= ["Canton", "Villages", "Sous-projets prioritaire de la sous-composante 1.3 (Besoins des jeunes)"]
                    )
            except Exception as exc:
                messages.info(request, _("An error has occurred..."))
            
            try:
                administrative_level_id = request.POST["administrative_level_id"]
                message, file_path = administrativelevels_functions.save_csv_datas_priorities_in_db(datas, administrative_level_id if bool(request.POST.get("administrative_level_id_checkbox")) else 0, _type) # call function to save CSV datas in database
                
                return download_file.download(request, file_path, "text/plain")

                # if message:
                #     messages.info(request, message)
                # return redirect(redirect_path, administrative_level_id=administrative_level_id)
            except Exception as exc:
                raise Http404
        elif _type == "subproject_new":
            """Load Subprojects"""
            redirect_path = "subprojects:list"
            try:
                datas = convert_file_to_dict.conversion_file_xlsx_to_dict(request.FILES.get('file'), request.POST.get('sheet_name'))
            except pd.errors.ParserError as exc:
                datas = convert_file_to_dict.conversion_file_csv_to_dict(request.FILES.get('file'), request.POST.get('sheet_name'))
            except Exception as exc:
                messages.info(request, _("An error has occurred..."))
            # try:
            message, file_path = administrativelevels_functions.save_csv_datas_priorities_in_db(datas, 0, _type) # call function to save CSV datas in database
            
            return download_file.download(request, file_path, "text/plain")
            
            # except Exception as exc:
            #     raise Http404
        
        else:
            datas = convert_file_to_dict.conversion_file_xlsx_to_dict(request.FILES.get('file'))
            try:
                datas = convert_file_to_dict.conversion_file_xlsx_to_dict(request.FILES.get('file'))
            except pd.errors.ParserError as exc:
                datas = convert_file_to_dict.conversion_file_csv_to_dict(request.FILES.get('file'))
            except Exception as exc:
                messages.info(request, _("An error has occurred..."))
            
            if _type == "allocation":
                """Load allocation"""
                redirect_path = "financial:financials"
                message, file_path = function_allocation.save_csv_datas_cantons_allocations_in_db(datas)
                return download_file.download(request, file_path, "text/plain")
            elif _type == "cvd":
                """Load CVD"""
                redirect_path = "administrativelevels:cvds_list"
                message = save_cvd_instead_of_csv_file_datas_in_db(datas) # call function to save CSV datas in database
            else:
                """Load Administrative Levels"""
                message = administrativelevels_functions.save_csv_file_datas_in_db(datas) # call function to save CSV datas in database
                
        if message:
            messages.info(request, message)

        return redirect(redirect_path)
    
    def get(self, request, *args, **kwargs):
        context = super(UploadCSVView, self).get(request, *args, **kwargs)
        return context



class DownloadCSVView(PageMixin, LoginRequiredMixin, TemplateView):
    """Class to download administrativelevels under excel file"""

    template_name = 'components/download.html'
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
        administrative_level_ids_get = self.request.POST.getlist('value_of_type', None)
        administrative_level_type = self.request.POST.get('type', 'All').title()
        
        administrative_level_type = "All" if administrative_level_type in ("", "null", "undefined") else administrative_level_type
        
        ald_filter_ids = []
        administrative_levels_ids = []
        if not administrative_level_ids_get:
            administrative_level_ids_get.append("")
        for ald_id in administrative_level_ids_get:
            ald_id = 0 if ald_id in ("", "null", "undefined", "All") else ald_id
            administrative_levels_ids += get_administrative_level_ids_descendants(
                ald_id, None, [], self.request.session.get('project_id')
            )
            if ald_id:
                ald_filter_ids.append(int(ald_id))
                
        administrative_levels_ids = list(set(administrative_levels_ids))

        try:
            file_path = administrativelevels_functions.get_administratives_levels_under_file_excel_or_csv(
                request.POST.get("file_type"), #file_type=request.POST.get("file_type"),
                administrative_levels_ids
                # params={"type":request.POST.get("type"), "value_of_type":request.POST.get("value_of_type")}
            )

        except Exception as exc:
            messages.info(request, _("An error has occurred..."))

        if not file_path:
            return redirect('administrativelevels:list')
        else:
            return download_file.download(
                request, 
                file_path,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    


class AdministrativeLevelsListView(PageMixin, LoginRequiredMixin, ListView):
    """Display administrative level list"""

    model = AdministrativeLevel
    queryset = [] # AdministrativeLevel.objects.filter(type="Village")
    template_name = 'administrativelevels_list.html'
    context_object_name = 'administrativelevels'
    title = _('Administrative levels')
    active_level1 = 'administrative_levels'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def filter_list_by_delete_empty(self, _list):
        if _list:
            return [elt for elt in _list if elt]
        else:
            return []
        
    def get_filters_context(self):
        kwargs = dict()

        kwargs["all_projects"] = self.request.session.get('tree_structure_projects_ids') if self.request.GET.get('include_all_projects', 0) in (1, '1') else []

        id_regions = self.filter_list_by_delete_empty(self.request.GET.getlist('region', []))
        id_prefectures = self.filter_list_by_delete_empty(self.request.GET.getlist('prefecture', []))
        id_communes = self.filter_list_by_delete_empty(self.request.GET.getlist('commune', []))
        id_cantons = self.filter_list_by_delete_empty(self.request.GET.getlist('canton', []))
        id_villages = self.filter_list_by_delete_empty(self.request.GET.getlist('village', []))

        kwargs["id_regions_selected"] = id_regions
        kwargs["id_prefectures_selected"] = id_prefectures
        kwargs["id_communes_selected"] = id_communes
        kwargs["id_cantons_selected"] = id_cantons
        kwargs["id_villages_selected"] = id_villages
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

    def get_queryset(self):
        count = 100
        search = self.request.GET.get("search", None)
        page_number = self.request.GET.get("page", None)
        _type = self.request.GET.get("type", "Village")
        id_regions = self.filter_list_by_delete_empty(self.request.GET.getlist('region', []))
        id_prefectures = self.filter_list_by_delete_empty(self.request.GET.getlist('prefecture', []))
        id_communes = self.filter_list_by_delete_empty(self.request.GET.getlist('commune', []))
        id_cantons = self.filter_list_by_delete_empty(self.request.GET.getlist('canton', []))
        id_villages = self.filter_list_by_delete_empty(self.request.GET.getlist('village', []))
        include_all_projects_checked = self.request.GET.get('include_all_projects', 0) in (1, '1')

        all_projects = self.request.session.get('tree_structure_projects_ids') if include_all_projects_checked else [self.request.session.get('project_id')]
        
        administrative_levels = AdministrativeLevel.objects.filter(
            type=_type,
            administrative_levels_projects__in=all_projects
        )

        if (
            (id_regions and 'All' not in id_regions) or 
            (id_prefectures and 'All' not in id_prefectures) or 
            (id_communes and 'All' not in id_communes) or 
            (id_cantons and 'All' not in id_cantons) or 
            (id_villages and 'All' not in id_villages)
        ):
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
            
            administrative_levels = administrative_levels.filter(
                Q(id__in=_ids) | 
                Q(parent__id__in=_ids) | 
                Q(parent__parent__id__in=_ids) | 
                Q(parent__parent__parent__id__in=_ids) | 
                Q(parent__parent__parent__parent__id__in=_ids)
            )
        
        if search and search != "All":
            search = search.upper()
            administrative_levels = administrative_levels.filter(name__icontains=search).distinct()
        
        administrative_levels = administrative_levels.distinct()

        if (
            id_regions or id_prefectures or id_communes or id_cantons or id_villages or search or include_all_projects_checked
        ):
            count = administrative_levels.count()
            if count == 0:
                count = 1
        
        return Paginator(administrative_levels, count).get_page(page_number)
    

        # return super().get_queryset()
    def get_context_data(self, **kwargs):
        ctx = super(AdministrativeLevelsListView, self).get_context_data(**kwargs)
        ctx.update(self.get_filters_context())

        # ctx['hide_content_header'] = True

        ctx['search'] = self.request.GET.get("search", None)
        ctx['type'] = self.request.GET.get("type", "Village")

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

        return ctx


class AdministrativeLevelAreaStatusView(PageMixin, LoginRequiredMixin, AdminPermissionRequiredMixin, ListView):
    """Bulk assignment page: select several Regions/Prefectures/Communes/Cantons/Villages
    and assign them all the same area_status (risk level). The status is then
    cascaded down to descendants and used to recompute ancestors' status."""

    model = AdministrativeLevel
    template_name = 'administrativelevel_area_status.html'
    context_object_name = 'administrativelevels'
    title = _('Area status')
    active_level1 = 'administrative_levels'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def filter_list_by_delete_empty(self, _list):
        return [elt for elt in _list if elt] if _list else []

    def get_filters_context(self):
        kwargs = dict()

        id_regions = self.filter_list_by_delete_empty(self.request.GET.getlist('region', []))
        id_prefectures = self.filter_list_by_delete_empty(self.request.GET.getlist('prefecture', []))
        id_communes = self.filter_list_by_delete_empty(self.request.GET.getlist('commune', []))
        id_cantons = self.filter_list_by_delete_empty(self.request.GET.getlist('canton', []))
        id_villages = self.filter_list_by_delete_empty(self.request.GET.getlist('village', []))

        kwargs["id_regions_selected"] = id_regions
        kwargs["id_prefectures_selected"] = id_prefectures
        kwargs["id_communes_selected"] = id_communes
        kwargs["id_cantons_selected"] = id_cantons
        kwargs["id_villages_selected"] = id_villages

        adm_queryset = AdministrativeLevel.objects.all()
        kwargs["regions"] = adm_queryset.filter(type=AdministrativeLevel.REGION)

        kwargs["prefectures"] = adm_queryset.filter(type=AdministrativeLevel.PREFECTURE)
        if id_regions:
            kwargs["prefectures"] = kwargs["prefectures"].filter(parent__id__in=id_regions)

        kwargs["communes"] = adm_queryset.filter(type=AdministrativeLevel.COMMUNE)
        if id_prefectures:
            kwargs["communes"] = kwargs["communes"].filter(parent__id__in=id_prefectures)
        elif id_regions:
            kwargs["communes"] = kwargs["communes"].filter(parent__parent__id__in=id_regions)

        kwargs["cantons"] = adm_queryset.filter(type=AdministrativeLevel.CANTON)
        if id_communes:
            kwargs["cantons"] = kwargs["cantons"].filter(parent__id__in=id_communes)
        elif id_prefectures:
            kwargs["cantons"] = kwargs["cantons"].filter(parent__parent__id__in=id_prefectures)
        elif id_regions:
            kwargs["cantons"] = kwargs["cantons"].filter(parent__parent__parent__id__in=id_regions)

        kwargs["villages"] = adm_queryset.filter(type=AdministrativeLevel.VILLAGE)
        if id_cantons:
            kwargs["villages"] = kwargs["villages"].filter(parent__id__in=id_cantons)
        elif id_communes:
            kwargs["villages"] = kwargs["villages"].filter(parent__parent__id__in=id_communes)
        elif id_prefectures:
            kwargs["villages"] = kwargs["villages"].filter(parent__parent__parent__id__in=id_prefectures)
        elif id_regions:
            kwargs["villages"] = kwargs["villages"].filter(parent__parent__parent__parent__id__in=id_regions)

        return kwargs

    def get_queryset(self):
        _type = self.request.GET.get("type", AdministrativeLevel.VILLAGE)
        search = self.request.GET.get("search", None)
        id_regions = self.filter_list_by_delete_empty(self.request.GET.getlist('region', []))
        id_prefectures = self.filter_list_by_delete_empty(self.request.GET.getlist('prefecture', []))
        id_communes = self.filter_list_by_delete_empty(self.request.GET.getlist('commune', []))
        id_cantons = self.filter_list_by_delete_empty(self.request.GET.getlist('canton', []))
        id_villages = self.filter_list_by_delete_empty(self.request.GET.getlist('village', []))

        administrative_levels = AdministrativeLevel.objects.filter(type=_type)

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
        else:
            _ids = None

        if _ids:
            administrative_levels = administrative_levels.filter(
                Q(id__in=_ids) |
                Q(parent__id__in=_ids) |
                Q(parent__parent__id__in=_ids) |
                Q(parent__parent__parent__id__in=_ids) |
                Q(parent__parent__parent__parent__id__in=_ids)
            )

        if search:
            administrative_levels = administrative_levels.filter(name__icontains=search.upper())

        return administrative_levels.distinct().order_by('name')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(self.get_filters_context())

        ctx['search'] = self.request.GET.get("search", None)
        ctx['type'] = self.request.GET.get("type", AdministrativeLevel.VILLAGE)
        ctx['area_status_choices'] = AdministrativeLevel.AreaStatus.choices

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

        return ctx

    def post(self, request, *args, **kwargs):
        selected_ids = request.POST.getlist('administrative_levels')
        new_status = request.POST.get('area_status')

        if selected_ids and new_status in AdministrativeLevel.AreaStatus.values:
            AdministrativeLevel.objects.filter(id__in=selected_ids).update(area_status=new_status)
            for level in AdministrativeLevel.objects.filter(id__in=selected_ids):
                level.cascade_area_status()
            messages.success(request, _("Area status updated successfully."))
        else:
            messages.error(request, _("Please select at least one administrative level and an area status."))

        query_string = request.GET.urlencode()
        url = reverse_lazy('administrativelevels:area_status')
        return redirect(f"{url}?{query_string}" if query_string else url)


#Obstacles
class ObstaclesListView(PageMixin, LoginRequiredMixin, TemplateView):
    model = VillageObstacle
    template_name = 'priorities/obstacles.html'
    context_object_name = 'obstacles'
    title = _('Village development priorities - Cycle 1')
    active_level1 = 'financial'
    active_level2 = 'obstacles'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]
    administrative_level_id = 0
    administrativelevel_village = None

    def get_context_data(self, **kwargs):
        ctx = super(ObstaclesListView, self).get_context_data(**kwargs)
        ctx.setdefault('administrativelevel_village', ObstaclesListView.administrativelevel_village)
        ctx.setdefault('OBSTACLES_FOCUS_GROUP', OBSTACLES_FOCUS_GROUP)

        ctx.setdefault('obstacles', VillageObstacle.objects.filter(administrative_level_id=ObstaclesListView.administrative_level_id).order_by('ranking'))

        return ctx

    def get(self, request, *args, **kwargs):
        try:
            ObstaclesListView.administrative_level_id = kwargs['administrative_level_id']
            ObstaclesListView.administrativelevel_village = AdministrativeLevel.objects.get(id=ObstaclesListView.administrative_level_id, type="Village")
            context = super(ObstaclesListView, self).get(request, *args, **kwargs)
            # context['obstacles'] = VillageObstacle.objects.filter(administrative_level_id=ObstaclesListView.administrative_level_id)
        except Exception as exc:
            raise Http404
        return context
    

    def post(self, request, *args, **kwargs):
        
        group = request.POST.get('group')
        description = request.POST.get('description')
        if group and description:
            '''Add'''
            obstacle = VillageObstacle()
            obstacle.focus_group = group
            obstacle.description = description
            obstacle.administrative_level = ObstaclesListView.administrativelevel_village
            obstacle.meeting_id = 1
            obstacle.save(user=self.request.user)
            messages.info(request, _("Add successfully!"))
        else:
            '''Edit'''
            for key in request.POST:
                if key and type(key) is str and '-' in key and key[-1].isdigit():
                    try:
                        id_str = key.split('-')[-1]
                        id = int(id_str)
                        group = request.POST.get('group-' + id_str)
                        description = request.POST.get('description-' + id_str)
                        if group and description:
                            obstacle = VillageObstacle.objects.get(id=id)
                            obstacle.focus_group = group
                            obstacle.description = description
                            obstacle.save(user=self.request.user)
                            messages.info(request, _("Update successfully!"))
                            break
                    except Exception as exc:
                        raise Http404
        if not description:
            messages.info(request, _("The description is required"))

        return self.get(request, *args, **kwargs)

@login_required
def obstacle_delete(request, obstacle_id):
    """Function to delete one obstacle"""
    administrative_level_id = 0
    try:
        obstacle = VillageObstacle.objects.get(id=obstacle_id)
        administrative_level_id = obstacle.administrative_level_id
        obstacle.delete()
        messages.info(request, _("Obstacle delete successfully"))
    except Exception as exc:
        raise Http404
    
    return redirect('administrativelevels:priorities_obstacles', administrative_level_id=administrative_level_id)



#Goals
class GoalsListView(PageMixin, LoginRequiredMixin, TemplateView):
    model = VillageGoal
    template_name = 'priorities/goals.html'
    context_object_name = 'goals'
    title = _('Village development priorities - Cycle 1')
    active_level1 = 'financial'
    active_level2 = 'goals'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]
    administrative_level_id = 0
    administrativelevel_village = None

    def get_context_data(self, **kwargs):
        ctx = super(GoalsListView, self).get_context_data(**kwargs)
        ctx.setdefault('administrativelevel_village', GoalsListView.administrativelevel_village)
        ctx.setdefault('GOALS_FOCUS_GROUP', GOALS_FOCUS_GROUP)

        ctx.setdefault('goals', VillageGoal.objects.filter(administrative_level_id=GoalsListView.administrative_level_id).order_by('ranking'))

        return ctx

    def get(self, request, *args, **kwargs):
        try:
            GoalsListView.administrative_level_id = kwargs['administrative_level_id']
            GoalsListView.administrativelevel_village = AdministrativeLevel.objects.get(id=GoalsListView.administrative_level_id, type="Village")
            context = super(GoalsListView, self).get(request, *args, **kwargs)
            # context['goals'] = VillageGoal.objects.filter(administrative_level_id=GoalsListView.administrative_level_id)
        except Exception as exc:
            raise Http404
        return context
    

    def post(self, request, *args, **kwargs):
        
        group = request.POST.get('group')
        description = request.POST.get('description')
        if group and description:
            '''Add'''
            goal = VillageGoal()
            goal.focus_group = group
            goal.description = description
            goal.administrative_level = GoalsListView.administrativelevel_village
            goal.meeting_id = 1
            goal.save(user=self.request.user)
            messages.info(request, _("Add successfully!"))
        else:
            '''Edit'''
            for key in request.POST:
                if key and type(key) is str and '-' in key and key[-1].isdigit():
                    try:
                        id_str = key.split('-')[-1]
                        id = int(id_str)
                        group = request.POST.get('group-' + id_str)
                        description = request.POST.get('description-' + id_str)
                        if group and description:
                            goal = VillageGoal.objects.get(id=id)
                            goal.focus_group = group
                            goal.description = description
                            goal.save(user=self.request.user)
                            messages.info(request, _("Update successfully!"))
                            break
                    except Exception as exc:
                        raise Http404
        if not description:
            messages.info(request, _("The description is required"))

        return self.get(request, *args, **kwargs)

@login_required
def goal_delete(request, goal_id):
    """Function to delete one goal"""
    administrative_level_id = 0
    try:
        goal = VillageGoal.objects.get(id=goal_id)
        administrative_level_id = goal.administrative_level_id
        goal.delete()
        messages.info(request, _("Goal delete successfully"))
    except Exception as exc:
        raise Http404
    
    return redirect('administrativelevels:priorities_goals', administrative_level_id=administrative_level_id)



#Priorities
class PrioritiesListView(PageMixin, LoginRequiredMixin, TemplateView):
    model = VillagePriority
    template_name = 'priorities/priorities.html'
    context_object_name = 'priorities'
    title = _('Village development priorities - Cycle 1')
    active_level1 = 'financial'
    active_level2 = 'eligible_priorities'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]
    administrative_level_id = 0
    administrativelevel_village = None

    def get_context_data(self, **kwargs):
        ctx = super(PrioritiesListView, self).get_context_data(**kwargs)
        ctx.setdefault('administrativelevel_village', PrioritiesListView.administrativelevel_village)
        ctx.setdefault('components', Component.objects.all())
        ctx.setdefault('goals', VillageGoal.objects.filter(administrative_level=PrioritiesListView.administrativelevel_village))
        
        ctx.setdefault('priorities', VillagePriority.objects.filter(administrative_level_id=PrioritiesListView.administrative_level_id).order_by('ranking'))
        
        return ctx

    def get(self, request, *args, **kwargs):
        try:
            PrioritiesListView.administrative_level_id = kwargs['administrative_level_id']
            PrioritiesListView.administrativelevel_village = AdministrativeLevel.objects.get(id=PrioritiesListView.administrative_level_id, type="Village")
            context = super(PrioritiesListView, self).get(request, *args, **kwargs)
            # context['priorities'] = VillagePriority.objects.filter(administrative_level_id=PrioritiesListView.administrative_level_id)
            
        except Exception as exc:
            raise Http404
        return context
    

    def post(self, request, *args, **kwargs):
        
        component_id = request.POST.get('component')
        proposed_men = request.POST.get('proposed_men')
        proposed_women = request.POST.get('proposed_women')
        estimated_cost = request.POST.get('estimated_cost')
        climate_changing_contribution = request.POST.get('climate_changing_contribution')
        if component_id and climate_changing_contribution:
            '''Add'''
            priority = VillagePriority()
            priority.component_id = int(component_id)
            priority.proposed_men = int(proposed_men) if proposed_men else 0
            priority.proposed_women = int(proposed_women) if proposed_women else 0
            priority.estimated_cost = float(estimated_cost) if estimated_cost else 0.0
            priority.climate_changing_contribution = climate_changing_contribution
            priority.administrative_level = PrioritiesListView.administrativelevel_village
            priority.meeting_id = 1
            priority.save(user=self.request.user)
            messages.info(request, _("Add successfully!"))
        else:
            '''Edit'''
            for key in request.POST:
                if key and type(key) is str and '-' in key and key[-1].isdigit():
                    try:
                        id_str = key.split('-')[-1]
                        id = int(id_str)
                        component_id = int(request.POST.get('component-' + id_str))
                        proposed_men = request.POST.get('proposed_men-' + id_str)
                        proposed_women = request.POST.get('proposed_women-' + id_str)
                        estimated_cost = request.POST.get('estimated_cost-' + id_str)
                        climate_changing_contribution = request.POST.get('climate_changing_contribution-' + id_str)
                        if component_id and climate_changing_contribution:
                            priority = VillagePriority.objects.get(id=id)
                            priority.component_id = component_id
                            priority.proposed_men = int(proposed_men) if proposed_men else 0
                            priority.proposed_women = int(proposed_women) if proposed_women else 0
                            priority.estimated_cost = float(estimated_cost) if estimated_cost else 0.0
                            priority.climate_changing_contribution = climate_changing_contribution
                            priority.save(user=self.request.user)
                            messages.info(request, _("Update successfully!"))
                            break
                    except Exception as exc:
                        raise Http404
                        
        if not component_id or not climate_changing_contribution:
            messages.info(request, _("Choice one component and give the description!"))

        return self.get(request, *args, **kwargs)

@login_required
def priority_delete(request, priority_id):
    """Function to delete one priority"""
    administrative_level_id = 0
    try:
        priority = VillagePriority.objects.get(id=priority_id)
        administrative_level_id = priority.administrative_level_id
        priority.delete()
        messages.info(request, _("Priority delete successfully"))
    except Exception as exc:
        raise Http404
    
    return redirect('administrativelevels:priorities_priorities', administrative_level_id=administrative_level_id)



#====================== Geographical unit=========================================
class GeographicalUnitListView(PageMixin, LoginRequiredMixin, ListView):
    """Display geographical unit list"""

    model = GeographicalUnit
    queryset = [] #GeographicalUnit.objects.all()
    template_name = 'geographical_unit_list.html'
    context_object_name = 'geographicalunits'
    title = _('Geographical units')
    active_level1 = 'administrative_levels'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def filter_list_by_delete_empty(self, _list):
        if _list:
            return [elt for elt in _list if elt]
        else:
            return []
        
    def get_filters_context(self):
        kwargs = dict()

        kwargs["all_projects"] = self.request.session.get('tree_structure_projects_ids') if self.request.GET.get('include_all_projects', 0) in (1, '1') else []

        id_regions = self.filter_list_by_delete_empty(self.request.GET.getlist('region', []))
        id_prefectures = self.filter_list_by_delete_empty(self.request.GET.getlist('prefecture', []))
        id_communes = self.filter_list_by_delete_empty(self.request.GET.getlist('commune', []))
        id_cantons = self.filter_list_by_delete_empty(self.request.GET.getlist('canton', []))
        id_villages = self.filter_list_by_delete_empty(self.request.GET.getlist('village', []))

        kwargs["id_regions_selected"] = id_regions
        kwargs["id_prefectures_selected"] = id_prefectures
        kwargs["id_communes_selected"] = id_communes
        kwargs["id_cantons_selected"] = id_cantons
        kwargs["id_villages_selected"] = id_villages
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

    # def get_queryset(self):
    #     return super().get_queryset()
    def get_queryset(self):
        count = 100
        search = self.request.GET.get("search", None)
        page_number = self.request.GET.get("page", None)        
        id_regions = self.filter_list_by_delete_empty(self.request.GET.getlist('region', []))
        id_prefectures = self.filter_list_by_delete_empty(self.request.GET.getlist('prefecture', []))
        id_communes = self.filter_list_by_delete_empty(self.request.GET.getlist('commune', []))
        id_cantons = self.filter_list_by_delete_empty(self.request.GET.getlist('canton', []))
        id_villages = self.filter_list_by_delete_empty(self.request.GET.getlist('village', []))
        include_all_projects_checked = self.request.GET.get('include_all_projects', 0) in (1, '1')

        all_projects = self.request.session.get('tree_structure_projects_ids') if include_all_projects_checked else [self.request.session.get('project_id')]
        
        geographical_units = GeographicalUnit.objects.filter(
            canton__administrative_levels_projects__in=all_projects
        )

        if (
            (id_regions and 'All' not in id_regions) or 
            (id_prefectures and 'All' not in id_prefectures) or 
            (id_communes and 'All' not in id_communes) or 
            (id_cantons and 'All' not in id_cantons) or 
            (id_villages and 'All' not in id_villages)
        ):
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
            
            geographical_units = geographical_units.filter(
                Q(administrativelevel__id__in=_ids) | 
                Q(administrativelevel__parent__id__in=_ids) | 
                Q(administrativelevel__parent__parent__id__in=_ids) | 
                Q(administrativelevel__parent__parent__parent__id__in=_ids) | 
                Q(administrativelevel__parent__parent__parent__parent__id__in=_ids)
            )
        
        if search and search != "All":
            search = search.upper()
            geographical_units = geographical_units.filter(
                Q(administrativelevel__name__icontains=search) | Q(administrativelevel__parent__name__icontains=search)
            )
                    
        geographical_units = geographical_units.distinct()

        if (
            id_regions or id_prefectures or id_communes or id_cantons or id_villages or search or include_all_projects_checked
        ):
            count = geographical_units.count()
            if count == 0:
                count = 1
        
        return Paginator(geographical_units, count).get_page(page_number)
    
    def get_context_data(self, **kwargs):
        ctx = super(GeographicalUnitListView, self).get_context_data(**kwargs)
        ctx.update(self.get_filters_context())

        # ctx['hide_content_header'] = True

        ctx['search'] = self.request.GET.get("search", None)
        ctx['type'] = self.request.GET.get("type", "Village")

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

        return ctx

class GeographicalUnitCreateView(PageMixin, LoginRequiredMixin, AdminPermissionRequiredMixin, CreateView):
    model = GeographicalUnit
    template_name = 'geographical_unit_create.html'
    context_object_name = 'geographicalunit'
    title = _('Create geographical unit')
    active_level1 = 'administrative_levels'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]
 
    form_class = GeographicalUnitForm # specify the class form to be displayed

    def post(self, request, *args, **kwargs):
        form = GeographicalUnitForm(request.POST)
        if form.is_valid():
            # cvds = form.cleaned_data['cvds']
            villages = form.cleaned_data['villages']
            
            unit = form.save(commit=False)
            # length_str = str(len(GeographicalUnit.objects.all())+1)
            try:
                length_str = str(GeographicalUnit.objects.all().last().pk + 1)
            except Exception as exc:
                length_str = "1"
            # import zlib
            # unit.unique_code = str(zlib.adler32(str(('0'*(9-len(length_str)))+length_str).encode('utf-8')))[:6]
            unit.unique_code = ('0'*(9-len(length_str))) + length_str
            unit = unit.save_and_return_object(user=self.request.user)

            for village_id in villages:
                try:
                    village = AdministrativeLevel.objects.get(id=int(village_id))
                    village.geographical_unit = unit
                    village.save(user=self.request.user)
                except Exception as exc:
                    pass
            
            #Record automatically CVD if unit has one village
            if villages and len(villages) == 1:
                try:
                    length_str_cvd = str(CVD.objects.all().last().pk + 1)
                    cvd = CVD()
                    cvd.name = "Record automatically"
                    cvd.geographical_unit = unit
                    cvd.unique_code = ('0'*(9-len(length_str_cvd))) + length_str_cvd
                    cvd = cvd.save_and_return_object(user=self.request.user)
                        
                    village = AdministrativeLevel.objects.get(id=int(villages[0]))
                    village.cvd = cvd
                    village.save(user=self.request.user)

                    cvd.name = village.name
                    cvd.headquarters_village = village
                    cvd.save(user=self.request.user)
                        

                except Exception as exc:
                    length_str_cvd = "1"
                

                

            return redirect('administrativelevels:geographical_units_list')
        return super(GeographicalUnitCreateView, self).get(request, *args, **kwargs)
    
class GeographicalUnitUpdateView(PageMixin, LoginRequiredMixin, AdminPermissionRequiredMixin, UpdateView):
    model = GeographicalUnit
    template_name = 'geographical_unit_create.html'
    context_object_name = 'geographicalunit'
    title = _('Update geographical unit')
    active_level1 = 'administrative_levels'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]
 
    form_class = GeographicalUnitForm # specify the class form to be displayed
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = GeographicalUnitForm(initial={
            "villages": [
                cat for cat in self.get_object().get_villages().values_list("id", flat=True)
            ]
        }, instance=self.get_object())

        # context['villages'] = self.get_object().geographical_unit.get_villages()

        return context
    def post(self, request, *args, **kwargs):
        form = GeographicalUnitForm(request.POST, instance=self.get_object())
        if form.is_valid():
            # cvds = form.cleaned_data['cvds']
            villages = form.cleaned_data['villages']
            
            unit = form.save(commit=False)
            unit = unit.save_and_return_object()
            unit.administrativelevel_set.clear()
            unit = unit.save_and_return_object(user=self.request.user)

            for village_id in villages:
                try:
                    village = AdministrativeLevel.objects.get(id=int(village_id))
                    village.geographical_unit = unit
                    village.save(user=self.request.user)
                except Exception as exc:
                    pass

            # for cvd_id in cvds:
            #     try:
            #         cvd = CVD.objects.get(id=int(cvd_id))
            #         cvd.geographical_unit = unit
            #         cvd.save()
            #     except Exception as exc:
            #         pass

            return redirect('administrativelevels:geographical_units_list')
        return super(GeographicalUnitUpdateView, self).get(request, *args, **kwargs)

class GeographicalUnitDetailView(PageMixin, LoginRequiredMixin, DetailView):
    """Class to present the detail page of one geographical unit"""
    model = GeographicalUnit
    template_name = 'geographical_unit_detail.html'
    context_object_name = 'geographicalunit'
    title = _('Geographical unit')
    active_level1 = 'administrative_levels'
    breadcrumb = [
        {
            'url': reverse_lazy('administrativelevels:geographical_units_list'),
            'title': _('Geographical units')
        },
        {
            'url': '',
            'title': title
        },
    ]
    



#======================================CVD==============================================

class CVDListView(PageMixin, LoginRequiredMixin, ListView):
    """Display geographical unit list"""

    model = CVD
    queryset = [] #CVD.objects.filter()
    template_name = 'cvds_list.html'
    context_object_name = 'cvds'
    title = _('CVD')
    active_level1 = 'administrative_levels'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]

    def filter_list_by_delete_empty(self, _list):
        if _list:
            return [elt for elt in _list if elt]
        else:
            return []
        
    def get_filters_context(self):
        kwargs = dict()

        kwargs["all_projects"] = self.request.session.get('tree_structure_projects_ids') if self.request.GET.get('include_all_projects', 0) in (1, '1') else []

        id_regions = self.filter_list_by_delete_empty(self.request.GET.getlist('region', []))
        id_prefectures = self.filter_list_by_delete_empty(self.request.GET.getlist('prefecture', []))
        id_communes = self.filter_list_by_delete_empty(self.request.GET.getlist('commune', []))
        id_cantons = self.filter_list_by_delete_empty(self.request.GET.getlist('canton', []))
        id_villages = self.filter_list_by_delete_empty(self.request.GET.getlist('village', []))

        kwargs["id_regions_selected"] = id_regions
        kwargs["id_prefectures_selected"] = id_prefectures
        kwargs["id_communes_selected"] = id_communes
        kwargs["id_cantons_selected"] = id_cantons
        kwargs["id_villages_selected"] = id_villages
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

    # def get_queryset(self):
    #     return super().get_queryset()
    def get_queryset(self):
        count = 100
        search = self.request.GET.get("search", None)
        page_number = self.request.GET.get("page", None)        
        id_regions = self.filter_list_by_delete_empty(self.request.GET.getlist('region', []))
        id_prefectures = self.filter_list_by_delete_empty(self.request.GET.getlist('prefecture', []))
        id_communes = self.filter_list_by_delete_empty(self.request.GET.getlist('commune', []))
        id_cantons = self.filter_list_by_delete_empty(self.request.GET.getlist('canton', []))
        id_villages = self.filter_list_by_delete_empty(self.request.GET.getlist('village', []))
        include_all_projects_checked = self.request.GET.get('include_all_projects', 0) in (1, '1')

        all_projects = self.request.session.get('tree_structure_projects_ids') if include_all_projects_checked else [self.request.session.get('project_id')]
        
        cvds = CVD.objects.filter(
            headquarters_village__administrative_levels_projects__in=all_projects
        )

        if (
            (id_regions and 'All' not in id_regions) or 
            (id_prefectures and 'All' not in id_prefectures) or 
            (id_communes and 'All' not in id_communes) or 
            (id_cantons and 'All' not in id_cantons) or 
            (id_villages and 'All' not in id_villages)
        ):
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
            
            cvds = cvds.filter(
                Q(headquarters_village__id__in=_ids) | 
                Q(headquarters_village__parent__id__in=_ids) | 
                Q(headquarters_village__parent__parent__id__in=_ids) | 
                Q(headquarters_village__parent__parent__parent__id__in=_ids) | 
                Q(headquarters_village__parent__parent__parent__parent__id__in=_ids)
            )
        
        if search and search != "All":
            search = search.upper()
            cvds = cvds.filter(
                Q(name__icontains=search) | Q(headquarters_village__parent__name__icontains=search)
            )
        
        cvds = cvds.distinct()

        if (
            id_regions or id_prefectures or id_communes or id_cantons or id_villages or search or include_all_projects_checked
        ):
            count = cvds.count()
            if count == 0:
                count = 1
        
        return Paginator(cvds, count).get_page(page_number)
    

    def get_context_data(self, **kwargs):
        ctx = super(CVDListView, self).get_context_data(**kwargs)
        ctx.update(self.get_filters_context())

        # ctx['hide_content_header'] = True

        ctx['search'] = self.request.GET.get("search", None)
        ctx['type'] = self.request.GET.get("type", "Village")

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

        return ctx


class CVDCreateView(PageMixin, LoginRequiredMixin, AdminPermissionRequiredMixin, CreateView):
    model = CVD
    template_name = 'cvd_create.html'
    context_object_name = 'cvd'
    title = _('Create CVD')
    active_level1 = 'administrative_levels'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]
 
    form_class = CVDForm # specify the class form to be displayed
    
    def post(self, request, *args, **kwargs):
        form = CVDForm(request.POST)
        if form.is_valid():
            villages = form.cleaned_data['villages']

            cvd = form.save(commit=False)
            # length_str = str(len(CVD.objects.all())+1)
            try:
                length_str = str(CVD.objects.all().last().pk + 1)
            except Exception as exc:
                length_str = "1"
            cvd.unique_code = ('0'*(9-len(length_str))) + length_str
            cvd = cvd.save_and_return_object(user=self.request.user)

            for village_id in villages:
                try:
                    village = AdministrativeLevel.objects.get(id=int(village_id))
                    village.cvd = cvd
                    village.save(user=self.request.user)
                except Exception as exc:
                    pass

            return redirect('administrativelevels:cvds_list')
        return super(CVDCreateView, self).get(request, *args, **kwargs)


class CVDUpdateView(PageMixin, LoginRequiredMixin, AccountantPermissionRequiredMixin, UpdateView):
    model = CVD
    template_name = 'cvd_create.html'
    context_object_name = 'cvd'
    title = _('Update CVD')
    active_level1 = 'administrative_levels'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]
 
    form_class = CVDForm # specify the class form to be displayed
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = CVDForm(initial={
            "villages": [
                cat for cat in self.get_object().get_villages().values_list("id", flat=True)
            ]
        }, instance=self.get_object())

        # context['villages'] = self.get_object().geographical_unit.get_villages()

        return context
    
    def post(self, request, *args, **kwargs):
        form = CVDForm(request.POST, instance=self.get_object())
        if form.is_valid():
            villages = form.cleaned_data['villages']

            cvd = form.save(commit=False)
            cvd = cvd.save_and_return_object()
            cvd.administrativelevel_set.clear()
            cvd = cvd.save_and_return_object(user=self.request.user)

            for village_id in villages:
                try:
                    village = AdministrativeLevel.objects.get(id=int(village_id))
                    village.cvd = cvd
                    village.save(user=self.request.user)
                except Exception as exc:
                    pass

            return redirect('administrativelevels:cvds_list')
        return super(CVDUpdateView, self).get(request, *args, **kwargs)
    
class CVDDetailView(PageMixin, LoginRequiredMixin, DetailView):
    """Class to present the detail page of one CVD"""
    model = CVD
    template_name = 'cvd_detail.html'
    context_object_name = 'cvd'
    title = _('CVD')
    active_level1 = 'administrative_levels'
    breadcrumb = [
        {
            'url': reverse_lazy('administrativelevels:cvds_list'),
            'title': _('CVD')
        },
        {
            'url': '',
            'title': title
        },
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['list_subprojects_kit'] = context['object'].get_list_subprojects_kit()
        context['list_subprojects'] = context['object'].get_list_subprojects()

        allocations_project = AdministrativeLevelAllocation.objects.filter(
            project_id=self.request.session.get('project_id'), 
            cvd_id=context['object'].id, 
            administrative_level=None
        )

        # Définir les composants de financement
        components_mapping = { _('Component 1.1'): 2, _('Component 1.2'): 3, _('Component 1.3'): 6 }
        financing_components = {}
        context['pie_graphes'] = []
        for component_label, component_id in components_mapping.items():
            comp_qs = context['list_subprojects'].filter(component_id=component_id)

            # Agrégation des montants en une seule passe
            agg = comp_qs.aggregate(
                estimated_cost=Sum('estimated_cost'),
                contract_amount=Sum('contract_amount_work_companies')
            )
            total_estimated = agg['estimated_cost'] or 0
            total_contract = agg['contract_amount'] or 0

            total_allocations = allocations_project.filter(component_id=component_id).aggregate(Sum('amount'))['amount__sum'] or 0

            financing_components[component_label] = {
                'total_amount_subprojects_estimated_cost': total_estimated,
                'total_amount_subprojects_contract_amount_work_companies': total_contract,
                'total_allocations_cantons': total_allocations,
                'total_amount_remaining_after_allocation': total_allocations - total_estimated,
                'total_amount_residual': total_allocations - total_contract
            }

            # Graphique pour chaque composant
            context['pie_graphes'].append({
                'type': _("Wording"),
                'type_value_label': _("Amount"),
                'title': _("Amount of infrastructures by status") + f" {component_label}",
                'labels': [_("Residual"), _("Spent")],
                'data': [financing_components[component_label]['total_amount_residual'], total_contract],
                'sorted': 0
            })

        context['financing_components'] = financing_components

        # Totaux globaux
        agg_total = context['list_subprojects'].aggregate(
            total_estimated_cost=Sum('estimated_cost'),
            total_contract_amount=Sum('contract_amount_work_companies')
        )
        total_estimated = agg_total['total_estimated_cost'] or 0
        total_contract = agg_total['total_contract_amount'] or 0
        total_allocations = allocations_project.aggregate(Sum('amount'))['amount__sum'] or 0

        context.update({
            'total_amount_subprojects_estimated_cost': total_estimated,
            'total_amount_subprojects_contract_amount_work_companies': total_contract,
            'total_allocations_cantons': total_allocations,
            'total_amount_remaining_after_allocation': total_allocations - total_estimated,
            'total_amount_residual': total_allocations - total_contract
        })

        return context


class DownloadCVDCSVView(PageMixin, LoginRequiredMixin, TemplateView):
    """Class to download CVD under excel file"""

    template_name = 'components/download.html'
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
        administrative_level_ids_get = self.request.POST.getlist('value_of_type', None)
        administrative_level_type = self.request.POST.get('type', 'All').title()
        
        administrative_level_type = "All" if administrative_level_type in ("", "null", "undefined") else administrative_level_type
        
        ald_filter_ids = []
        administrative_levels_ids = []
        if not administrative_level_ids_get:
            administrative_level_ids_get.append("")
        for ald_id in administrative_level_ids_get:
            ald_id = 0 if ald_id in ("", "null", "undefined", "All") else ald_id
            administrative_levels_ids += get_administrative_level_ids_descendants(
                ald_id, None, [], self.request.session.get('project_id')
            )
            if ald_id:
                ald_filter_ids.append(int(ald_id))
                
        administrative_levels_ids = list(set(administrative_levels_ids))

        try:
            file_path = cvd_functions.get_cvd_under_file_excel_or_csv(
                request.POST.get("file_type"), administrative_levels_ids
            )

        except Exception as exc:
            messages.info(request, _("An error has occurred..."))

        if not file_path:
            return redirect('administrativelevels:list')
        else:
            return download_file.download(
                request, 
                file_path,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    