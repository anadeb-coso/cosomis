"""Jetons de session du mobile DCC, délivrés par le DCC à la connexion et valables sur le DCC, le SIG et le MGP
(cdd-backend : authentication/platform_tokens.py). Le mobile envoie le jeton dans le champ `token` à la place du mot
de passe ; le SIG le vérifie en lisant la table du DCC `authentication_platformaccesstoken` (même base), avec les
mêmes règles : empreinte SHA-256 du jeton connue, ni expiré ni révoqué, compte actif, mot de passe inchangé depuis
la délivrance (empreinte du hash du mot de passe)."""
import hashlib
import logging

from django.contrib.auth.models import User
from django.db import connection, transaction

from authentication.models import Facilitator

logger = logging.getLogger(__name__)

PREFIX = 'cps_'
TABLE = 'authentication_platformaccesstoken'


def is_platform_token(value):
    return isinstance(value, str) and value.startswith(PREFIX)


def password_fingerprint(password_hash):
    return hashlib.sha256((password_hash or '').encode('utf-8')).hexdigest()


def account_from_token(token, touch=True):
    """Facilitator (base du DCC) ou User désigné par un jeton valide, sinon None. Table absente (DCC pas encore
    migré) : None."""
    if not is_platform_token(token):
        return None
    key_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    try:
        # point de sauvegarde : une erreur (table absente) ne doit pas rendre inutilisable une transaction en cours
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                f"SELECT id, account_kind, account_id, password_fingerprint, "
                f"last_used_at IS NULL OR last_used_at < now() - interval '1 hour' "
                f"FROM {TABLE} WHERE key_hash = %s AND revoked_at IS NULL AND expires_at > now()",
                [key_hash],
            )
            row = cursor.fetchone()
            if row is None:
                return None
            record_id, kind, account_id, fingerprint, stale = row
            if kind == 'facilitator':
                account = Facilitator.objects.using('cdd').filter(pk=account_id).first()
                active = bool(account and account.active)
            else:
                account = User.objects.filter(pk=account_id).first()
                active = bool(account and account.is_active)
            if not active or password_fingerprint(account.password) != fingerprint:
                return None
            if touch and stale:
                cursor.execute(f"UPDATE {TABLE} SET last_used_at = now() WHERE id = %s", [record_id])
            return account
    except Exception as exc:
        logger.warning("Platform token not read: %s", exc)
        return None
