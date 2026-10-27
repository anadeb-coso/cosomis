"""Importe les types d'ouvrage depuis la feuille « priorites_ok » du fichier des priorités définies.

    python manage.py import_subproject_types [--file chemin.xlsx] [--dry-run]

- Secteur -> `sector`, Secteur bénéficiaire -> `beneficiary_sector`, Priorité -> `name` et `name_fr`,
  Certificat de donation -> `donation_certificate`, Coût estimatif -> `estimated_cost`, Unité -> `unit`,
  Regroupement -> `regroup` (SubprojectTypeRegroup). La colonne « Mobilier » est ignorée.
- Les anciens types sont fusionnés dans les nouveaux (OLD_TYPES) : leurs sous-projets sont reclassés, leur nom est
  noté dans `old_name` du nouveau type, puis l'ancien type est supprimé. Certains sont classés sous-projet par
  sous-projet (intitulé, secteur, sous-composante, coût). Les anciens types sans correspondance sont conservés.
- La commande peut être relancée : elle met à jour ce qui existe déjà.
"""
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import openpyxl
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from subprojects.models import Subproject, SubprojectSector, SubprojectType, SubprojectTypeRegroup

DEFAULT_FILE = Path(settings.BASE_DIR).parent / 'context' / 'priorities' / 'priorites_definies.1.1_vf.xlsx'
SHEET = 'priorites_ok'

# secteurs existants renommés avec le nom du fichier
SECTOR_RENAMES = {
    'Pistes': 'Piste',
    'Eau–Hydraulique': 'Hydraulique',
    'Sport–Loisir': 'Sport',
    'Developpement–a–la–Base': 'Action–sociale',
}

STORAGE_CAPACITIES = (50, 75, 100, 150, 200, 250, 350)
DEFAULT_COMMUNITY_CAPACITY = 100
DEFAULT_MARKET_CAPACITY = 75


def normalize(text):
    """Texte comparable : sans accents, en minuscules, apostrophes et espaces uniformisés."""
    text = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode()
    text = text.replace('’', "'").replace('–', ' ').lower()
    return re.sub(r'\s+', ' ', text).strip()


def clean(value):
    return re.sub(r'\s+', ' ', str(value)).strip() if value not in (None, '') else None


def context_of(subproject):
    """Intitulé, secteur et sous-composante d'un sous-projet, normalisés, pour le classer."""
    return normalize(' '.join(filter(None, [
        subproject.full_title_of_approved_subproject,
        subproject.subproject_sector_id,
        subproject.component.name if subproject.component_id else '',
    ])))


def is_market(subproject, text):
    return (subproject.subproject_sector_id == 'Commerce'
            or (subproject.component_id and '1.2' in subproject.component.name)
            or bool(re.search(r'\bmarche|\bgare\b', text)))


def street_lamps(subproject, text):
    if is_market(subproject, text):
        return 'Électrification hors réseau avec lampadaires solaires au marché'
    if re.search(r'\becole|\bepp\b|scolaire|\bceg\b|\blycee|\bjep\b', text):
        return 'Électrification hors réseau avec lampadaires solaires à l’école'
    if re.search(r'\bsante|\busp\b|\bcms\b', text):
        return 'Électrification hors réseau avec lampadaires solaires au centre de santé'
    if re.search(r'terrain|football', text):
        return 'Électrification hors réseau avec lampadaires solaires au terrain de jeux'
    return 'Électrification hors réseau avec lampadaires solaires en communauté'


def school_fence(subproject, text):
    return 'Clôture de JEP' if re.search(r'\bjep\b|jardin d.enfant', text) else 'Clôture de l’école'


def school_admin_block(subproject, text):
    return 'Bloc administratif au lycée' if 'lycee' in text else 'Bloc administratif au CEG'


def market_garden_borehole(subproject, text):
    return 'Mini-forage' if 'mini' in text else 'Forage photovoltaïque pour le maraîchage + kit maraîcher'


def waste_dump(subproject, text):
    if is_market(subproject, text):
        return 'Décharge intermédiaire au marché (dépotoir)'
    return 'Décharge intermédiaire en communauté (dépotoir)'


STORAGE = 'storage'  # magasins de stockage : classés par capacité (voir Command.classify_storage)

# ancien type -> nouveau type (nom du fichier), ou fonction(sous-projet, contexte) -> nouveau type
OLD_TYPES = {
    'Equipement de centre de santé': 'Équipement du centre de santé',
    'Bâtiment Scolaire au Pré-scolaire': 'Bâtiment scolaire préscolaire',
    'Bâtiments scolaires au préscolaire': 'Bâtiment scolaire préscolaire',
    'Bâtiment Scolaire au Primaire': 'Bâtiment scolaire primaire',
    'Bâtiments scolaires au primaire': 'Bâtiment scolaire primaire',
    'Bâtiment Scolaire au CEG': 'Bâtiment scolaire au CEG',
    'Bâtiments scolaires au premier cycle du secondaire (CEG)': 'Bâtiment scolaire au CEG',
    'Bâtiments scolaires au second cycle du secondaire (Lycée)': 'Bâtiment scolaire au lycée',
    "Bloc administratif d'école": school_admin_block,
    'Bibliothèques scolaires': 'Bibliothèque scolaire',
    'Clôtures d’école': school_fence,
    'Paillote dans les établissements scolaires pour enseignants': "Paillote à l'école",
    'Blocs de latrines dans les établissements scolaires': 'Bloc de latrines à l’école',
    'Blocs de latrines dans les marchés': 'Bloc de latrines du marché',
    'Blocs latrines dans les centres de santé': 'Bloc de latrines du centre de santé',
    'Latrine Communautaire': 'Latrines communautaires',
    'Latrines dans les terrains de football': 'Latrines du terrain de jeux',
    'Electrification hors réseau avec lampadaires solaires': street_lamps,
    'Electrification hors réseau avec des lampadaires solaires': street_lamps,
    'Extension réseau électrique': 'Extension réseau électrique en communauté (Basse tension)',
    'Extension du réseau électrique': 'Extension réseau électrique en communauté (Basse tension)',
    'Forages photovoltaïques pour les activités maraîchères': market_garden_borehole,
    'Forage Photovoltaïque (Maraichage)': market_garden_borehole,
    'Forage Photovoltaïque (Ecole)': 'Forage photovoltaïque à l’école',
    'Forages photovoltaïques dans les établissements scolaires': 'Forage photovoltaïque à l’école',
    'Réhabilitation PMH en Forage Photovoltaïque (Ecole)': 'Forage photovoltaïque à l’école',
    'PMH à réhabiliter/transformer en Forages photovoltaïques dans les établissements scolaires': 'Forage photovoltaïque à l’école',
    'Forages photovoltaïques dans les communautés pour eau de boisson': 'Forage photovoltaïque en communauté pour l’eau potable',
    'Forage Photovoltaïque (Boisson)': 'Forage photovoltaïque en communauté pour l’eau potable',
    'Forage Photovoltaïque (Centre communautaire)': 'Forage photovoltaïque du centre communautaire',
    'Forage Photovoltaïque (Salle de réunion)': 'Forage photovoltaïque de la salle de réunion',
    'Forage Photovoltaïque (Maison des jeunes)': 'Forage photovoltaïque de la maison des jeunes',
    'Forages photovoltaïques dans les marchés pour eau de boisson': 'Forage photovoltaïque au marché',
    'Réhabilitation PMH': 'PMH (Pompe à motricité humaine)',
    'Pompe à motricité humaine (PMH)': 'PMH (Pompe à motricité humaine)',
    "Extension du réseau d'eau (TDE)": 'Extension du réseau de la TdE',
    'Parking auto/moto': 'Parking automobiles',
    'Parking moto': 'Parking motos',
    'Magasin de stockage': STORAGE,
    'Magasin De Stockage': STORAGE,
    'Magasin': STORAGE,
    'Centre Communautaire': 'Centre communautaire',
    'Clôture de terrain de jeux': 'Clôture du terrain de jeux',
    'Clôture du site de maraichage': 'Clôture du site de maraîchage',
    'Clôture/Façade de marché': 'Clôture de façade du marché',
    'Clôture de Centre de santé': 'Clôture du centre de santé',
    'Clôture de centre communautaire': 'Clôture du centre communautaire',
    "Retenues d'eau": 'Retenue d’eau',
    "Retenue d'eau": 'Retenue d’eau',
    'Boutiques': 'Boutique',
    'Reboisement': 'Reboisement d’un site communautaire non boisé',
    'Logements du personnel de santé': 'Logement du personnel de santé',
    'Logements': 'Logement du centre communautaire',
    'Terrain de Foot': 'Terrain de jeux',
    'Tribune de terrain de Foot': 'Tribune',
    'Vestiaires de terrain de Foot': 'Vestiaires',
    'Vestiaires de Terrain de Foot': 'Vestiaires',
    "Local de stockage d'oxygène médical": 'Local de stockage d’oxygène',
    "Ouvrage de franchissement au niveau de la retenue d'eau": "Ponceau / dalot d’accès à la retenue d'eau",
    'Ouvrage de franchissement au niveau du centre communautaire': 'Ponceau / dalot d’accès au centre communautaire',
    'Ouvrage de franchissement au niveau du Magasin de stockage': 'Ponceau / dalot d’accès au magasin de stockage',
    'Ouvrage de franchissement au niveau du marché': 'Ponceau / dalot d’accès au marché',
    "Ouvrage de franchissement au niveau de l'établissement scolaire": 'Ponceau / dalot d’accès à l’école',
    "Ouvrage de franchissement au niveau de l'établissment scolaire": 'Ponceau / dalot d’accès à l’école',
    'Ouvrage de franchissement sur la voie publique': 'Ponceau / dalot de franchissement sur piste',
    'Pistes': 'Ponceau / dalot de franchissement sur piste',
    'Hangar de type cantonal': 'Hangars de marché (type cantonal)',
    'Hangar de Gare routière': 'Hangars de gare routière',
    'Dortoir': 'Dortoir du marché',
    'Centre Médico-Social (CMS)': 'CMS (Centre Médico-Social)',
    'Unité de soins périphériques (USP)': 'USP (Unité de soins périphériques)',
    'Paillote pour centre de santé': 'Paillote du centre de santé',
    'Incinérateurs médicaux': 'Incinérateur de déchets médicaux',
    'Bloc administratif de marché': 'Bloc administratif du marché',
    'Dépotoir': waste_dump,
    "Cantine d'Hôpital": 'Bâtiment de cantine du centre de santé',
    'Pharmacie': 'Pharmacie communautaire',
}


class Command(BaseCommand):
    help = "Importe les types d'ouvrage (feuille « priorites_ok ») et y fusionne les anciens types."

    def add_arguments(self, parser):
        parser.add_argument('--file', default=str(DEFAULT_FILE), help="Fichier Excel des priorités définies")
        parser.add_argument('--dry-run', action='store_true', help="Affiche le résultat sans rien enregistrer")

    def handle(self, *args, **options):
        path = Path(options['file'])
        if not path.exists():
            raise CommandError(f"Fichier introuvable : {path}")
        rows = self.read_rows(path)

        with transaction.atomic():
            self.rename_sectors()
            self.types_by_key = {normalize(t.name): t for t in self.import_types(rows)}
            self.merge_old_types()
            if options['dry_run']:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Simulation (--dry-run) : rien n'a été enregistré."))

    # --- lecture du fichier ---------------------------------------------------------------------------------------
    def read_rows(self, path):
        sheet = openpyxl.load_workbook(path, data_only=True, read_only=True)[SHEET]
        rows = list(sheet.iter_rows(values_only=True))
        header = [normalize(h) for h in rows[0]]
        col = {key: header.index(normalize(label)) for key, label in {
            'sector': 'Secteur', 'beneficiary_sector': 'Secteur bénéficiaire', 'name': 'Priorité',
            'donation_certificate': 'Certificat de donation', 'estimated_cost': 'Coût estimatif',
            'unit': 'Unité', 'regroup': 'Regroupement',
        }.items()}
        result, seen = [], set()
        for row in rows[1:]:
            data = {key: clean(row[index]) for key, index in col.items()}
            if not data['name']:
                continue
            if normalize(data['name']) in seen:
                raise CommandError(f"Priorité en double dans le fichier : {data['name']}")
            seen.add(normalize(data['name']))
            certificate = normalize(data['donation_certificate'])
            data['donation_certificate'] = True if certificate == 'oui' else False if certificate == 'non' else None
            cost = row[col['estimated_cost']]
            data['estimated_cost'] = float(cost) if isinstance(cost, (int, float)) else None
            result.append(data)
        return result

    # --- secteurs ---------------------------------------------------------------------------------------------------
    def rename_sectors(self):
        for old, new in SECTOR_RENAMES.items():
            sector = SubprojectSector.objects.filter(name=old).first()
            if sector and not SubprojectSector.objects.filter(name=new).exists():
                sector.name = new
                sector.save()  # renomme aussi le secteur des sous-projets
                self.stdout.write(f"Secteur renommé : {old} -> {new}")

    def sector(self, name):
        if not name:
            return None
        sector, created = SubprojectSector.objects.get_or_create(name=name)
        if created:
            self.stdout.write(f"Secteur créé : {name}")
        return sector

    # --- types du fichier ------------------------------------------------------------------------------------------
    def import_types(self, rows):
        file_names = {data['name'] for data in rows}
        exact = {t.name: t for t in SubprojectType.objects.filter(name__in=file_names)}
        # même nom à la casse, aux accents ou aux apostrophes près (et pas déjà le nom exact d'une autre priorité)
        close = {normalize(t.name): t for t in SubprojectType.objects.exclude(name__in=file_names).order_by('-pk')}
        created = updated = 0
        types = []
        for data in rows:
            subproject_type = exact.get(data['name']) or close.pop(normalize(data['name']), None) or SubprojectType()
            created += subproject_type.pk is None
            updated += subproject_type.pk is not None
            if subproject_type.pk and subproject_type.name != data['name']:
                self.stdout.write(f"Type renommé : {subproject_type.name} -> {data['name']}")
                names = [n for n in (subproject_type.old_name or '').split('; ') if n]
                subproject_type.old_name = '; '.join(names + [subproject_type.name])
            subproject_type.name = subproject_type.name_fr = data['name']
            subproject_type.sector = self.sector(data['sector'])
            subproject_type.beneficiary_sector = self.sector(data['beneficiary_sector'])
            subproject_type.regroup = SubprojectTypeRegroup.objects.get_or_create(name=data['regroup'])[0] if data['regroup'] else None
            subproject_type.donation_certificate = data['donation_certificate']
            subproject_type.estimated_cost = data['estimated_cost']
            subproject_type.unit = data['unit']
            subproject_type.save()
            types.append(subproject_type)
        self.stdout.write(f"Types du fichier : {created} créé(s), {updated} mis à jour.")
        return types

    # --- fusion des anciens types ----------------------------------------------------------------------------------
    def target(self, name):
        subproject_type = self.types_by_key.get(normalize(name))
        if subproject_type is None:
            raise CommandError(f"Type cible absent du fichier : {name}")
        return subproject_type

    def merge_old_types(self):
        old_types = SubprojectType.objects.exclude(pk__in=[t.pk for t in self.types_by_key.values()])
        storage_subprojects = []
        moves = defaultdict(list)  # (ancien type, nouveau type) -> [sous-projets]
        for old_type in old_types:
            rule = OLD_TYPES.get(old_type.name)
            subprojects = list(Subproject.objects.filter(type_of_subproject_id=old_type.name).select_related('component'))
            if rule is None:
                self.stdout.write(self.style.WARNING(f"Conservé (sans correspondance) : {old_type.name} ({len(subprojects)} sous-projet(s))"))
                continue
            if rule == STORAGE:
                storage_subprojects += subprojects
                if not subprojects:
                    old_type.delete()
                continue
            if not subprojects:  # type inutilisé : on garde la trace de son nom sur la cible fixe
                if not callable(rule):
                    moves[(old_type.name, self.target(rule).name)] += []
                else:
                    old_type.delete()
            for subproject in subprojects:
                new_name = rule(subproject, context_of(subproject)) if callable(rule) else rule
                moves[(old_type.name, self.target(new_name).name)].append(subproject)

        for subproject, new_name in self.classify_storage(storage_subprojects).items():
            moves[(subproject.type_of_subproject_id, self.target(new_name).name)].append(subproject)

        for (old_name, new_name), subprojects in sorted(moves.items()):
            Subproject.objects.filter(pk__in=[s.pk for s in subprojects]).update(type_of_subproject_id=new_name)
            self.note_old_name(old_name, new_name)
            self.stdout.write(f"{old_name} -> {new_name} : {len(subprojects)} sous-projet(s)")

        for old_name in {old for old, _ in moves}:
            if not Subproject.objects.filter(type_of_subproject_id=old_name).exists():
                SubprojectType.objects.filter(name=old_name).delete()

    def note_old_name(self, old_name, new_name):
        target = SubprojectType.objects.get(name=new_name)
        old_type = SubprojectType.objects.filter(name=old_name).first()
        names = [n for n in (target.old_name or '').split('; ') if n]
        if old_name != new_name and old_name not in names:
            names.append(old_name)
        target.old_name = '; '.join(names) or None
        if not target.color and old_type and old_type.color:
            target.color = old_type.color
        target.save(update_fields=['old_name', 'color', 'updated_date'])

    # --- magasins de stockage --------------------------------------------------------------------------------------
    def storage_cost(self, capacity, place):
        return self.target(f'Magasin de stockage {place} ({capacity} tonnes)').estimated_cost

    def closest_market_capacity(self, cost):
        priced = [(c, self.storage_cost(c, 'du marché')) for c in STORAGE_CAPACITIES]
        priced = [(c, price) for c, price in priced if price]
        return min(priced, key=lambda item: abs(item[1] - cost))[0]

    def classify_storage(self, subprojects):
        """Magasins de communauté : capacité lue dans l'intitulé (100 t par défaut). Magasins de marché : capacité
        dont le coût du fichier est le plus proche du coût estimé ; si, dans un même marché, un seul magasin porte un
        coût, ce coût est réparti entre tous ses magasins ; sinon 75 t."""
        result = {}
        markets = defaultdict(list)
        for subproject in subprojects:
            text = context_of(subproject)
            if is_market(subproject, text):
                key = (normalize(subproject.full_title_of_approved_subproject), subproject.location_subproject_realized_id)
                markets[key].append(subproject)
                continue
            capacities = [int(c) for c in re.findall(r'(\d+)\s*(?:t\b|tonne)', text) if int(c) in STORAGE_CAPACITIES]
            capacity = capacities[0] if capacities else DEFAULT_COMMUNITY_CAPACITY
            result[subproject] = f'Magasin de stockage en communauté ({capacity} tonnes)'

        for stores in markets.values():
            with_cost = [s for s in stores if s.estimated_cost]
            shared_cost = with_cost[0].estimated_cost / len(stores) if len(with_cost) == 1 and len(stores) > 1 else None
            for subproject in stores:
                if shared_cost:
                    capacity = self.closest_market_capacity(shared_cost)
                elif subproject.estimated_cost:
                    capacity = self.closest_market_capacity(subproject.estimated_cost)
                else:
                    capacity = DEFAULT_MARKET_CAPACITY
                result[subproject] = f'Magasin de stockage du marché ({capacity} tonnes)'
        return result
