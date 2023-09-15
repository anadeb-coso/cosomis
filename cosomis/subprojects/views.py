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
from subprojects.models import Subproject, VulnerableGroup, SubprojectImage
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q
from django.core.exceptions import PermissionDenied

from django import forms
from subprojects import functions as subprojects_functions
from administrativelevels.libraries import download_file
from usermanager.permissions import (
    CDDSpecialistPermissionRequiredMixin, SuperAdminPermissionRequiredMixin,
    AdminPermissionRequiredMixin, InfraPermissionRequiredMixin
    )
from cosomis.constants import SUB_PROJECT_STATUS_COLOR_TRANSLATE


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

class SubprojectsMapView(LoginRequiredMixin, generic.ListView):

    model = Subproject
    queryset = Subproject.objects.all()
    template_name = 'subprojects_map.html'
    context_object_name = 'subprojects'
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


class SubprojectCreateView(PageMixin, LoginRequiredMixin, InfraPermissionRequiredMixin, generic.CreateView):
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
    
class SubSubprojectCreateView(PageMixin, LoginRequiredMixin, InfraPermissionRequiredMixin, generic.CreateView):
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
def subprojectimage_delete(request, image_id):
    """Function to delete one subprojectImage"""
    try:
        img = SubprojectImage.objects.get(id=image_id)
        subproject = img.subproject
        if img.principal:
            for image in subproject.get_all_images():
                if image.id != image_id:
                    image.principal = True
                    image.save()
                    break

        img.delete()
        
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
    