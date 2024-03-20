from django.http import HttpResponseRedirect
from django.conf import settings
from django.utils.translation import get_language

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import generic
from django.http import Http404
from django.apps import apps

from cosomis.mixins import AJAXRequestMixin, JSONResponseMixin, ModalFormMixin
from cosomis.forms import DeleteConfirmForm
from usermanager.permissions import AdminPermissionRequiredMixin
from subprojects.models import SubprojectStep


def set_language(request):
    response = HttpResponseRedirect('/')
    if request.method == 'POST':
        try:
            language = request.POST.get('language')
            next = request.POST.get('next')
            next_url_generate = False
            language_code = get_language()
            
            if next and language_code and next.startswith("/"+language_code+"/") :
                next = next[(len(language_code)+2):]
                next_url_generate = True
                
            if language:
                if language != settings.LANGUAGE_CODE and [lang for lang in settings.LANGUAGES if lang[0] == language]:
                    redirect_path = f'/{language}/{next}' if next_url_generate else f'/{language}/'
                elif language == settings.LANGUAGE_CODE:
                    redirect_path = f'/{next}' if next_url_generate else '/'
                else:
                    return response
                from django.utils import translation
                translation.activate(language)
                response = HttpResponseRedirect(redirect_path)
                response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language)
        except Exception as exc:
            pass
    return response


#Delete
class DeleteObjectFormView(AJAXRequestMixin, ModalFormMixin, AdminPermissionRequiredMixin, JSONResponseMixin,
                                      generic.FormView):
    form_class = DeleteConfirmForm
    id_form = "subproject_deletion_step_form"
    title = _('Confirm deletion')
    submit_button = _('Confirm')
    form_class_color = 'danger'

    def post(self, request, *args, **kwargs):
        form = None
        if self.kwargs.get('object_id') and self.kwargs.get('type'):
            ClassModal = None
            for app_conf in apps.get_app_configs():
                try:
                    ClassModal = app_conf.get_model(self.kwargs.get('type').lower())
                    break # stop as soon as it is found
                except LookupError:
                    # no such model in this application
                    pass
            
            if ClassModal:
                obj = ClassModal.objects.get(id=self.kwargs.get('object_id'))
                form = DeleteConfirmForm(request.POST)

                if form and form.is_valid():
                    return self._delete_object(obj)
        
        msg = _("An error has occurred...")
        messages.add_message(self.request, messages.ERROR, msg, extra_tags='error')

        context = {'msg': render(self.request, 'common/messages.html').content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)
    
    def _delete_object(self, obj):
        _class = obj.__class__
        
        obj.delete()
        
        #SubprojetStep
        if _class == SubprojectStep:
            subproject: SubprojectStep = obj.subproject
            current_subproject_step = subproject.get_current_subproject_step
            if current_subproject_step:
                if current_subproject_step.step.ranking < 8 and current_subproject_step.step.ranking != 2:
                    subproject.current_status_of_the_site = "Identifié"
                elif current_subproject_step.step.ranking == 9:
                    subproject.current_status_of_the_site = "Abandon"
                elif current_subproject_step.step.ranking == 10:
                    subproject.current_status_of_the_site = "Arrêt"
                elif current_subproject_step.step.ranking == 14:
                    subproject.current_status_of_the_site = "Réception provisoire"
                else:
                    subproject.current_status_of_the_site = current_subproject_step.step.wording

                if current_subproject_step.step.ranking == 3:
                    subproject.approval_date_cora = current_subproject_step.begin

                subproject.current_level_of_physical_realization_of_the_work = str(current_subproject_step.step.percent if current_subproject_step.step.percent else current_subproject_step.step.wording)
                subproject.save()
            
        
        msg = _("The Step was successfully removed.")
        messages.add_message(self.request, messages.SUCCESS, msg, extra_tags='success')

        context = {'msg': render(self.request, 'common/messages.html').content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)
#And Delete