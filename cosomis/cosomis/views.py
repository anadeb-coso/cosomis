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
    """Profile page of the logged-in user, served by the SIG itself (same content as the DCC one). Opened with a
    GET; a POST (old link) is redirected to the GET page."""
    from django.shortcuts import redirect

    from usermanager.profile_details import build_profile_details
    from usermanager.views_first_login import FirstLoginPasswordForm

    if request.method == 'POST':
        return redirect('profile')

    return render(request, 'profile.html', {
        'title': _('Profile'),
        'breadcrumb': [{'url': '', 'title': _('Profile')}],
        'hide_content_header': True,
        'd': build_profile_details(request.user),
        'password_form': FirstLoginPasswordForm(),
        'open_password': request.GET.get('password') == '1',
    })


@login_required
def profile_change_password(request):
    """New password for all the person's accounts (DCC, SIG, facilitator, MGP), applied by the DCC."""
    from django.contrib.auth import update_session_auth_hash
    from django.contrib.auth.models import User
    from django.shortcuts import redirect

    from usermanager.password_change import CHECKED_SESSION_KEY, change_password_on_all_platforms
    from usermanager.profile_details import build_profile_details
    from usermanager.views_first_login import FirstLoginPasswordForm

    if request.method != 'POST':
        return redirect('profile')
    form = FirstLoginPasswordForm(request.POST)
    if form.is_valid():
        data = form.cleaned_data
        ok, message = change_password_on_all_platforms(
            request.user.email or request.user.username, data['current_password'], data['new_password'],
            data['new_password_confirm'], language=get_language(),
        )
        if ok:
            # `auth_user` is shared with the DCC, which has just written the new password: keep this session open.
            update_session_auth_hash(request, User.objects.get(pk=request.user.pk))
            request.session[CHECKED_SESSION_KEY] = True
            messages.success(request, message or _("The password has been changed on all the platforms."))
            return redirect('profile')
        form.add_error(None, message)
    return render(request, 'profile.html', {
        'title': _('Profile'),
        'breadcrumb': [{'url': '', 'title': _('Profile')}],
        'd': build_profile_details(request.user),
        'password_form': form,
        'open_password': True,
    })
