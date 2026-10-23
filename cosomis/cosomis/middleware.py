from threading import local

_thread_locals = local()


def get_current_user():
    """The user attached to the in-flight request, if any - set by
    CurrentUserMiddleware. Used by the M2M history signal (see
    cosomis/models_base.py) to attribute an M2M change (form.save_m2m(),
    field.set()/.add()/.remove()/.clear()) to whoever triggered it, since
    Django's m2m_changed signal itself carries no user information.

    Reads `request.user` fresh on every call rather than caching a snapshot -
    for a DRF endpoint (e.g. a token/JWT-authenticated React Native client),
    Django's own AuthenticationMiddleware only resolves the session (usually
    AnonymousUser, since a mobile client sends no session cookie); the actual
    JWTAuthentication runs later, inside the view (APIView.initial()), which
    still executes *within* CurrentUserMiddleware's get_response() call. DRF's
    Request.user setter writes the authenticated user back onto this same
    underlying HttpRequest, so by the time an M2M write happens deeper in the
    view, request.user already reflects the real, token-authenticated user -
    as long as we read it then, not at middleware entry."""
    request = getattr(_thread_locals, 'request', None)
    if request is None:
        return None
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    return user


class CurrentUserMiddleware:
    """Stashes the request itself (not a snapshot of request.user) in a
    thread-local for the duration of the request, so code with no direct
    access to the request (signal receivers, model methods) can still know
    who is acting - see get_current_user()."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.request = request
        try:
            return self.get_response(request)
        finally:
            _thread_locals.request = None


class PasswordChangeRequiredMiddleware:
    """Compte créé dans le DCC dont le mot de passe initial n'a été changé sur aucune plateforme : toute page du SIG
    (adresses préfixées par la langue) renvoie vers le changement obligatoire (`usermanager:first_login_password`).
    Les API (`/api/`, jetons du mobile) ne sont pas concernées. Vérifié une fois par session. Doit suivre
    AuthenticationMiddleware."""

    EXEMPT_VIEW_NAMES = {
        'usermanager:first_login_password',
        'usermanager:login',
        'usermanager:logout',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        from django.conf import settings
        from usermanager.password_change import CHECKED_SESSION_KEY, password_change_required

        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated or request.session.get(CHECKED_SESSION_KEY):
            return None
        match = request.resolver_match
        prefixes = tuple(f"/{code}/" for code, _name in settings.LANGUAGES)
        if match is None or match.view_name in self.EXEMPT_VIEW_NAMES or not request.path_info.startswith(prefixes):
            return None
        if not password_change_required(user):
            request.session[CHECKED_SESSION_KEY] = True
            return None

        from django.http import JsonResponse
        from django.shortcuts import redirect
        from django.utils.translation import gettext

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or getattr(request, 'htmx', False):
            return JsonResponse({'detail': gettext('You must change your password before your first login.'),
                                 'code': 'password_change_required'}, status=403)
        return redirect('usermanager:first_login_password')
