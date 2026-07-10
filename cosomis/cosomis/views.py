from django.http import HttpResponseRedirect, HttpResponse
from django.conf import settings
from django.utils.translation import get_language
from django.contrib.auth.decorators import login_required

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import generic
from django.http import Http404
from django.apps import apps
import requests

from cosomis.mixins import AJAXRequestMixin, JSONResponseMixin, ModalFormMixin
from cosomis.forms import DeleteConfirmForm
from usermanager.permissions import AdminPermissionRequiredMixin
from subprojects.models import SubprojectStep
from cosomis.functions import get_validation_code
from cosomis.constants import (
    IN_PROGRESS_RANKING, APPROVED_BY_CORA_RANKING, NOT_APPROVED_BY_CORA_RANKING, ABANDONED_RANKING, INTERRUPTED_RANKING,
    HANDOVER_TO_COMMUNITY_RANKING
)


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
                if current_subproject_step.step.ranking < IN_PROGRESS_RANKING and current_subproject_step.step.ranking != NOT_APPROVED_BY_CORA_RANKING:
                    subproject.current_status_of_the_site = "Identifié"
                elif current_subproject_step.step.ranking == ABANDONED_RANKING:
                    subproject.current_status_of_the_site = "Abandon"
                elif current_subproject_step.step.ranking == INTERRUPTED_RANKING:
                    subproject.current_status_of_the_site = "Arrêt"
                elif current_subproject_step.step.ranking == HANDOVER_TO_COMMUNITY_RANKING:
                    subproject.current_status_of_the_site = "Réception provisoire"
                else:
                    subproject.current_status_of_the_site = current_subproject_step.step.wording

                if current_subproject_step.step.ranking == APPROVED_BY_CORA_RANKING:
                    subproject.approval_date_cora = current_subproject_step.begin

                if current_subproject_step.step.percent:
                    subproject.current_level_of_physical_realization_of_the_work = str(current_subproject_step.step.percent)
                    subproject.current_level_of_physical_realization_of_the_work_percent = current_subproject_step.step.percent
                else:
                    subproject.current_level_of_physical_realization_of_the_work = current_subproject_step.step.wording
                    subproject.current_level_of_physical_realization_of_the_work_percent = 0.0
                subproject.current_level_of_physical_realization_of_the_work_wording = subproject.get_current_subproject_step_and_level_without_percent
                
                subproject.save(user=self.request.user)
            
        
        msg = _("The Step was successfully removed.")
        messages.add_message(self.request, messages.SUCCESS, msg, extra_tags='success')

        context = {'msg': render(self.request, 'common/messages.html').content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)
#And Delete


@login_required
def profile(request):
    if request.method == 'POST':
        try:
            scheme = request.scheme
            domain = request.get_host()
            full_url = f"{scheme}://{domain}"
            language = get_language()

            previous_url = request.headers.get('Referer', full_url)

            #Recuperation de Token
            session = requests.Session()
            response = session.get(f"{settings.CDD_URL_BASE}/authentication/get-csrf-token/")

            if response.status_code == 200:
                data = response.json()
                token = data.get("csrfToken")
            else:
                raise Http404
            
            cookies = session.cookies.get_dict()
            headers = {
                "X-CSRFToken": token,
                "Referer": f"{settings.CDD_URL_BASE}/",
                "Origin": settings.CDD_URL_BASE
            }
            post_data = {
                'email': request.user.email,
                'code': get_validation_code(request.user.email),
                'redirection_url': full_url,
                'csrfmiddlewaretoken': token,
                'language': language,
                'previous_url': previous_url
            }
            
            response_post = session.post(f"{settings.CDD_URL_BASE}/{language}/user-manager/", headers=headers, cookies=cookies, data=post_data)

            content = response_post.text\
                .replace('/static/', f'{settings.CDD_URL_BASE}/static/')\
                .replace(f'url: "/{language}/', f'url: "{settings.CDD_URL_BASE}/{language}/')\
                .replace('action="/i18n/', f'action="{settings.CDD_URL_BASE}/i18n/')


            return HttpResponse(content)


        except Exception as e:
            raise Http404
        
    raise Http404