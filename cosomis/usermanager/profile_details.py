"""Profile page of the logged-in user, the same as the DCC one but built by the SIG itself.

The SIG shares its database with the DCC: the web account (`auth_user`, also the DCC web account), the facilitator
account (`authentication_facilitator`) and the project links (`process_manager_project_users` / `_facilitators`)
are read here directly. Only the MGP account is asked to the MGP (service API), the MGP database being separate.
Every block is protected: the page must always be shown."""
import logging

from django.db import connection
from django.utils.translation import gettext as _, gettext_lazy

import grm_client
from administrativelevels.models import AdministrativeLevel
from authentication.models import Facilitator
from subprojects.models import Cycle, Project

logger = logging.getLogger(__name__)

FACILITATOR_TYPES = {'community_facilitator': gettext_lazy("Community facilitator"),
                     'technical_facilitator': gettext_lazy("Technical facilitator")}
FEMALE_VALUES = {'mme', 'mlle', 'f', 'femme', 'female', 'féminin', 'feminin'}
MALE_VALUES = {'m.', 'm', 'mr', 'h', 'homme', 'male', 'masculin'}


def gender_of(sex):
    value = (sex or '').strip().lower()
    if value in FEMALE_VALUES:
        return 'female'
    if value in MALE_VALUES:
        return 'male'
    return None


def _linked_facilitator(user):
    """Facilitator account of the same person (same e-mail, or linked to this web account)."""
    try:
        queryset = Facilitator.objects.using('cdd').filter(active=True)
        by_email = queryset.filter(email__iexact=user.email).first() if user.email else None
        if by_email:
            return by_email
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM authentication_facilitator WHERE user_id = %s AND active LIMIT 1", [user.pk])
            row = cursor.fetchone()
        return queryset.filter(pk=row[0]).first() if row else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Facilitator account not read: %s", exc)
        return None


def _project_ids(table, column, value):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT project_id FROM {table} WHERE {column} = %s", [value])
        return {row[0] for row in cursor.fetchall()}


def _projects(user, facilitator):
    as_user = _project_ids('process_manager_project_users', 'user_id', user.pk)
    as_facilitator = _project_ids('process_manager_project_facilitators', 'facilitator_id', facilitator.pk) if facilitator else set()
    projects = list(Project.objects.filter(pk__in=as_user | as_facilitator).select_related('parent').order_by('name'))
    cycles = {}
    for cycle in Cycle.objects.filter(project__in=projects).order_by('order', 'id'):
        cycles.setdefault(cycle.project_id, []).append(cycle.name)
    facilitator_role = str(FACILITATOR_TYPES.get(getattr(facilitator, 'facilitator_type', None), _("Facilitator")))
    return [{
        'name': project.name,
        'description': project.description,
        'parent': project.parent.name if project.parent_id else None,
        'cycles': cycles.get(project.pk, []),
        'roles': ([_("User")] if project.pk in as_user else []) + ([facilitator_role] if project.pk in as_facilitator else []),
    } for project in projects]


def _facilitator_zone(facilitator):
    """Cantons of the facilitator's villages, and the villages themselves."""
    ids = set()
    for item in (facilitator.administrative_levels_ids or []) + (facilitator.administrative_levels or []):
        value = item.get('id') if isinstance(item, dict) else item
        if str(value or '').isdigit():
            ids.add(int(value))
    villages = list(AdministrativeLevel.objects.filter(pk__in=ids).select_related('parent').order_by('name'))
    cantons = []
    for village in villages:
        parent = village.parent
        while parent is not None and parent.type != 'Canton':
            parent = parent.parent
        if parent is not None and parent.name not in cantons:
            cantons.append(parent.name)
    return {'labels': [_("Canton: %(name)s") % {'name': name} for name in sorted(cantons)],
            'additional': [v.name for v in villages], 'villages': len(villages)}


def build_profile_details(user):
    facilitator = _linked_facilitator(user)
    grm = grm_client.get_user_account(user.email)  # None: MGP unreachable
    gender = gender_of(getattr(facilitator, 'sex', None))
    details = {
        'user': user,
        'facilitator': facilitator,
        'facilitator_type': FACILITATOR_TYPES.get(facilitator.facilitator_type) if facilitator else None,
        'gender': gender,
        'civility': getattr(facilitator, 'sex', None),
        'full_name': user.get_full_name() or getattr(facilitator, 'name', None) or user.username,
        'phone': getattr(facilitator, 'phone', None) or (grm or {}).get('phone_number'),
        'usernames': [],
        'groups': [],
        'projects': [],
        'zone': None,
        'grm_reachable': grm is not None,
    }
    usernames = []
    for name in (user.username, getattr(facilitator, 'username', None), (grm or {}).get('username')):
        if name and name not in usernames:
            usernames.append(name)
    details['usernames'] = usernames

    groups = set(user.groups.values_list('name', flat=True))
    groups.update((grm or {}).get('groups') or [])
    details['groups'] = sorted(groups)

    details['platforms'] = [
        {'name': _('Web DCC'), 'icon': 'fa-desktop', 'active': True},  # web accounts are shared by the DCC and the SIG
        {'name': _('Mobile DCC'), 'icon': 'fa-mobile-alt', 'active': facilitator is not None},
        {'name': _('SIG (COSOMIS)'), 'icon': 'fa-map-marked-alt', 'active': True},
        {'name': _('MGP (GRM)'), 'icon': 'fa-comments', 'active': bool((grm or {}).get('exists')), 'unknown': grm is None},
    ]
    try:
        details['projects'] = _projects(user, facilitator)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Projects of the profile not read: %s", exc)
    try:
        if facilitator is not None:
            details['zone'] = _facilitator_zone(facilitator)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Area of intervention not read: %s", exc)
    return details
