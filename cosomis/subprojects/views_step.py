from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
# from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import generic
from django.http import Http404
from datetime import timedelta, date
from itertools import zip_longest
import json
from django.forms.models import model_to_dict
from storages.backends.s3boto3 import S3Boto3Storage
import os
import time

from cosomis.mixins import AJAXRequestMixin, JSONResponseMixin, ModalFormMixin
from subprojects.views import SubprojectMixin
from subprojects.forms import SubprojectAddStepForm, SubprojectAddLevelForm #, DeleteConfirmForm
from subprojects.models import SubprojectStep, Level, SubprojectFile
from usermanager.permissions import (
    InfraPermissionRequiredMixin, 
)

class SubprojectFormMixin(SubprojectMixin, generic.FormView):

    def get_form_kwargs(self):
        self.initial = {'subproject_id': self.subproject.id}
        return super().get_form_kwargs()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.kwargs.get('subproject_step_update_id'):
            obj = SubprojectStep.objects.get(id=self.kwargs['subproject_step_update_id'])
            context['form'] = SubprojectAddStepForm(instance=obj)
        elif self.kwargs.get('subproject_level_update_id'):
            obj = Level.objects.get(id=self.kwargs['subproject_level_update_id'])
            context['form'] = SubprojectAddLevelForm(instance=obj)
        return context


class SubprojectStepGraphTemplateView(SubprojectMixin, AJAXRequestMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = 'components/subproject_tracking_graph.html'

    def get_oldest_latest_and_percent(self, objects):
        dates_wording_with_percents = []
        oldest, latest = {}, {}
        for step in objects:
            if hasattr(step, 'step') and hasattr(step.step, 'has_levels') and step.step.has_levels:
                continue

            if (step.begin and step.end) or step.end:
                dates_wording_with_percents.append({
                    'date': step.end.__str__(),
                    'wording' : step.wording,
                    'percent' : step.percent if step.percent else 0
                })
            elif step.begin:
                dates_wording_with_percents.append({
                    'date': step.begin.__str__(),
                    'wording' : step.wording,
                    'percent' : step.percent if step.percent else 0
                })
            
            if step.begin and ((not oldest) or (oldest and list(oldest.keys())[0] > step.begin)):
                oldest = {step.begin: step.wording}
            if step.end and ((not oldest) or (oldest and list(oldest.keys())[0] > step.end)):
                oldest = {step.end: step.wording}

            if step.begin and ((not latest) or (latest and list(latest.keys())[0] < step.begin)):
                latest = {step.begin: step.wording}
            if step.end and ((not latest) or (latest and list(latest.keys())[0] < step.end)):
                latest = {step.end: step.wording}
        return oldest, latest, dates_wording_with_percents
    
    def daterange(self, start_date, end_date, step):
        for n in range(0, int ((end_date - start_date).days), step):
            yield (start_date + timedelta(n))
    
    def get_element_str(self, objects):
        return [o.__str__() for o in objects]

    # def grouper(self, iterable, n, fillvalue=None):
    #     "Collect data into fixed-length chunks or blocks"
    #     # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    #     args = [iter(iterable)] * n
    #     return zip_longest(*args, fillvalue=fillvalue)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subproject_steps'] = self.subproject.get_subproject_steps()

        subproject_levels = []
        for elt in context['subproject_steps']:
            subproject_levels += list(elt.get_levels())

        dates_wording_with_percents, dates_with_wording, percents = [], [], []
        oldest_step, latest_step, dates_wording_with_percents_step = self.get_oldest_latest_and_percent(context['subproject_steps'])
        oldest_level, latest_level, dates_wording_with_percents_level = self.get_oldest_latest_and_percent(subproject_levels)
        
        dates_wording_with_percents += dates_wording_with_percents_step
        dates_wording_with_percents += dates_wording_with_percents_level
        dates_wording_with_percents = sorted(dates_wording_with_percents, key=lambda obj: f"{obj.get('date')} {obj.get('percent')}")
        
        for elt in dates_wording_with_percents:
            dates_with_wording.append(f"{elt.get('date')} {elt.get('wording')}")
            percents.append(elt.get('percent'))

        if dates_with_wording and len(dates_with_wording) > 1 and percents and percents[-1] != 100:
            percents.append(100)

        context['x_axes_values'] = json.dumps(dates_with_wording)
        context['y_axes_values'] = json.dumps(percents)
        return context
    
class SubprojectStepAddTemplateView(SubprojectMixin, AJAXRequestMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = 'components/subproject_tracking_add.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subproject_steps'] = self.subproject.get_subproject_steps()
        return context
    
#Add
class SubprojectStepAddFormView(AJAXRequestMixin, ModalFormMixin, LoginRequiredMixin, 
                                InfraPermissionRequiredMixin, JSONResponseMixin, SubprojectFormMixin):
    model = SubprojectStep
    form_class = SubprojectAddStepForm
    id_form = "subproject_add_step_form"
    title = _('Record a step')
    submit_button = _('Save')
    # permissions = ('read',)

    def check_permissions(self):
        super().check_permissions()

    def post(self, request, *args, **kwargs):
        form = None
        obj = None
        msg = ''
        if self.kwargs.get('subproject_step_update_id'):
            obj = SubprojectStep.objects.get(id=self.kwargs['subproject_step_update_id'])
            form = SubprojectAddStepForm(request.POST, instance=obj)
        else:
            form = SubprojectAddStepForm(request.POST)

        if form and form.is_valid():
            data = form.cleaned_data
            ranking = None
            if obj:
                ranking = obj.ranking
            else:
                current_subproject_step = self.subproject.get_current_subproject_step
                if current_subproject_step and current_subproject_step.ranking:
                    ranking = current_subproject_step.ranking
                    if ranking:
                        if current_subproject_step.wording == "Identifié" and data['step'].ranking == 3:
                            ranking = 2
                        elif current_subproject_step.wording == "En cours" and data['step'].ranking == 10:
                            ranking = 9
                        elif current_subproject_step.wording == "En cours" and data['step'].ranking == 11:
                            ranking = 10
                        elif current_subproject_step.wording == "Interrompu":
                            ranking = 8
                                
                    ranking = ranking + 1
            print(data['step'].ranking, ranking)
            if (data.get('step') and ranking and data['step'].ranking != ranking) or (not ranking and data['step'].ranking != 1):
                msg = _("You must follow each step...")
            else:
                return self.form_valid(form)
        else:
            msg = _("An error has occurred...")
        messages.add_message(self.request, messages.ERROR, msg, extra_tags='error')

        context = {'msg': render(self.request, 'common/messages.html').content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)
    
    def form_valid(self, form):
        # data = form.cleaned_data
        
        subproject_step = form.save(commit=False)
        subproject_step.subproject = self.subproject
        subproject_step.wording = subproject_step.step.wording
        subproject_step.percent = subproject_step.step.percent
        subproject_step.ranking = subproject_step.step.ranking
        subproject_step = subproject_step.save_and_return_object()

        images = subproject_step.subproject.get_all_images()
        for file in [self.request.FILES.get('level_image'), self.request.FILES.get('level_other_file')]:
            if file:
                file_directory_within_bucket = 'proof_of_work/'
                file_path_within_bucket = os.path.join(
                    file_directory_within_bucket,
                    f'{str(time.time())}-{file.name}'
                )
                media_storage = S3Boto3Storage()
                if not media_storage.exists(file_path_within_bucket):  # avoid overwriting existing file
                    media_storage.save(file_path_within_bucket,file)
                    file_url = media_storage.url(file_path_within_bucket)

                    principal = False
                    if len(images) == 0:
                        principal = True

                    image = SubprojectFile.objects.filter(
                        subproject_step_id=subproject_step.id, file_type=file.content_type
                    ).first()
                    if not image:
                        image = SubprojectFile()
                        image.order = len(images) + 1
                        image.subproject = subproject_step.subproject
                        image.subproject_step = subproject_step
                        image.file_type = file.content_type

                    image.url = file_url
                    image.principal = principal
                    image.date_taken = subproject_step.begin
                    image.name = subproject_step.wording
                    image.save()


        
        msg = _("The Step was successfully saved.")
        messages.add_message(self.request, messages.SUCCESS, msg, extra_tags='success')

        context = {'msg': render(self.request, 'common/messages.html').content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)

class SubprojectLevelAddFormView(AJAXRequestMixin, ModalFormMixin, LoginRequiredMixin, InfraPermissionRequiredMixin, 
                                 JSONResponseMixin, SubprojectFormMixin):
    model = Level
    form_class = SubprojectAddLevelForm
    id_form = "subproject_add_level_form"
    title = _('Record an evolution level')
    submit_button = _('Save')
    

    def check_permissions(self):
        super().check_permissions()

    def post(self, request, *args, **kwargs):
        form = None
        if self.kwargs.get('subproject_level_update_id'):
            obj = Level.objects.get(id=self.kwargs['subproject_level_update_id'])
            form = SubprojectAddLevelForm(request.POST, instance=obj)
        else:
            form = SubprojectAddLevelForm(request.POST)

        if form and form.is_valid():
            return self.form_valid(form)
        
        msg = _("An error has occurred...")
        messages.add_message(self.request, messages.ERROR, msg, extra_tags='error')

        context = {'msg': render(self.request, 'common/messages.html').content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)

    def form_valid(self, form):
        subproject_step = None
        try:
            subproject_step = SubprojectStep.objects.get(id=self.kwargs['subproject_step_id'])
        except:
            raise Http404
        
        subproject_level = form.save(commit=False)
        subproject_level.subproject_step = subproject_step
        subproject_level = subproject_level.save_and_return_object()


        images = subproject_level.subproject_step.subproject.get_all_images()
        for file in [self.request.FILES.get('level_image'), self.request.FILES.get('level_other_file')]:
            if file:
                file_directory_within_bucket = 'proof_of_work/'
                file_path_within_bucket = os.path.join(
                    file_directory_within_bucket,
                    f'{str(time.time())}-{file.name}'
                )
                media_storage = S3Boto3Storage()
                if not media_storage.exists(file_path_within_bucket):  # avoid overwriting existing file
                    media_storage.save(file_path_within_bucket,file)
                    file_url = media_storage.url(file_path_within_bucket)
                    
                    principal = False
                    if len(images) == 0:
                        principal = True

                    image = SubprojectFile.objects.filter(
                        subproject_level_id=subproject_level.id, file_type=file.content_type
                    ).first()
                    if not image:
                        image = SubprojectFile()
                        image.order = len(images) + 1
                        image.subproject = subproject_level.subproject_step.subproject
                        image.subproject_level = subproject_level
                        image.file_type = file.content_type
                    image.url = file_url
                    image.principal = principal
                    image.date_taken = subproject_level.begin
                    image.name = subproject_level.wording
                    image.save()


        
        msg = _("The Level was successfully saved.")
        messages.add_message(self.request, messages.SUCCESS, msg, extra_tags='success')

        context = {'msg': render(self.request, 'common/messages.html').content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)
#And Add


#Display Files
class FilesView(AJAXRequestMixin, ModalFormMixin, LoginRequiredMixin, InfraPermissionRequiredMixin, 
                                 JSONResponseMixin, generic.TemplateView):
    template_name = "components/subproject_tracking_files.html"
    id_form = "display_subproject_step_files_form"
    title = _('Attachments')
    

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.kwargs.get('subproject_step_id'):
            context['object'] = SubprojectStep.objects.get(id=self.kwargs['subproject_step_id'])
        elif self.kwargs.get('subproject_level_id'):
            context['object'] = Level.objects.get(id=self.kwargs['subproject_level_id'])
        else:
            raise Http404
        
        context['object_images'] = context['object'].get_images()
        context['object_exclude_images'] = context['object'].get_exclude_images()
        
        return context


#End Display Fils

# #Delete
# class SubprojectStepDeleteFormView(AJAXRequestMixin, ModalFormMixin, LoginRequiredMixin, JSONResponseMixin,
#                                       generic.FormView):
#     form_class = DeleteConfirmForm
#     id_form = "subproject_deletion_step_form"
#     title = _('Confirm deletion')
#     submit_button = _('Confirm')
#     form_class_color = 'danger'
#     # permissions = ('read',)

#     def check_permissions(self):
#         super().check_permissions()

#     def post(self, request, *args, **kwargs):
#         form = None
#         if self.kwargs.get('subproject_step_deletion_id'):
#             if self.kwargs.get('type') == "Step":
#                 obj = SubprojectStep.objects.get(id=self.kwargs['subproject_step_deletion_id'])
#             elif self.kwargs.get('type') == "Level":
#                 obj = Level.objects.get(id=self.kwargs['subproject_step_deletion_id'])
            
#             form = DeleteConfirmForm(request.POST)

#             if form and form.is_valid():
#                 return self._delete_object(obj)
        
#         msg = _("An error has occurred...")
#         messages.add_message(self.request, messages.ERROR, msg, extra_tags='error')

#         context = {'msg': render(self.request, 'common/messages.html').content.decode("utf-8")}
#         return self.render_to_json_response(context, safe=False)
    
#     def _delete_object(self, obj):
        
#         # obj.delete()
        
#         msg = _("The Step was successfully removed.")
#         messages.add_message(self.request, messages.SUCCESS, msg, extra_tags='success')

#         context = {'msg': render(self.request, 'common/messages.html').content.decode("utf-8")}
#         return self.render_to_json_response(context, safe=False)
# #And Delete