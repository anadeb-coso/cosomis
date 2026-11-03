"""Recherche d'un niveau administratif à partir de son nom ET de sa hiérarchie.

Un nom n'identifie pas un niveau administratif : deux cantons « LOKO » existent (OTI 2 et TANDJOUARE 1), des villages
portent le même nom dans plusieurs cantons. Toute recherche par nom doit donc passer par la hiérarchie (canton,
commune, préfecture, région) et ne jamais choisir au hasard (`.first()`) entre plusieurs candidats : s'il en reste
plusieurs, la recherche est déclarée ambiguë et la ligne doit être signalée, pas enregistrée.

Les noms sont comparés sans accents, sans casse, tirets/espaces/apostrophes ignorés (« KPIMBONGA-BAS » =
« KPIMBONGA BAS »). Pour les niveaux parents (canton, commune...), une faute de frappe est tolérée
(« TANDJOARE 1 » = « TANDJOUARE 1 »), mais jamais si les numéros diffèrent (« OTI 1 » ≠ « OTI 2 », « YOUAK I » ≠
« YOUAK II »).
"""
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher

from administrativelevels.models import AdministrativeLevel

LEVEL_TYPES = (
    AdministrativeLevel.REGION, AdministrativeLevel.PREFECTURE, AdministrativeLevel.COMMUNE,
    AdministrativeLevel.CANTON, AdministrativeLevel.VILLAGE,
)
ROMAN_NUMERALS = {'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII'}
FUZZY_RATIO = 0.85

NOT_FOUND = 'not_found'
AMBIGUOUS = 'ambiguous'


def normalize_name(name):
    """« Kpimbonga-Bas » -> « KPIMBONGA BAS »."""
    name = unicodedata.normalize('NFKD', str(name or '')).encode('ascii', 'ignore').decode().upper()
    name = re.sub(r"[-_'’`.]", ' ', name)
    return re.sub(r'\s+', ' ', name).strip()


def compact_name(name):
    return normalize_name(name).replace(' ', '')


def name_numbers(name):
    """Numéros d'un nom (chiffres et chiffres romains) : « YOUAK II » -> ('II',), « OTI 2 » -> ('2',)."""
    return tuple(t for t in normalize_name(name).split(' ') if t.isdigit() or t in ROMAN_NUMERALS)


def match_by_name(name, candidates, fuzzy=False):
    """Candidats qui portent ce nom : exact, sinon normalisé, sinon (si `fuzzy`) le plus proche avec les mêmes
    numéros. Retourne (liste, 'exact' | 'normalized' | 'fuzzy' | None)."""
    candidates = list(candidates)
    matches = [c for c in candidates if c.name == name]
    if matches:
        return matches, 'exact'
    key = compact_name(name)
    if not key:
        return [], None
    matches = [c for c in candidates if compact_name(c.name) == key]
    if matches:
        return matches, 'normalized'
    if fuzzy:
        numbers = name_numbers(name)
        scored = [(SequenceMatcher(None, key, compact_name(c.name)).ratio(), c) for c in candidates if name_numbers(c.name) == numbers]
        scored = [(ratio, c) for ratio, c in scored if ratio >= FUZZY_RATIO]
        if scored:
            best = max(ratio for ratio, _ in scored)
            return [c for ratio, c in scored if ratio == best], 'fuzzy'
    return [], None


class LookupResult:
    def __init__(self, level=None, error=None, candidates=(), warnings=()):
        self.level = level
        self.error = error
        self.candidates = list(candidates)
        self.warnings = list(warnings)

    def __bool__(self):
        return self.level is not None

    def describe(self, resolver):
        if self.error == AMBIGUOUS:
            return "plusieurs correspondances : " + ", ".join(resolver.path(c) for c in self.candidates)
        if self.error == NOT_FOUND:
            return "introuvable"
        return resolver.path(self.level)


class AdministrativeLevelResolver:
    """Charge une fois tous les niveaux administratifs (imports de fichiers : une requête au lieu d'une par ligne)."""

    def __init__(self):
        self.by_id = {}
        self.by_type = defaultdict(list)
        self.children = defaultdict(list)
        for level in AdministrativeLevel.objects.only('id', 'name', 'type', 'parent_id'):
            self.add(level)

    def add(self, level):
        """À appeler pour un niveau créé pendant l'import."""
        self.by_id[level.id] = level
        self.by_type[level.type].append(level)
        self.children[level.parent_id].append(level)

    def ancestor(self, level, level_type):
        seen = set()
        while level is not None and level.id not in seen:
            if level.type == level_type:
                return level
            seen.add(level.id)
            level = self.by_id.get(level.parent_id)
        return None

    def path(self, level):
        names = []
        while level is not None and len(names) < 6:
            names.append(level.name)
            level = self.by_id.get(level.parent_id)
        return " / ".join(reversed(names))

    def child(self, parent, name, level_type, fuzzy=False):
        """Enfant de `parent` (None = racine) de ce type et de ce nom."""
        siblings = [c for c in self.children[parent.id if parent else None] if c.type == level_type]
        matches, how = match_by_name(name, siblings, fuzzy=fuzzy)
        warnings = [f"« {name} » rapproché de « {matches[0].name} »"] if how == 'fuzzy' and len(matches) == 1 else []
        if len(matches) == 1:
            return LookupResult(matches[0], warnings=warnings)
        return LookupResult(error=AMBIGUOUS if matches else NOT_FOUND, candidates=matches)

    def find(self, name, level_type, region=None, prefecture=None, commune=None, canton=None):
        """Niveau de ce type et de ce nom, départagé par les parents fournis (du plus proche au plus lointain).
        Un parent fourni dont le nom ne correspond à aucun candidat (faute de saisie) est ignoré."""
        candidates, _ = match_by_name(name, self.by_type[level_type])
        warnings = []
        for parent_type, parent_name in (
            (AdministrativeLevel.CANTON, canton), (AdministrativeLevel.COMMUNE, commune),
            (AdministrativeLevel.PREFECTURE, prefecture), (AdministrativeLevel.REGION, region),
        ):
            if not parent_name or LEVEL_TYPES.index(parent_type) >= LEVEL_TYPES.index(level_type):
                continue
            parents = {c.id: self.ancestor(c, parent_type) for c in candidates}
            matching_parents, how = match_by_name(parent_name, [p for p in parents.values() if p], fuzzy=True)
            narrowed = [c for c in candidates if parents[c.id] in matching_parents]
            if narrowed:
                candidates = narrowed
                if how == 'fuzzy':
                    warnings.append(f"« {parent_name} » rapproché de « {matching_parents[0].name} »")
            else:
                warnings.append(f"{parent_type} « {parent_name} » ignoré(e) : ne correspond à aucun parent de « {name} »")
        if len(candidates) == 1:
            return LookupResult(candidates[0], warnings=warnings)
        return LookupResult(error=AMBIGUOUS if candidates else NOT_FOUND, candidates=candidates, warnings=warnings)

    def find_or_split(self, names, level_type, separators=r"[&,;/+]| ET ", **parents):
        """Comme `find`, en essayant aussi chaque nom d'une liste « A / B ; C » : premier trouvé."""
        result = self.find(names, level_type, **parents)
        if result or result.error == AMBIGUOUS:
            return result
        for name in re.split(separators, str(names).upper()):
            if name.strip():
                result = self.find(name.strip(), level_type, **parents)
                if result:
                    return result
        return LookupResult(error=NOT_FOUND)


def find_administrative_level(name, level_type, **parents):
    """Recherche ponctuelle (hors import de fichier)."""
    return AdministrativeLevelResolver().find(name, level_type, **parents)
