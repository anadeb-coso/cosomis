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
from .forms import SubprojectForm, VulnerableGroupForm
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q
from django.core.exceptions import PermissionDenied

from subprojects.models import Subproject, VulnerableGroup, SubprojectFile
from django import forms
from subprojects import functions as subprojects_functions
from administrativelevels.libraries import download_file
from usermanager.permissions import (
    CDDSpecialistPermissionRequiredMixin, SuperAdminPermissionRequiredMixin,
    AdminPermissionRequiredMixin, InfraPermissionRequiredMixin, EvaluatorPermissionRequiredMixin
    )
from cosomis.constants import SUB_PROJECT_STATUS_COLOR_TRANSLATE, TYPES_OF_SUB_PROJECT_COLOR
from administrativelevels.functions_adl import get_cascade_villages_ids_by_administrative_level_id
from dashboard.forms import AdministrativeLevelFilterForm
from subprojects.forms import SubprojectFilterForm

class SubprojectMixin:
    subproject = None
    permissions = ('read', 'write')
    has_permission = True

    def get_query_result(self, **kwargs):
        try:
            return Subproject.objects.get(id=kwargs['subproject_id'])
        except Exception as exc:
            print(exc)
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
    

class SubprojectsListView(PageMixin, LoginRequiredMixin, generic.ListView):
    model = Subproject
    queryset = [] #Subproject.objects.all()
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

    # def get_queryset(self):
    #     # return super().get_queryset()
    #     return Subproject.objects.filter(link_to_subproject=None)
    def get_queryset(self):
        search = self.request.GET.get("search", None)
        page_number = self.request.GET.get("page", None)
        if search:
            if search == "All":
                gs = Subproject.objects.filter(link_to_subproject=None)
                return Paginator(gs, gs.count()).get_page(page_number)
            search = search.upper()
            return Paginator(
                Subproject.objects.filter(
                    Q(link_to_subproject=None, full_title_of_approved_subproject__icontains=search) | 
                    Q(link_to_subproject=None, location_subproject_realized__name__icontains=search) | 
                    Q(link_to_subproject=None, subproject_sector__icontains=search) | 
                    Q(link_to_subproject=None, type_of_subproject__icontains=search) | 
                    Q(link_to_subproject=None, works_type__icontains=search) | 
                    Q(link_to_subproject=None, cvd__name__icontains=search) | 
                    Q(link_to_subproject=None, facilitator_name__icontains=search)
                ), 100).get_page(page_number)
        else:
            return Paginator(Subproject.objects.filter(link_to_subproject=None), 100).get_page(page_number)
        
    def get_context_data(self, **kwargs):
        ctx = super(SubprojectsListView, self).get_context_data(**kwargs)
        ctx['search'] = self.request.GET.get("search", None)
        all = Subproject.objects.all()
        ctx['total'] = all.count()
        ctx['total_without_link'] = all.filter(link_to_subproject=None, subproject_type_designation="Subproject").count()
        ctx['total_subproject'] = all.filter(subproject_type_designation="Subproject").count()
        ctx['total_infrastruture'] = all.filter(subproject_type_designation="Infrastructure").count()
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

    def get_results(self):
        id_regions = self.request.GET.getlist('id_region[]')
        id_prefectures = self.request.GET.getlist('id_prefecture[]')
        id_communes = self.request.GET.getlist('id_commune[]')
        id_cantons = self.request.GET.getlist('id_canton[]')
        id_villages = self.request.GET.getlist('id_village[]')
        subproject_sectors = self.request.GET.getlist('id_subproject_sectors[]')
        subproject_types = self.request.GET.getlist('id_subproject_types[]')
        works_type_of_subprojects = self.request.GET.getlist('id_works_type_of_subproject[]')
        subproject_steps = self.request.GET.getlist('id_subproject_step[]')
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

            subprojects = Subproject.objects.filter(
                Q(location_subproject_realized_id__in=liste_villages) | 
                Q(list_of_villages_crossed_by_the_track_or_electrification__id__in=liste_villages)
            )
        else:
            subprojects = Subproject.objects.all()
        
        if subproject_sectors:
            subprojects = subprojects.filter(subproject_sector__in=[elt for elt in subproject_sectors if elt])
        
        if subproject_types:
            subprojects = subprojects.filter(type_of_subproject__in=[elt for elt in subproject_types if elt])
            
        if works_type_of_subprojects:
            subprojects = subprojects.filter(works_type__in=[elt for elt in works_type_of_subprojects if elt])
        
        if subproject_steps:
            _subprojects = []
            for subproject in subprojects:
                subproject_step = subproject.get_current_subproject_step
                if subproject_step:
                    if 'not_started' in subproject_steps and subproject_step.ranking < 8 and subproject_step.ranking not in (2,):
                        _subprojects.append(subproject)
                    if 'in_progress' in subproject_steps and subproject_step.ranking == 8:
                        _subprojects.append(subproject)
                    if 'completed' in subproject_steps and subproject_step.ranking > 8 and subproject_step.ranking not in (9, 10):
                        _subprojects.append(subproject)
            subprojects = _subprojects
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
        context = super().get_context_data(**kwargs)
        context['preview_page'] = reverse_lazy('subprojects:list')
        context['object_tile'] = _('Subproject Detail').__str__()
        return context


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
            subproject.save()
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
            context['title'] = _('Update the infrastructure')
        elif _object.link_to_subproject and _object.subproject_type_designation == "Subproject":
            context['title'] = _('Update the subproject')

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
            subproject.save()
            return redirect('subprojects:detail', pk=subproject.id)
        self.form_mixin = form
        return super(SubprojectCreateView, self).get(request, *args, **kwargs)
    
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
            subproject.save()
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
            vulnerable_group.save()
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
                    image.save()
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
        try:
            file_path = subprojects_functions.get_subprojects_under_file_excel_or_csv(
                file_type=request.POST.get("file_type"),
                params={"type":request.POST.get("type"), "value_of_type":request.POST.get("value_of_type"),
                        "sector":request.POST.get("sector"), "subproject_type":request.POST.get("subproject_type")}
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
    