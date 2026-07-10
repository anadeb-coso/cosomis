from django.forms.models import model_to_dict
import json
from decimal import Decimal
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
    # objets Django (model, queryset, etc.)
    if hasattr(value, "__dict__"):
        return format_value(value.__dict__)
    # types natifs JSON (int, float, bool, str)
    if isinstance(value, (int, float, bool, str)):
        return value
    return value
