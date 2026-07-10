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
from subprojects.api.functions import convert_str_percent_to_float
from cosomis.constants import (
    STRUCTURE_IN_PROGRESS_STATUS, STRUCTURE_NOT_START_STATUS,
    INTERRUPTED_RANKING, ABANDONED_RANKING, ANOTHER_SITE_HANDED_OVER_FOR_CONSTRUCTION_RANKING,
    SELECTED_COMPANY_RANKING, FIRST_CONTRACT_RANKING, OTHERS_CONTRACT_RANKING, CONTRACT_TERMINATED_RANKING,
    DAO_RELAUNCHED_RANKING, SITE_DISCOUNT_RANKING, STRUCTURE_IN_PROGRESS_RANKING_LIST,
    IN_PROGRESS_RANKING, APPROVED_BY_CORA_RANKING, NOT_APPROVED_BY_CORA_RANKING, COMPLETED_RANKING,
    RECEPTION_TECHNICAL_RANKING, PROVISIONAL_RECEPTION_RANKING, HANDOVER_TO_COMMUNITY_RANKING, 
    FINAL_RECEPTION_RANKING
)


class SubprojectFormMixin(SubprojectMixin, generic.FormView):

    def get_form_kwargs(self):
        self.initial = {'subproject_id': self.subproject.id}
        return super().get_form_kwargs()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.kwargs.get('subproject_step_update_id'):
            obj = SubprojectStep.objects.get(id=self.kwargs['subproject_step_update_id'])
            context['form'] = SubprojectAddStepForm(instance=obj, initial= {'subproject': self.subproject})
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
                    'percent' : step.percent if step.percent else 0,
                    'created_date': step.created_date.__str__() if step.created_date else '',
                    'ranking': step.ranking if hasattr(step, 'ranking') else ''
                })
            elif step.begin:
                dates_wording_with_percents.append({
                    'date': step.begin.__str__(),
                    'wording' : step.wording,
                    'percent' : step.percent if step.percent else 0,
                    'created_date': step.created_date.__str__() if step.created_date else '',
                    'ranking': step.ranking if hasattr(step, 'ranking') else ''
                })

            # Mange if step is "Interrompu, Abandon or Autre site remis pour la construction"
            if (
                (
                    (
                    (step.begin and step.end) or step.end
                    ) or (
                        step.begin
                    )
                ) and (
                    step.ranking in (
                        SELECTED_COMPANY_RANKING, FIRST_CONTRACT_RANKING, OTHERS_CONTRACT_RANKING, CONTRACT_TERMINATED_RANKING,
                        DAO_RELAUNCHED_RANKING, SITE_DISCOUNT_RANKING, ANOTHER_SITE_HANDED_OVER_FOR_CONSTRUCTION_RANKING, 
                        INTERRUPTED_RANKING, ABANDONED_RANKING
                    )
                )
            ):
                # we are looking for the nearest step/level with a percentage
                if hasattr(step, 'subproject'):
                    nearest_step_or_level = step.subproject.get_nearest_step_or_level_with_percent_from_step(step)
                else:
                    nearest_step_or_level = step.subproject_step.subproject.get_nearest_step_or_level_with_percent_from_step(step)

                if nearest_step_or_level and nearest_step_or_level.percent:
                    dates_wording_with_percents[-1]['percent'] = nearest_step_or_level.percent
            
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
        dates_wording_with_percents = sorted(dates_wording_with_percents, key=lambda obj: f"{obj.get('date')} {obj.get('created_date')} {obj.get('percent')}")
        
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
    _obj = None

    def check_permissions(self):
        super().check_permissions()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.kwargs.get('subproject_step_update_id'):
            context['form'] = SubprojectAddStepForm(initial={'subproject': self.subproject})

        return context

    def post(self, request, *args, **kwargs):
        form = None
        obj = None
        msg = ''
        if self.kwargs.get('subproject_step_update_id'):
            obj = SubprojectStep.objects.get(id=self.kwargs['subproject_step_update_id'])
            form = SubprojectAddStepForm(request.POST, instance=obj, initial= {'subproject': self.subproject})
        else:
            form = SubprojectAddStepForm(request.POST, initial= {'subproject': self.subproject})
        self._obj = obj
        if form and form.is_valid():
            data = form.cleaned_data
            # ranking = None
            # if obj:
            #     ranking = obj.ranking
            # else:
            #     current_subproject_step = self.subproject.get_current_subproject_step
            #     if current_subproject_step and current_subproject_step.ranking:
            #         ranking = current_subproject_step.ranking
            #         if ranking:
            #             if current_subproject_step.wording in STRUCTURE_NOT_START_STATUS and data['step'].ranking == APPROVED_BY_CORA_RANKING:
            #                 ranking = NOT_APPROVED_BY_CORA_RANKING
            #             elif (current_subproject_step.wording in STRUCTURE_IN_PROGRESS_STATUS or (current_subproject_step.ranking in STRUCTURE_IN_PROGRESS_RANKING_LIST)) and data['step'].ranking == INTERRUPTED_RANKING:
            #                 ranking = ABANDONED_RANKING
            #             elif (current_subproject_step.wording in STRUCTURE_IN_PROGRESS_STATUS or (current_subproject_step.ranking in STRUCTURE_IN_PROGRESS_RANKING_LIST)) and data['step'].ranking == COMPLETED_RANKING:
            #                 ranking = INTERRUPTED_RANKING
            #             # elif current_subproject_step.wording == "Interrompu":
            #             #     ranking = IN_PROGRESS_RANKING
                                
            #         ranking = ranking + 1
                    
            # if (data.get('step') and ranking and data['step'].ranking != ranking) or (not ranking and data['step'].ranking != IDENTIFIED_RANKING):
            #     msg = _("You must follow each step...")
            # else:

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
        subproject_step = subproject_step.save_and_return_object(user=self.request.user)

        # if not self._obj:
        _subproject_step = self.subproject.get_current_subproject_step
        if _subproject_step:
            if _subproject_step.step.ranking < IN_PROGRESS_RANKING and _subproject_step.step.ranking != NOT_APPROVED_BY_CORA_RANKING:
                self.subproject.current_status_of_the_site = "Identifié"
            elif _subproject_step.step.ranking == ABANDONED_RANKING:
                self.subproject.current_status_of_the_site = "Abandon"
            elif _subproject_step.step.ranking == INTERRUPTED_RANKING:
                self.subproject.current_status_of_the_site = "Arrêt"
            elif _subproject_step.step.ranking == HANDOVER_TO_COMMUNITY_RANKING:
                self.subproject.current_status_of_the_site = "Réception provisoire"
            else:
                self.subproject.current_status_of_the_site = _subproject_step.step.wording

            if subproject_step.step.ranking == APPROVED_BY_CORA_RANKING:
                self.subproject.approval_date_cora = subproject_step.begin
            elif subproject_step.step.ranking in (FIRST_CONTRACT_RANKING, OTHERS_CONTRACT_RANKING): # contract_signed
                self.subproject.date_signature_contract_work_companies = subproject_step.begin
            # elif subproject_step.step.ranking == IN_PROGRESS_RANKING: # progress
            #     self.subproject.launch_date_of_the_construction_site_in_the_village = subproject_step.begin
            elif subproject_step.step.ranking == COMPLETED_RANKING: # completed
                self.subproject.work_completion_date = subproject_step.begin
            elif subproject_step.step.ranking == RECEPTION_TECHNICAL_RANKING: # technical_acceptance
                self.subproject.date_of_technical_acceptance_of_work_contracts = subproject_step.begin
            elif subproject_step.step.ranking == PROVISIONAL_RECEPTION_RANKING: # provisional_acceptance
                self.subproject.date_of_provisional_acceptance_of_work_contracts = subproject_step.begin
            elif subproject_step.step.ranking == HANDOVER_TO_COMMUNITY_RANKING: # handover_to_the_community
                self.subproject.official_handover_date_of_the_microproject_to_the_community = subproject_step.begin
            elif subproject_step.step.ranking == FINAL_RECEPTION_RANKING: # final_acceptance
                self.subproject.date_of_final_acceptance_of_the_work = subproject_step.begin
            
            if _subproject_step.step.percent:
                self.subproject.current_level_of_physical_realization_of_the_work = str(_subproject_step.step.percent)
                self.subproject.current_level_of_physical_realization_of_the_work_percent = _subproject_step.step.percent
            else:
                self.subproject.current_level_of_physical_realization_of_the_work = _subproject_step.step.wording
                self.subproject.current_level_of_physical_realization_of_the_work_percent = 0.0
            self.subproject.current_level_of_physical_realization_of_the_work_wording = self.subproject.get_current_subproject_step_and_level_without_percent

            self.subproject.save(user=self.request.user)

        images = subproject_step.subproject.get_all_images()
        for file in [self.request.FILES.get('level_image'), self.request.FILES.get('level_other_file')]:
            if file:
                file_directory_within_bucket = 'proof_of_work/'
                file_path_within_bucket = os.path.join(
                    file_directory_within_bucket,
                    f'{str(time.time())}-{file.name}'
                )
                media_storage = S3Boto3Storage()
                # if not media_storage.exists(file_path_within_bucket):  # avoid overwriting existing file
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
                image.save(user=self.request.user)


        
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
    _obj = None
    

    def check_permissions(self):
        super().check_permissions()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.kwargs.get('subproject_level_update_id'):
            context['form'] = SubprojectAddLevelForm(initial={'subproject': self.subproject})

        return context

    def post(self, request, *args, **kwargs):
        form = None
        obj = None
        if self.kwargs.get('subproject_level_update_id'):
            obj = Level.objects.get(id=self.kwargs['subproject_level_update_id'])
            form = SubprojectAddLevelForm(request.POST, instance=obj)
        else:
            form = SubprojectAddLevelForm(request.POST)
        self._obj = obj
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
        subproject_level = subproject_level.save_and_return_object(user=self.request.user)

        # if not self._obj:
        _step = self.subproject.get_current_subproject_step
        if _step and (_step.wording in STRUCTURE_IN_PROGRESS_STATUS or (_step.ranking in STRUCTURE_IN_PROGRESS_RANKING_LIST)):
            
            old_percent = convert_str_percent_to_float(self.subproject.current_level_of_physical_realization_of_the_work)
            new_percent = convert_str_percent_to_float(subproject_level.percent)
            
            if old_percent < new_percent:
                self.subproject.current_status_of_the_site = "En cours"
                
                if subproject_level.percent:
                    self.subproject.current_level_of_physical_realization_of_the_work = str(subproject_level.percent)
                    self.subproject.current_level_of_physical_realization_of_the_work_percent = subproject_level.percent
                else:
                    self.subproject.current_level_of_physical_realization_of_the_work = "0"
                    self.subproject.current_level_of_physical_realization_of_the_work_percent = 0.0
                self.subproject.current_level_of_physical_realization_of_the_work_wording = self.subproject.get_current_subproject_step_and_level_without_percent

                self.subproject.save(user=self.request.user)

        images = subproject_level.subproject_step.subproject.get_all_images()
        for file in [self.request.FILES.get('level_image'), self.request.FILES.get('level_other_file')]:
            if file:
                file_directory_within_bucket = 'proof_of_work/'
                file_path_within_bucket = os.path.join(
                    file_directory_within_bucket,
                    f'{str(time.time())}-{file.name}'
                )
                media_storage = S3Boto3Storage()
                # if not media_storage.exists(file_path_within_bucket):  # avoid overwriting existing file
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
                image.save(user=self.request.user)


        
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