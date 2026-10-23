"""Mot de passe initial à changer à la première connexion, pour les comptes créés dans le DCC : l'obligation est
rangée par le DCC dans `authentication_passwordchangerequirement` (même base que le SIG) et levée par le DCC dès
que la personne change son mot de passe sur une plateforme (DCC, MGP, SIG). Le changement fait ici passe aussi
par le DCC (`authentication/api/first-login-password/`), qui l'applique à tous les comptes de la personne (la table
`auth_user` est partagée avec le DCC ; le compte MGP de même e-mail est mis à jour par le DCC)."""
import logging

import requests
from django.conf import settings
from django.db import connection, transaction
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)

# Posé dans la session une fois vérifié qu'aucun changement n'est en attente.
CHECKED_SESSION_KEY = 'password_change_checked'


def password_change_required(user):
    """True si un changement imposé est en attente pour ce compte (par son id, son e-mail ou le facilitateur qui
    lui est lié). Table absente (DCC pas encore migré) : False."""
    try:
        # point de sauvegarde : une erreur (table absente) ne doit pas rendre inutilisable une transaction en cours
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM authentication_passwordchangerequirement WHERE changed_at IS NULL AND ("
                " user_id = %s OR (email IS NOT NULL AND email <> '' AND email = lower(%s))"
                " OR facilitator_id IN (SELECT id FROM authentication_facilitator WHERE user_id = %s)"
                ") LIMIT 1",
                [user.pk, (user.email or '').strip(), user.pk],
            )
            return cursor.fetchone() is not None
    except Exception as exc:
        logger.warning("Password change requirement not read: %s", exc)
        return False


def change_initial_password_on_cdd(login, current_password, new_password, confirmation, language=None):
    """Changement imposé fait par le DCC pour toutes les plateformes. Renvoie (ok, message)."""
    try:
        response = requests.post(
            f"{settings.CDD_URL_BASE}/authentication/api/first-login-password/",
            json={
                'login': login, 'current_password': current_password, 'new_password': new_password,
                'new_password_confirm': confirmation, 'platform': 'sig_web', 'language': language,
            },
            timeout=60,
        )
    except requests.RequestException as exc:
        logger.warning("DCC unreachable for the password change: %s", exc)
        return False, _("The password could not be changed: the DCC platform cannot be reached. Please try again later.")
    try:
        data = response.json()
    except ValueError:
        return False, _("The password could not be changed (error %(status)s).") % {'status': response.status_code}
    return bool(data.get('ok')), data.get('message') or ''
