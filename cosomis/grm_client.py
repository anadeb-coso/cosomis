"""Client HTTP vers l'API inter-services de grm-backend (cf. `D:\\COSO\\PROJECTS\\GRM\\claude\\CLAUDE.md`).

Remplace les accès directs aux bases CouchDB partagées `eadls` (facilitateurs/ADL) et `grm`
(plaintes/issues) : ces deux bases ont été migrées vers Postgres côté GRM
(`issue.models.Adl`, `issue.models.Issue`) et ne sont plus la source de vérité. MIS interroge
désormais l'API REST inter-services exposée par grm-backend sous `/api/service/...`.

Authentification par secret partagé (`settings.GRM_SECRET_KEY_GENRATE`, header
`X-GRM-Secret`) — même mécanisme que l'intégration GRM -> CDD déjà existante
(GRM `authentication/functions.py::update_user_adl_on_cdd_app`, CDD
`authentication/api/facilitators/update-user-adls/`), simplement étendu à MIS.

Toutes les fonctions sont "best-effort" : une panne du service GRM (timeout, 5xx, DNS...) ne
doit jamais faire planter MIS, elle renvoie donc None/[] plutôt que de lever une exception.
"""
import requests
from django.conf import settings

_TIMEOUT = 15


def _headers():
    return {'X-GRM-Secret': settings.GRM_SECRET_KEY_GENRATE}


def _base_url():
    return f"{settings.GRM_URL_BASE}/api/service"


def get_facilitator_by_email(email):
    """Remplace `nsc.get_db('eadls').get_query_result({"type": "adl", "representative.email": email})`.

    Renvoie le dict façon ancien document CouchDB `eadls`
    (`_id`, `type`, `name`, `location_name`, `administrative_region`,
    `administrative_regions`, `additional_administrative_regions`,
    `representative: {id, name, email, phone, photo, is_active, password, groups}`),
    ou None si aucun facilitateur GRM ne correspond à cet email (ou si le service est
    injoignable), au lieu de lever une exception d'index sur une liste vide comme le faisait
    souvent l'ancien code CouchDB.
    """
    if not email:
        return None
    try:
        response = requests.get(
            f"{_base_url()}/adls/by-email/",
            params={'email': email}, headers=_headers(), timeout=_TIMEOUT,
        )
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    return response.json()


def get_issue_categories():
    """Remplace la requête Mango CouchDB `grm` `{"type": "issue_category"}`.
    Renvoie une liste de dicts `{legacy_id, name, label, abbreviation,
    confidentiality_level, administrative_level}` (liste vide si le service est injoignable)."""
    try:
        response = requests.get(
            f"{_base_url()}/issue-categories/", headers=_headers(), timeout=_TIMEOUT,
        )
    except requests.RequestException:
        return []
    if response.status_code != 200:
        return []
    return response.json()


def get_issue_statuses():
    """Remplace la requête Mango CouchDB `grm` `{"type": "issue_status"}`.
    Renvoie une liste de dicts `{legacy_id, name, final_status, initial_status,
    rejected_status, open_status, unresolved_status, eligible_status, not_eligible_status}`
    (liste vide si le service est injoignable)."""
    try:
        response = requests.get(
            f"{_base_url()}/issue-statuses/", headers=_headers(), timeout=_TIMEOUT,
        )
    except requests.RequestException:
        return []
    if response.status_code != 200:
        return []
    return response.json()


def search_issues(**filters):
    """Remplace une requête Mango CouchDB `grm` `{"type": "issue", ...}`.

    `filters` est transmis tel quel en paramètres de requête à l'endpoint `/issues/` :
    `confirmed`, `publish` (bool), `auto_increment_id`, `status`, `category` (legacy_id),
    `assignee_email`, `reporter_email`, `administrative_region_id`,
    `start_date`/`end_date` (ISO, filtrent sur `issue_date`). C'est un appel de service de
    confiance : aucun filtrage par périmètre de villages n'est appliqué côté GRM, MIS doit
    transmettre lui-même les filtres voulus.

    Renvoie une liste de dicts (liste vide si le service est injoignable). Chaque valeur
    None est retirée des paramètres pour ne pas envoyer `param=None` en query string.
    """
    params = {k: v for k, v in filters.items() if v is not None}
    try:
        response = requests.get(
            f"{_base_url()}/issues/", params=params, headers=_headers(), timeout=_TIMEOUT,
        )
    except requests.RequestException:
        return []
    if response.status_code != 200:
        return []
    return response.json()


def get_issue_stats_by_assignee():
    """Remplace `grm_db.get_view_result('issues', 'by_assignee_stats')`.
    Renvoie une liste de dicts `{assignee_email, assignee_name, total}`
    (liste vide si le service est injoignable)."""
    try:
        response = requests.get(
            f"{_base_url()}/issues/stats/by-assignee/", headers=_headers(), timeout=_TIMEOUT,
        )
    except requests.RequestException:
        return []
    if response.status_code != 200:
        return []
    return response.json()
