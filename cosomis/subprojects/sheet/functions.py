import re
import datetime

from django.utils.translation import gettext as _

from subprojects.models import Subproject
from .utils import (
    subproject_fk_fields_names,
    subproject_m2m_fields_names,
    reference_fields,
)

def get_date(value: str):
    try:
        if 'T' in value and value.endswith('Z'):
            # Retirer le Z car strptime ne le supporte pas directement
            date_time_str = value.replace('Z', '+00:00') # Remplacer Z par le fuseau horaire UTC
            
            # Format : 'YYYY-MM-DDTHH:mm:ss.SSS' (notez le .f pour les microsecondes)
            # Python gère les millisecondes comme des microsecondes dans %f
            return datetime.datetime.strptime(date_time_str, '%Y-%m-%dT%H:%M:%S.%f%z')
        
        return datetime.datetime.strptime(value, '%Y-%m-%d').date()
    except TypeError:
        # Gérer le cas où la valeur est None (null en DB) ou n'est pas une chaîne
        if value is None:
            return None
        else:
            return None
        
    except ValueError as e:
        # Gérer le cas où le format ne correspond pas à '%Y-%m-%d'
        return None

def extract_id(value):
    """
    Extract an integer ID from strings like "[1922].AFELE-BALANKA"
    Returns None if extraction fails.
    """
    if not isinstance(value, str):
        return None

    match = re.search(r"\[(\d+)\]", value)
    return int(match.group(1)) if match else None


def normalize_foreign_key(value):
    """
    Normalize a foreign key value:
    - If it's an int → OK
    - If it's a string like "[1922].Name" → extract ID
    - If it's a list → get first valid ID
    - If nothing valid → return None
    """
    # Case 1 : déjà un entier
    if isinstance(value, int):
        return value

    # Case 2 : une string "[123].Xxxxx"
    if isinstance(value, str):
        return extract_id(value)

    # Case 3 : une liste : ["[1922].AA", "[1927].BB"]
    if isinstance(value, list):
        for item in value:
            if isinstance(item, int):
                return item
            if isinstance(item, str):
                _id = extract_id(item)
                if _id is not None:
                    return _id
        return None  # rien trouvé

    # Autre cas (None, dict, etc.)
    return None


def normalize_subproject_dict(data: dict) -> dict:
    """
    Normalise automatiquement tout le dictionnaire.
    - Corrige foreign keys mal formées
    - Remplace les listes FK vides par None
    """

    CLEANED = {}

    for key, value in data.items():

        # Cas : secteur, type d'ouvrage, type de travaux, désignation (valeur texte d'une liste de référence)
        if key in reference_fields:
            value = value.strip() if isinstance(value, str) else value
            CLEANED[key + "_id"] = value if value not in (None, "") else None

        # Cas : les champs FK habituels
        elif key.endswith("_id") or key in subproject_fk_fields_names:
            CLEANED[key + "_id"] = normalize_foreign_key(value)

        # Si c’est list_of_villages (many-to-many)
        elif key in subproject_m2m_fields_names:
            # Extraire uniquement les IDs valides
            valid_ids = []

            for item in value if isinstance(value, list) else []:
                if isinstance(item, int):
                    valid_ids.append(item)
                elif isinstance(item, str):
                    _id = extract_id(item)
                    if _id is not None:
                        valid_ids.append(_id)

            CLEANED[key] = valid_ids

        elif key in ['created_date', 'updated_date'] or 'date' in key:
            CLEANED[key] = get_date(value)

        else:
            # Pas un FK = copier tel quel
            CLEANED[key] = value

    return CLEANED


def unknown_reference_values(data: dict) -> list:
    """Messages d'erreur pour les valeurs (dictionnaire normalisé) absentes de leur liste de référence."""
    errors = []
    for field, Model in reference_fields.items():
        value = data.get(field + "_id")
        if value is not None and not Model.objects.filter(name=value).exists():
            errors.append(_("“%(value)s” is not in the list of values of the field “%(field)s”.") % {
                'value': value, 'field': Subproject._meta.get_field(field).verbose_name
            })
    return errors
