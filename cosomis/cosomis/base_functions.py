from django.forms.models import model_to_dict
from django.db import models
from django.db.models.fields.files import FieldFile
from django.utils.translation import gettext_lazy as _
import json
from decimal import Decimal
from enum import Enum
from uuid import UUID
from datetime import date, datetime, time
from pathlib import Path

def make_json_serializable(obj):
    if hasattr(obj, '_meta'):  # instance Django
        return model_to_full_dict(obj)
    elif isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(v) for v in obj]
    elif hasattr(obj, 'isoformat'):  # datetime
        return obj.isoformat()
    else:
        return obj



def model_or_dict_to_serializable(data):
    if hasattr(data, '_meta'):  # c'est un modèle Django
        return {k: format_value(v) for k, v in model_to_dict(data).items()}
    elif isinstance(data, dict):
        return format_value(data)
    elif isinstance(data, list):
        return [model_or_dict_to_serializable(d) for d in data]
    return data

def model_to_full_dict(instance):
        data = model_to_dict(instance, fields=[f.name for f in instance._meta.fields])
        return {k: format_value(v) for k, v in data.items()}


def record_m2m_change(instance, field_name, old_pks, user=None):
    """Append a history entry for a ManyToManyField change to `instance.users_involved`,
    in the same (old, new) diff shape BaseModel.users_history() uses for concrete
    fields, so the "History" panel (history_entries() in
    subprojects/templatetags/custom_tags.py) renders it the same way as any other
    field edit. Needed because m2m writes (form.save_m2m(), field.set()/.add()/
    .remove()) happen outside save() and are invisible to users_history()'s
    model_to_dict()-based diff, which only walks instance._meta.fields -
    ManyToManyField isn't one of those.

    Call right after the m2m has actually been written, passing the related pks
    that were set *before* that write (old_pks) - the new set is read live off
    `instance`.
    """
    manager = getattr(instance, field_name)
    new_pks = list(manager.values_list('pk', flat=True))
    if set(old_pks) == set(new_pks):
        return

    related_model = manager.model
    related_manager = getattr(related_model, 'all_objects', related_model.objects)

    def display(pks):
        if not pks:
            return str(_('(empty)'))
        return ', '.join(str(o) for o in related_manager.filter(pk__in=pks))

    # AnonymousUser (or any other non-model value) has no _meta - guard against
    # model_to_full_dict() crashing on it rather than trusting every caller to
    # have already filtered it out (get_current_user() does, but this stays
    # safe even if called with a raw request.user directly).
    if user is not None and not isinstance(user, dict) and not hasattr(user, '_meta'):
        user = None
    user_json = (user if isinstance(user, dict) else model_to_full_dict(user)) if user else {'type': None}
    if user_json.get('last_name'):
        user_json['type'] = 'user'
    elif user_json.get('no_sql_user'):
        user_json['type'] = 'facilitator'
    user_json['data_updated_date'] = datetime.now().isoformat()
    user_json['data_changed'] = {field_name: (display(old_pks), display(new_pks))}

    users_involved = instance.users_involved if instance.users_involved else []
    users_involved.append(user_json)
    instance.users_involved = format_value(users_involved)
    instance.update_by_user = user_json

    models.Model.save(instance, update_fields=['users_involved', 'update_by_user', 'updated_date'])

def serialize_for_json(data):
    """Convertit les datetime et autres objets non sérialisables en str"""
    def default(o):
        if hasattr(o, "isoformat"):
            return o.isoformat()  # datetime → '2025-10-02T12:30:00'
        return str(o)  # fallback

    return json.loads(json.dumps(data, default=default))
def format_value(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):  # datetime, date, time
        return value.isoformat()
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [format_value(v) for v in value]
    if isinstance(value, dict):
        return {k: format_value(v) for k, v in value.items()}
    if isinstance(value, Decimal):
        # str = pas de perte de précision (recommandé pour montants)
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="ignore")
    if isinstance(value, set):
        return [format_value(v) for v in value]
    # enums (e.g. Django TextChoices/IntegerChoices) - store their plain value,
    # not the member's __dict__ (which holds __objclass__, a class whose own
    # __dict__ is a non-JSON-serializable mappingproxy)
    if isinstance(value, Enum):
        return format_value(value.value)
    # FieldFile (FileField/ImageField value) - __dict__ holds a back-reference to
    # its owning model instance ("instance"), which would recurse into this same
    # FieldFile forever; store its relative path instead, like the CharField it replaces.
    if isinstance(value, FieldFile):
        return value.name or None
    # objets Django (model, queryset, etc.)
    if hasattr(value, "__dict__"):
        return format_value(value.__dict__)
    # types natifs JSON (int, float, bool, str)
    if isinstance(value, (int, float, bool, str)):
        return value
    return value
