"""Import des niveaux administratifs (Région, Préfecture, Commune, Canton, Village/localité) depuis un fichier :
envoi du fichier -> aperçu -> confirmation (et rattachement, au choix, au projet courant).

L'aperçu et l'enregistrement passent par la même fonction (`process_rows`) : l'aperçu la lance « à blanc » (rien
n'est enregistré, les niveaux à créer reçoivent un identifiant provisoire négatif), la confirmation la relance sur
l'état actuel de la base. Ce que montre l'aperçu est donc exactement ce qui sera enregistré.

Chaque ligne est lue de haut en bas : chaque niveau est cherché SOUS le parent trouvé juste avant (jamais par son
seul nom : deux cantons « LOKO » existent dans deux communes différentes), puis créé s'il n'existe pas. Un nom
proche d'un niveau existant (accents, tirets, faute de frappe sur un parent) est rapproché de ce niveau au lieu
d'en créer un doublon ; une ligne ambiguë est signalée et n'est pas enregistrée.
"""
from decimal import Decimal

import pandas as pd

from administrativelevels.functions_lookup import AMBIGUOUS, AdministrativeLevelResolver
from administrativelevels.libraries import convert_file_to_dict
from administrativelevels.models import AdministrativeLevel

LEVEL_COLUMNS = (
    ("Région", AdministrativeLevel.REGION), ("Préfecture", AdministrativeLevel.PREFECTURE),
    ("Commune", AdministrativeLevel.COMMUNE), ("Canton", AdministrativeLevel.CANTON),
    ("Village/localité", AdministrativeLevel.VILLAGE),
)
LEVEL_TYPES = tuple(_type for _, _type in LEVEL_COLUMNS)
FRONTALIER_COLUMN = "Village frontalier (1=oui, 0= non)"
RURAL_COLUMN = "Localité (Rural=1, urbain=0)"


class ImportFileError(Exception):
    pass


def _value(elt):
    return None if elt is None or (not isinstance(elt, str) and pd.isna(elt)) else elt


def read_import_file(uploaded, sheet_name=None):
    """Fichier envoyé -> dict de colonnes (format lu par `rows_from_columns`)."""
    try:
        if uploaded.name.lower().endswith('.csv'):
            return convert_file_to_dict.conversion_file_csv_to_dict(uploaded)
        return convert_file_to_dict.conversion_file_xlsx_to_dict(uploaded, sheet_name or "Sheet1")
    except Exception as exc:
        raise ImportFileError(f"Fichier illisible ({exc})")


def rows_from_columns(datas_file):
    """Dict de colonnes {colonne: {index: valeur}} -> lignes sérialisables (gardées en session entre l'aperçu et la
    confirmation)."""
    if not datas_file:
        return []

    def cell(column, count):
        try:
            return _value(datas_file[column][count])
        except Exception:
            return None

    def to_float(value):
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    rows = []
    for count in range(len(list(datas_file.values())[0])):
        names = []
        for column, _ in LEVEL_COLUMNS:
            value = cell(column, count)
            names.append(str(value).upper().strip() if value is not None and str(value).strip() else None)
        rows.append({
            'line': count + 2,  # ligne 1 = en-têtes
            'names': names,
            'frontalier': bool(cell(FRONTALIER_COLUMN, count)),
            'rural': bool(cell(RURAL_COLUMN, count)),
            'latitude': to_float(cell("Latitude", count)),
            'longitude': to_float(cell("Longitude", count)),
        })
    return rows


def _same_coordinate(current, new):
    if current is None or new is None:
        return current is None and new is None
    return round(Decimal(current), 6) == round(Decimal(str(new)), 6)


def _village_changes(village, row):
    return (village.frontalier != row['frontalier'] or village.rural != row['rural']
            or not _same_coordinate(village.latitude, row['latitude'])
            or not _same_coordinate(village.longitude, row['longitude']))


def process_rows(rows, apply=False):
    """Résout chaque ligne ; enregistre seulement si `apply`. Retourne le résultat (lignes, compteurs, erreurs...)."""
    resolver = AdministrativeLevelResolver()
    created_ids, existing_ids = set(), set()
    created_by_type = {t: [] for t in LEVEL_TYPES}
    existing_by_type = {t: set() for t in LEVEL_TYPES}
    village_values = {}  # id village existant -> valeurs du fichier (la dernière ligne l'emporte, comme à l'enregistrement)
    lines, errors, warnings = [], [], []
    villages_changed = set()
    fake_id = 0
    empty_rows = 0

    for row in rows:
        if not any(row['names']):
            empty_rows += 1
            continue
        parent = None
        cells = []
        error = None
        try:
            for name, _type in zip(row['names'], LEVEL_TYPES):
                if not name:
                    break  # niveau vide : on s'arrête au dernier niveau renseigné de la ligne
                is_village = _type == AdministrativeLevel.VILLAGE
                # tolérance aux fautes de frappe seulement pour les niveaux au-dessus du village
                result = resolver.child(parent, name, _type, fuzzy=not is_village)
                if result.error == AMBIGUOUS:
                    raise ValueError(f"{_type} « {name} » en double sous « {parent.name if parent else '-'} » : "
                                     + ", ".join(f"id {c.id}" for c in result.candidates))
                warnings += [f"Ligne {row['line']} : {w}" for w in result.warnings]
                level = result.level
                if level is None:
                    if apply:
                        level = AdministrativeLevel(name=name, type=_type, parent=parent)
                        if is_village:
                            level.frontalier, level.rural = row['frontalier'], row['rural']
                            level.latitude, level.longitude = row['latitude'], row['longitude']
                        level.save(user={'is_superuser': True})
                    else:
                        fake_id -= 1
                        level = AdministrativeLevel(id=fake_id, name=name, type=_type,
                                                    parent_id=parent.id if parent else None)
                    resolver.add(level)
                    created_ids.add(level.id)
                    created_by_type[_type].append(resolver.path(level))
                elif level.id not in created_ids:
                    existing_ids.add(level.id)
                    existing_by_type[_type].add(level.id)
                    if is_village:
                        # coordonnées et caractéristiques de la ligne : celles du village, pas de ses parents
                        village_values[level.id] = row
                        if apply:
                            village = AdministrativeLevel.objects.get(pk=level.pk)
                            if _village_changes(village, row):
                                villages_changed.add(village.id)
                            village.frontalier, village.rural = row['frontalier'], row['rural']
                            village.latitude, village.longitude = row['latitude'], row['longitude']
                            village.save(user={'is_superuser': True})
                cells.append({
                    'name': level.name, 'file_name': name, 'type': _type,
                    'status': 'new' if level.id in created_ids else 'existing',
                    'renamed': level.name != name,
                })
                parent = level
        except Exception as exc:
            # La ligne s'arrête au niveau en erreur : sans lui, ceux du dessous seraient rattachés au mauvais parent.
            # Les niveaux du dessus déjà trouvés/créés sont gardés (pas de transaction par ligne : un niveau créé
            # reste connu du resolver pour les lignes suivantes, en aperçu comme en enregistrement).
            name = row['names'][len(cells)] if len(cells) < len(row['names']) else ''
            error = f"Ligne {row['line']} - {name or ''} : {exc}"
            errors.append(error)
        skipped = row['names'][len(cells):] if error else []
        lines.append({'line': row['line'], 'cells': cells, 'error': error, 'skipped': skipped,
                      'padding': range(len(LEVEL_TYPES) - len(cells) - len(skipped)),  # colonnes vides de l'aperçu
                      'village': row if cells and cells[-1]['type'] == AdministrativeLevel.VILLAGE else None})

    # villages existants dont le fichier change les coordonnées / caractéristiques (en enregistrement : relevé
    # avant la sauvegarde, dans la boucle)
    if village_values and not apply:
        for village in AdministrativeLevel.objects.filter(id__in=village_values).only(
                'id', 'latitude', 'longitude', 'frontalier', 'rural'):
            if _village_changes(village, village_values[village.id]):
                villages_changed.add(village.id)
    villages_updated = len(villages_changed)

    by_type = [{
        'type': _type,
        'new': len(created_by_type[_type]),
        'existing': len(existing_by_type[_type]),
        'total': len(created_by_type[_type]) + len(existing_by_type[_type]),
    } for _type in LEVEL_TYPES]

    return {
        'lines': lines,
        'errors': errors,
        'warnings': warnings,
        'by_type': by_type,
        'created_by_type': [(t, sorted(created_by_type[t])) for t in LEVEL_TYPES if created_by_type[t]],
        'created_ids': {i for i in created_ids if i > 0},
        'existing_ids': existing_ids,
        'counts': {
            'rows': len(rows) - empty_rows,
            'rows_ok': sum(1 for line in lines if not line['error']),
            'rows_error': len(errors),
            'new': len(created_ids),
            'existing': len(existing_ids),
            'total': len(created_ids) + len(existing_ids),
            'villages_updated': villages_updated,
            'warnings': len(warnings),
        },
    }


def project_link_counts(result, project):
    """Rattachement au projet : niveaux du fichier déjà liés au projet / à lier."""
    if project is None:
        return None
    linked = set(project.administrative_levels.filter(id__in=result['existing_ids']).values_list('id', flat=True))
    return {
        'already_linked': len(linked),
        'to_link': result['counts']['total'] - len(linked),
    }


def link_levels_to_project(project, level_ids):
    """Ajoute les niveaux au projet (sans retirer ceux déjà liés) puis aligne ses cycles, comme le formulaire de
    projet."""
    from subprojects.models import sync_project_cycles

    level_ids = [i for i in level_ids if i and i > 0]
    if not level_ids:
        return 0
    already = set(project.administrative_levels.filter(id__in=level_ids).values_list('id', flat=True))
    to_add = [i for i in level_ids if i not in already]
    if to_add:
        project.administrative_levels.add(*to_add)
        sync_project_cycles(project)
    return len(to_add)
