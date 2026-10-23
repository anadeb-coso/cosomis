from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.utils.translation import get_language, gettext_lazy
from django.views import generic

from usermanager.password_change import CHECKED_SESSION_KEY, change_initial_password_on_cdd, password_change_required


class FirstLoginPasswordForm(forms.Form):
    current_password = forms.CharField(label=gettext_lazy("Current password"), strip=False,
                                       widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))
    new_password = forms.CharField(label=gettext_lazy("New password"), strip=False, max_length=16,
                                   widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
                                   help_text=gettext_lazy("8 to 16 letters and digits, with at least one letter and one digit."))
    new_password_confirm = forms.CharField(label=gettext_lazy("New password confirmation"), strip=False, max_length=16,
                                           widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))


class FirstLoginPasswordView(LoginRequiredMixin, generic.FormView):
    """Changement obligatoire du mot de passe initial d'un compte créé dans le DCC (PasswordChangeRequiredMiddleware y
    renvoie les pages tant qu'il n'est pas fait). Le DCC l'applique à toutes les plateformes ; la session courante
    reste ouverte."""
    template_name = 'first_login_password.html'
    form_class = FirstLoginPasswordForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not password_change_required(request.user):
            request.session[CHECKED_SESSION_KEY] = True
            return redirect(settings.LOGIN_REDIRECT_URL)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        data = form.cleaned_data
        ok, message = change_initial_password_on_cdd(
            self.request.user.email or self.request.user.username, data['current_password'], data['new_password'],
            data['new_password_confirm'], language=get_language(),
        )
        if not ok:
            form.add_error(None, message)
            return self.form_invalid(form)
        # `auth_user` est partagée avec le DCC, qui vient d'y écrire le nouveau mot de passe : la session est gardée.
        update_session_auth_hash(self.request, User.objects.get(pk=self.request.user.pk))
        self.request.session[CHECKED_SESSION_KEY] = True
        messages.success(self.request, gettext_lazy("Your password has been changed. It is now valid on all the platforms (DCC, MGP and SIG)."))
        return redirect(settings.LOGIN_REDIRECT_URL)
