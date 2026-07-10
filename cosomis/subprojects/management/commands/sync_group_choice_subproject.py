from django.core.management.base import BaseCommand, CommandError
import time
from django.db.models import Q
import pandas as pd
import re
from fuzzywuzzy import fuzz

from no_sql_client import NoSQLClient
from administrativelevels.models import AdministrativeLevel
from subprojects.models import Subproject


def normalize_text(text):
    """
    Nettoie et normalise les chaînes de caractères pour améliorer la correspondance.
    """
    if not isinstance(text, str):
        return ""
    
    text = text.upper().strip()
    
    # 1. Suppression du coût entre parenthèses (si la priorité contient un coût)
    text = re.sub(r'\s*\([^)]+\)', '', text)
    
    # 2. Suppression des verbes d'action/préfixes (essentiel pour les Priorités)
    # Les verbes d'action sont en début de chaîne, mais on les supprime partout pour sécurité.
    actions_a_supprimer = [
        "CONSTRUCTION ", "RÉALISATION ", "RÉHABILITATION ", "EXTENSION ",
        "AMÉNAGEMENT ", "ELECTRIFICATION ", "EXTENTION " # 'extention' est une faute de frappe fréquente
    ]
    for action in actions_a_supprimer:
        # On remplace l'action par un espace (pour éviter de coller deux mots)
        text = text.replace(action, " ")

    # 3. Normalisation des acronymes et variations
    text = text.replace(" AEP", " EAU DE BOISSON")
    text = text.replace(" AGRI", " MARAICHERE")
    text = text.replace(" EP", " EPP")
    text = text.replace(" PRIMAIRE", " EPP")
    text = text.replace(" CMS", " CENTRE MÉDICO-SOCIAL")
    text = text.replace(" USP", " UNITÉ DE SOINS PÉRIPHÉRIQUES")
    text = text.replace(" LYCÉE", " SECOND CYCLE DU SECONDAIRE")
    text = text.replace(" PREMIER CYCLE DU SECONDAIRE", " CEG")
    text = text.replace(" SECONDAIRE (CEG)", " CEG")
    text = text.replace(" JARDIN D'ENFANTS", " PRÉSCOLAIRE")
    text = text.replace(" JEP", " PRÉSCOLAIRE")
    text = text.replace(" PMH", " FORAGES")
    text = text.replace(" AVEC DES LAMPADAIRES SOLAIRES", " HORS RÉSEAU")
    text = text.replace(" de pistes".upper(), " Piste".upper())
    text = text.replace("Electrification avec Panneaux solaires".upper(), "Electrification hors réseau avec des lampadaires solaires".upper())
    
    if "photovoltaïque".upper() in text and "boisson".upper() in text:
        text = "Forages photovoltaïques dans les communautés pour eau de boisson".upper()
    
    if ("jardin".upper() in text and "enfant".upper() in text) or "Pré-scolaire".upper() in text:
        text = "Bâtiments scolaires au préscolaire".upper()
    
    # 4. Nettoyage final
    text = re.sub(r'\s+', ' ', text).strip() # Enlève les espaces multiples

    # Enlever les partir "dans les "
    text = text.split("DANS LES ")[0]
    
    return text

def extract_priority_description(text):
    """Extrait la description du projet en retirant le coût (entre parenthèses)."""
    if pd.isna(text):
        return ""
    # Enlève les parenthèses et ce qu'elles contiennent (le coût)
    text = re.sub(r'\s*\([^)]+\)', '', str(text)).strip()
    return text



class Command(BaseCommand):

    def check_for_valid_facilitator(self, facilitator):
        db = self.nsc.get_db(facilitator).get_query_result({
            "type": "facilitator"
        })
        for document in db:
            try:
                if not document['develop_mode'] and not document["training_mode"]:
                    return True
            except:
                return False
        return False

    def handle(self, *args, **options):
        # Your command logic here
        self.nsc = NoSQLClient()
        facilitator_dbs = self.nsc.list_all_databases('facilitator')

        village_priorities_tasks_name = [
            "Identification et établissement de la liste des besoins prioritaires pour la composante 1.1  par groupe", # COSO, FA-COSO
        ]

        for db_name in facilitator_dbs:
            if self.check_for_valid_facilitator(db_name):
                db = self.nsc.get_db(db_name).get_query_result({
                    "type": "task",
                    "phase_name": "PLANIFICATION",
                    "name": {
                        "$in": village_priorities_tasks_name
                    }
                    # "name": "Identification et établissement de la liste des besoins prioritaires pour la composante 1.1  par groupe"
                })
                for document in db:
                    update_or_create_priorities_document(document)
                
        self.stdout.write(self.style.SUCCESS('Successfully executed mycommand!'))


def process_priority_for_subprojects(administrative_level, priority, type_group: str):
    subprojects = Subproject.objects.filter(
        cvd__headquarters_village=administrative_level,
        component__name__icontains="Composante 1.1"
    )
    similarity_threshold = 60 # Seuil de confiance
    priority_clean_value = normalize_text(extract_priority_description(priority['besoinSelectionne']))
    for subproject in subprojects:
        ref_value = normalize_text(extract_priority_description(str(subproject.type_of_subproject).strip()))
        if priority_clean_value:
            score = fuzz.token_set_ratio(priority_clean_value, ref_value)
            if score >= similarity_threshold:

                if type_group == "agriculteursEtEleveurs":
                    subproject.breeders_farmers_group = True
                elif type_group == "groupeDesFemmes":
                    subproject.women_s_group = True
                elif type_group == "groupeDesJeunes":
                    subproject.youth_group = True
                elif type_group == "groupeEthniqueMinoritaires":
                    subproject.ethnic_minority_group = True
                elif type_group == "groupeDesRefugiesEtDesDeplacesInternes":
                    subproject.refugee_and_internally_displaced_persons_group = True
                
                subproject.save()

                print(f"Matched Priority: '{priority['besoinSelectionne']}' with Subproject: '{subproject.type_of_subproject}' (Score: {score}). Administrative Level ID: {administrative_level.name} ; {subproject.location_subproject_realized.name}")


def update_or_create_priorities_document(priorities_document):
    # Extract the administrative_level_id from the priorities document
    adm_id = priorities_document['administrative_level_id']
    print(adm_id)

    administrative_levels = AdministrativeLevel.objects.filter(id=adm_id)
    if administrative_levels.exists():
        administrative_level = administrative_levels.first()
        # TODO Complete Sector Allocation
        # Extract priorities from the priorities document

        if 'form_response' in priorities_document and priorities_document.get('form_response'):
            for _ in priorities_document['form_response']:
                for group in ['agriculteursEtEleveurs', 'groupeDesFemmes', 'groupeDesJeunes', 'groupeEthniqueMinoritaires', 'groupeDesRefugiesEtDesDeplacesInternes']:
                    try:
                        if group in _:
                            for idx, priority in enumerate(_[group]['besoinsPrioritairesDuGroupe']):
                                    process_priority_for_subprojects(administrative_level, priority, group)
                    except:
                        pass
            