"""Import des Unités géographiques (UG) et des CVD à partir d'un fichier Excel/CSV.

Canevas : context/import_ug_cvd/exemple_ug_cvd.xlsx. Colonnes lues : Région, Préfecture, Commune, Canton,
Village/Quartier (ou Village/localité), CVD, Siège CVD, Unité géographique. Les autres colonnes sont ignorées.

Règles métier :
- une UG regroupe un ou plusieurs CVD et porte un numéro unique DANS SON CANTON : les villages d'un même canton
  portant le même numéro d'UG sont dans la même UG ;
- un CVD regroupe un ou plusieurs villages : les villages d'un même canton portant le même nom de CVD sont dans le
  même CVD ;
- « Siège CVD » vaut OUI/NON pour le village de la ligne, ou le nom du village siège (un des villages du CVD).

L'import se fait en deux temps : `build_import_plan` lit les lignes et calcule, sans rien écrire, ce qui sera créé
ou modifié (aperçu montré à l'utilisateur, avec les villages introuvables et les incohérences) ; `apply_import_plan`
enregistre ensuite le plan confirmé, dans une transaction.

Les villages ne sont jamais créés par cet import : un village du fichier absent de la base est signalé et ignoré.
Une UG dont les lignes sont incohérentes (CVD sur plusieurs numéros d'UG, village dans plusieurs CVD, plusieurs
sièges différents) est écartée entièrement : rien n'est enregistré pour elle.
"""
import csv
import io
import re
from collections import OrderedDict, defaultdict

import pandas as pd
from django.db import transaction
from django.db.models import Max
from django.utils.translation import gettext as _

from administrativelevels.functions_lookup import (
    AMBIGUOUS, AdministrativeLevelResolver, compact_name, match_by_name, normalize_name,
)
from administrativelevels.models import CVD, AdministrativeLevel, GeographicalUnit

FIELDS = ('region', 'prefecture', 'commune', 'canton', 'village', 'cvd', 'headquarters', 'unit')
# En-têtes acceptés (comparés sans accents, casse, espaces ni ponctuation).
HEADERS = {
    'region': ('REGION',),
    'prefecture': ('PREFECTURE',),
    'commune': ('COMMUNE',),
    'canton': ('CANTON',),
    'village': ('VILLAGEQUARTIER', 'VILLAGELOCALITE', 'VILLAGEOUQUARTIER', 'VILLAGE', 'LOCALITE', 'QUARTIER'),
    'cvd': ('CVD', 'NOMCVD', 'NOMDUCVD'),
    'headquarters': ('SIEGECVD', 'SIEGEDUCVD', 'SIEGE'),
    'unit': ('UNITEGEOGRAPHIQUE', 'UG', 'NUMEROUG', 'NUNITEGEOGRAPHIQUE', 'NUMEROUNITEGEOGRAPHIQUE'),
}
REQUIRED_FIELDS = ('canton', 'village', 'cvd', 'unit')
TEMPLATE_HEADERS = ('Région', 'Préfecture', 'Commune', 'Canton', 'Village/Quartier', 'CVD', 'Siège CVD', 'Unité géographique')
YES = {'OUI', 'O', 'YES', 'Y', 'X', 'VRAI', 'TRUE', '1'}
NO = {'NON', 'N', 'NO', 'FAUX', 'FALSE', '0'}


class ImportFileError(Exception):
    """Fichier illisible ou sans les colonnes obligatoires."""


def header_key(header):
    return re.sub(r'[^A-Z0-9]', '', normalize_name(header))


def clean_cell(value):
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return re.sub(r'\s+', ' ', str(value)).strip()


def map_headers(headers):
    """{champ: index de colonne} ; lève ImportFileError s'il manque une colonne obligatoire."""
    keys = [header_key(h) for h in headers]
    mapping = {}
    for field, accepted in HEADERS.items():
        for name in accepted:  # par ordre de préférence
            if name in keys:
                mapping[field] = keys.index(name)
                break
    missing = [field for field in REQUIRED_FIELDS if field not in mapping]
    if missing:
        labels = dict(zip(FIELDS, TEMPLATE_HEADERS))
        raise ImportFileError(_("Missing column(s) in the file: %(columns)s") % {
            'columns': ", ".join(labels[f] for f in missing)})
    return mapping


def rows_from_table(headers, records, first_line=2):
    """Lignes du fichier -> [{'line': n° de ligne Excel, champ: texte}], lignes entièrement vides ignorées."""
    mapping = map_headers(headers)
    rows = []
    for offset, record in enumerate(records):
        row = {'line': first_line + offset}
        for field in FIELDS:
            index = mapping.get(field)
            row[field] = clean_cell(record[index]) if index is not None and index < len(record) else ''
        if any(row[field] for field in FIELDS):
            rows.append(row)
    return rows


def read_import_file(uploaded_file, sheet_name=None):
    """Lit un fichier Excel (feuille `sheet_name`, la première par défaut) ou CSV."""
    name = (getattr(uploaded_file, 'name', '') or '').lower()
    try:
        if name.endswith('.csv'):
            content = uploaded_file.read()
            text = content.decode('utf-8-sig') if isinstance(content, bytes) else content
            try:
                dialect = csv.Sniffer().sniff(text[:4096], delimiters=',;\t')
            except csv.Error:
                dialect = csv.excel
            table = list(csv.reader(io.StringIO(text), dialect))
            if not table:
                raise ImportFileError(_("The file is empty."))
            return rows_from_table(table[0], table[1:])
        frame = pd.read_excel(uploaded_file, sheet_name=sheet_name or 0, dtype=object, header=None)
    except ImportFileError:
        raise
    except Exception as exc:
        raise ImportFileError(_("The file could not be read: %(error)s") % {'error': exc})
    table = frame.values.tolist()
    if not table:
        raise ImportFileError(_("The file is empty."))
    return rows_from_table([clean_cell(h) for h in table[0]], table[1:])


def parse_unit_number(value):
    """« 7 », « 7.0 », « UG 7 », « UG-07 » -> 7 ; None si pas de numéro."""
    value = str(value or '').strip()
    if re.fullmatch(r'\d+[.,]0*', value):
        value = re.split(r'[.,]', value)[0]
    digits = re.findall(r'\d+', value)
    return int(digits[0]) if len(digits) == 1 else None


def lines_label(lines):
    return ", ".join(str(n) for n in sorted(set(lines)))


class CvdGroup:
    def __init__(self, canton, name):
        self.canton = canton
        self.name = name
        self.entries = []  # lignes résolues (village trouvé)
        self.unit_numbers = OrderedDict()  # numéro -> lignes
        self.hq_lines = []  # (ligne, valeur brute)
        self.hq_villages = OrderedDict()  # village id -> village désigné siège
        self.headquarters = None
        self.existing = None

    @property
    def villages(self):
        return [e['village'] for e in self.entries]

    @property
    def lines(self):
        return [e['line'] for e in self.entries]


class UnitGroup:
    def __init__(self, canton, number):
        self.canton = canton
        self.number = number
        self.cvds = OrderedDict()  # clé CVD -> CvdGroup
        self.errors = []
        self.existing = None
        self.canton_path = ''
        self.remaining_villages = []  # villages déjà dans l'UG existante et absents du fichier

    @property
    def valid(self):
        return not self.errors

    @property
    def lines(self):
        return [line for cvd in self.cvds.values() for line in cvd.lines]


class ImportPlan:
    def __init__(self):
        self.rows_count = 0
        self.ignored_rows = []  # lignes sans CVD ni UG
        self.missing_villages = []  # villages introuvables (ou ambigus) : ignorés
        self.row_errors = []  # lignes incomplètes
        self.warnings = []
        self.units = []  # UnitGroup triées
        self.emptied_cvds = []  # CVD existants qui n'auront plus de village
        self.emptied_units = []  # UG existantes qui n'auront plus de village

    @property
    def valid_units(self):
        return [u for u in self.units if u.valid]

    @property
    def invalid_units(self):
        return [u for u in self.units if not u.valid]

    def warn(self, message):
        if message not in self.warnings:
            self.warnings.append(message)

    def counts(self):
        valid = self.valid_units
        cvds = [c for u in valid for c in u.cvds.values()]
        return {
            'rows': self.rows_count,
            'ignored_rows': len(self.ignored_rows),
            'missing_villages': len(self.missing_villages),
            'row_errors': len(self.row_errors),
            'units': len(valid),
            'units_to_create': len([u for u in valid if not u.existing]),
            'units_to_update': len([u for u in valid if u.existing]),
            'invalid_units': len(self.invalid_units),
            'cvds': len(cvds),
            'cvds_to_create': len([c for c in cvds if not c.existing]),
            'cvds_to_update': len([c for c in cvds if c.existing]),
            'villages': sum(len(c.entries) for c in cvds),
        }

    @property
    def can_be_applied(self):
        return bool(self.valid_units)


def build_import_plan(rows):
    """Calcule l'aperçu de l'import des lignes `rows` (voir `read_import_file`), sans rien enregistrer."""
    plan = ImportPlan()
    resolver = AdministrativeLevelResolver()
    canton_cache = {}
    units = OrderedDict()  # (canton id, numéro) -> UnitGroup
    cvds = OrderedDict()  # (canton id, nom compact) -> CvdGroup
    village_rows = defaultdict(list)  # village id -> lignes résolues

    for row in rows:
        plan.rows_count += 1
        line = row['line']
        if not row['cvd'] and not row['unit']:
            plan.ignored_rows.append(line)
            continue
        missing = [label for field, label in (('canton', 'Canton'), ('village', 'Village'), ('cvd', 'CVD'), ('unit', _('Geographical unit'))) if not row[field]]
        if missing:
            plan.row_errors.append({'line': line, 'village': row['village'], 'message': _("Missing value(s): %(fields)s") % {'fields': ", ".join(missing)}})
            continue
        number = parse_unit_number(row['unit'])
        if number is None:
            plan.row_errors.append({'line': line, 'village': row['village'], 'message': _("Invalid geographical unit number: « %(value)s »") % {'value': row['unit']}})
            continue

        # Canton, départagé par la commune, la préfecture et la région (tolère les fautes de frappe).
        key = (row['region'], row['prefecture'], row['commune'], row['canton'])
        if key not in canton_cache:
            canton_cache[key] = resolver.find(row['canton'], AdministrativeLevel.CANTON, commune=row['commune'], prefecture=row['prefecture'], region=row['region'])
        canton_result = canton_cache[key]
        if not canton_result:
            reason = (_("Canton « %(canton)s » matches several cantons: %(candidates)s") % {
                'canton': row['canton'], 'candidates': ", ".join(resolver.path(c) for c in canton_result.candidates)}
                if canton_result.error == AMBIGUOUS else _("Canton « %(canton)s » not found") % {'canton': row['canton']})
            plan.missing_villages.append(dict(row, reason=reason, suggestions=''))
            continue
        canton = canton_result.level
        for warning in canton_result.warnings:
            plan.warn(warning)

        # Village : uniquement dans ce canton, nom exact ou normalisé (pas de rapprochement approximatif).
        village_result = resolver.child(canton, row['village'], AdministrativeLevel.VILLAGE)
        if not village_result:
            siblings = [c for c in resolver.children[canton.id] if c.type == AdministrativeLevel.VILLAGE]
            close, _how = match_by_name(row['village'], siblings, fuzzy=True)
            if village_result.error == AMBIGUOUS:
                reason = _("Several villages with this name in the canton")
            else:
                reason = _("Village not found in the canton %(canton)s") % {'canton': resolver.path(canton)}
            plan.missing_villages.append(dict(row, reason=reason, suggestions=", ".join(c.name for c in close)))
            continue
        village = village_result.level

        entry = {'line': line, 'village': village, 'canton': canton, 'number': number, 'cvd_name': row['cvd'], 'headquarters': row['headquarters']}
        village_rows[village.id].append(entry)
        cvd_key = (canton.id, compact_name(row['cvd']))
        cvd = cvds.get(cvd_key)
        if cvd is None:
            cvd = cvds[cvd_key] = CvdGroup(canton, row['cvd'])
        cvd.unit_numbers.setdefault(number, []).append(line)
        if len(village_rows[village.id]) == 1:
            cvd.entries.append(entry)
        if row['headquarters']:
            cvd.hq_lines.append((line, row['headquarters'], village))

    # Rattachement de chaque CVD à son UG.
    for cvd_key, cvd in cvds.items():
        number = next(iter(cvd.unit_numbers))
        unit_key = (cvd.canton.id, number)
        if unit_key not in units:
            units[unit_key] = UnitGroup(cvd.canton, number)
        units[unit_key].cvds[cvd_key] = cvd
        if len(cvd.unit_numbers) > 1:
            detail = "; ".join(_("GU %(number)s (line(s) %(lines)s)") % {'number': n, 'lines': lines_label(l)} for n, l in cvd.unit_numbers.items())
            message = _("CVD « %(cvd)s » is given several geographical unit numbers: %(detail)s") % {'cvd': cvd.name, 'detail': detail}
            for n in cvd.unit_numbers:
                units.setdefault((cvd.canton.id, n), UnitGroup(cvd.canton, n)).errors.append(message)

    # Un village ne peut être que dans un seul CVD / une seule UG.
    for entries in village_rows.values():
        if len(entries) < 2:
            continue
        targets = {(compact_name(e['cvd_name']), e['number']) for e in entries}
        village = entries[0]['village']
        if len(targets) == 1:
            plan.warn(_("Village « %(village)s » is listed several times (lines %(lines)s): only one is kept") % {
                'village': village.name, 'lines': lines_label(e['line'] for e in entries)})
            continue
        message = _("Village « %(village)s » is placed in several CVD or geographical units (lines %(lines)s)") % {
            'village': village.name, 'lines': lines_label(e['line'] for e in entries)}
        for e in entries:
            canton = e['canton']
            units.setdefault((canton.id, e['number']), UnitGroup(canton, e['number'])).errors.append(message)
            cvd = cvds[(canton.id, compact_name(e['cvd_name']))]
            units[(canton.id, next(iter(cvd.unit_numbers)))].errors.append(message)

    # Siège de chaque CVD.
    for cvd_key, cvd in cvds.items():
        unit = units[(cvd.canton.id, next(iter(cvd.unit_numbers)))]
        villages = cvd.villages
        for line, value, row_village in cvd.hq_lines:
            flag = normalize_name(value)
            if flag in NO:
                continue
            if flag in YES:
                cvd.hq_villages[row_village.id] = row_village
                continue
            matches, _how = match_by_name(value, villages)
            if not matches:
                matches, _how = match_by_name(value, villages, fuzzy=True)
            if len(matches) == 1:
                cvd.hq_villages[matches[0].id] = matches[0]
            else:
                plan.warn(_("CVD « %(cvd)s »: headquarters « %(value)s » (line %(line)s) is not one of the villages of the CVD") % {
                    'cvd': cvd.name, 'value': value, 'line': line})
        if len(cvd.hq_villages) > 1:
            unit.errors.append(_("CVD « %(cvd)s » has several headquarters villages: %(villages)s") % {
                'cvd': cvd.name, 'villages': ", ".join(v.name for v in cvd.hq_villages.values())})
        elif cvd.hq_villages:
            cvd.headquarters = next(iter(cvd.hq_villages.values()))
        elif villages:
            same_name = [v for v in villages if compact_name(v.name) == compact_name(cvd.name)]
            cvd.headquarters = same_name[0] if same_name else villages[0]
            if len(villages) > 1 and not same_name:
                plan.warn(_("CVD « %(cvd)s »: no headquarters village given, « %(village)s » is used") % {
                    'cvd': cvd.name, 'village': cvd.headquarters.name})

    # Une UG sans aucun village trouvé n'a rien à enregistrer.
    for unit in units.values():
        for key in [k for k, c in unit.cvds.items() if not c.entries]:
            del unit.cvds[key]
    plan.units = sorted(
        [u for u in units.values() if u.cvds or u.errors],
        key=lambda u: (resolver.path(u.canton), u.number))
    for unit in plan.units:
        unit.errors = list(OrderedDict.fromkeys(unit.errors))
        unit.canton_path = resolver.path(unit.canton)

    match_existing_records(plan)
    return plan


def match_existing_records(plan):
    """Associe les UG et CVD du plan à ceux déjà en base, et repère les effets de bord (villages déplacés, CVD/UG
    existants qui se vident)."""
    canton_ids = {u.canton.id for u in plan.units}
    existing_units = {(u.canton_id, u.attributed_number_in_canton): u for u in GeographicalUnit.objects.filter(canton_id__in=canton_ids)}
    existing_cvds = defaultdict(list)
    for cvd in CVD.objects.filter(geographical_unit__canton_id__in=canton_ids).select_related('geographical_unit'):
        existing_cvds[(cvd.geographical_unit.canton_id, compact_name(cvd.name))].append(cvd)

    village_ids = [v.id for u in plan.valid_units for c in u.cvds.values() for v in c.villages]
    current = {v.id: v for v in AdministrativeLevel.objects.filter(id__in=village_ids).select_related('cvd', 'geographical_unit')}
    imported = set(village_ids)
    used_cvd_ids = set()

    for unit in plan.units:
        unit.existing = existing_units.get((unit.canton.id, unit.number))
        if not unit.valid:
            continue
        for cvd in unit.cvds.values():
            for entry in cvd.entries:
                village = current.get(entry['village'].id)
                entry['current_cvd'] = village.cvd if village else None
                entry['current_unit'] = village.geographical_unit if village else None
            # CVD existant du même canton et du même nom : celui qui a déjà le plus de villages du groupe, puis
            # celui qui est déjà dans l'UG.
            candidates = [c for c in existing_cvds.get((unit.canton.id, compact_name(cvd.name)), []) if c.id not in used_cvd_ids]
            if candidates:
                def score(candidate):
                    held = len([e for e in cvd.entries if e['current_cvd'] and e['current_cvd'].id == candidate.id])
                    in_unit = bool(unit.existing and candidate.geographical_unit_id == unit.existing.id)
                    return (held, in_unit, -candidate.id)
                cvd.existing = max(candidates, key=score)
                used_cvd_ids.add(cvd.existing.id)
            for entry in cvd.entries:
                same_cvd = bool(cvd.existing and entry['current_cvd'] and entry['current_cvd'].id == cvd.existing.id)
                same_unit = bool(unit.existing and entry['current_unit'] and entry['current_unit'].id == unit.existing.id)
                entry['status'] = 'unchanged' if same_cvd and same_unit else ('moved' if entry['current_cvd'] or entry['current_unit'] else 'new')
            if cvd.existing:
                others = AdministrativeLevel.objects.filter(cvd=cvd.existing).exclude(id__in=imported)
                for village in others:
                    plan.warn(_("Village « %(village)s » is not in the file but stays in the CVD « %(cvd)s »") % {
                        'village': village.name, 'cvd': cvd.existing.name})
        if unit.existing:
            unit.remaining_villages = list(AdministrativeLevel.objects.filter(geographical_unit=unit.existing).exclude(id__in=imported))

    # CVD et UG existants qui perdent tous leurs villages (ils ne sont pas supprimés : à vérifier par l'utilisateur).
    target_cvd_ids = {c.existing.id for u in plan.valid_units for c in u.cvds.values() if c.existing}
    target_unit_ids = {u.existing.id for u in plan.valid_units if u.existing}
    left_cvds = {v.cvd_id for v in current.values() if v.cvd_id} - target_cvd_ids
    left_units = {v.geographical_unit_id for v in current.values() if v.geographical_unit_id} - target_unit_ids
    moved_cvds = {c.existing.id: c.existing.geographical_unit_id for u in plan.valid_units for c in u.cvds.values() if c.existing}
    plan.emptied_cvds = [
        cvd for cvd in CVD.objects.filter(id__in=left_cvds).select_related('geographical_unit__canton')
        if not AdministrativeLevel.objects.filter(cvd=cvd).exclude(id__in=imported).exists()
    ]
    left_units |= set(moved_cvds.values()) - target_unit_ids
    plan.emptied_units = [
        unit for unit in GeographicalUnit.objects.filter(id__in=left_units).select_related('canton')
        if not AdministrativeLevel.objects.filter(geographical_unit=unit).exclude(id__in=imported).exists()
    ]


def next_code(model):
    """Code sur 9 chiffres, comme les UG/CVD créés à la main (pk suivant), sans doublon."""
    number = (model.objects.aggregate(m=Max('pk'))['m'] or 0) + 1
    while model.objects.filter(unique_code=str(number).zfill(9)).exists():
        number += 1
    return str(number).zfill(9)


@transaction.atomic
def apply_import_plan(plan, user=None):
    """Enregistre les UG valides du plan. Retourne les compteurs de ce qui a été fait."""
    done = {'units_created': 0, 'units_updated': 0, 'cvds_created': 0, 'cvds_updated': 0, 'villages': 0}
    for unit_plan in plan.valid_units:
        unit = unit_plan.existing
        if unit is None:
            unit = GeographicalUnit(canton_id=unit_plan.canton.id, attributed_number_in_canton=unit_plan.number, unique_code=next_code(GeographicalUnit))
            unit = unit.save_and_return_object(user=user)
            done['units_created'] += 1
        else:
            done['units_updated'] += 1
        for cvd_plan in unit_plan.cvds.values():
            cvd = CVD.objects.get(pk=cvd_plan.existing.pk) if cvd_plan.existing else CVD(name=cvd_plan.name, unique_code=next_code(CVD))
            done['cvds_updated' if cvd.pk else 'cvds_created'] += 1
            cvd.geographical_unit = unit
            cvd.headquarters_village_id = cvd_plan.headquarters.id if cvd_plan.headquarters else None
            cvd = cvd.save_and_return_object(user=user)
            for village_plan in cvd_plan.villages:
                village = AdministrativeLevel.objects.get(pk=village_plan.id)
                if village.cvd_id != cvd.id or village.geographical_unit_id != unit.id:
                    village.cvd = cvd
                    village.geographical_unit = unit
                    village.save(user=user)
                done['villages'] += 1
    return done


# --- Sérialisation pour la session (aperçu -> confirmation) ------------------------------------------------------

def rows_to_session(rows):
    return [{k: row[k] for k in ('line',) + FIELDS} for row in rows]


def missing_villages_csv(plan):
    out = io.StringIO()
    writer = csv.writer(out, delimiter=';')
    writer.writerow((_('Line'),) + TEMPLATE_HEADERS + (_('Reason'), _('Close names in the canton')))
    for row in plan.missing_villages:
        writer.writerow([row['line']] + [row[f] for f in FIELDS] + [row['reason'], row['suggestions']])
    return '﻿' + out.getvalue()


def template_workbook():
    """Canevas vide (en-têtes + une ligne d'exemple), au format xlsx."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'UG-CVD'
    sheet.append(TEMPLATE_HEADERS)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sheet.append(('CENTRALE', 'SOTOUBOUA', 'SOTOUBOUA 2', 'ADJENGRE', 'AKONTA', 'TAMPINLOGO/LOUME', 'NON', 7))
    sheet.append(('CENTRALE', 'SOTOUBOUA', 'SOTOUBOUA 2', 'ADJENGRE', 'ATCHIDE', 'TAMPINLOGO/LOUME', 'OUI', 7))
    for column, width in zip('ABCDEFGH', (14, 16, 16, 16, 22, 22, 14, 20)):
        sheet.column_dimensions[column].width = width
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
