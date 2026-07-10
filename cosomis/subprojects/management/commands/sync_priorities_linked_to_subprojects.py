from django.core.management.base import BaseCommand, CommandError
import time
from dateutil import parser
from no_sql_client import NoSQLClient
from cloudant.result import Result
from cloudant.document import Document
from subprojects.models import Subproject
from administrativelevels.models import AdministrativeLevel
from .sync_group_choice_subproject import normalize_text, extract_priority_description
import re
from fuzzywuzzy import fuzz

class Command(BaseCommand):
    help = 'Description of your command'

    def check_for_valid_facilitator(self, facilitator):
        db = self.nsc.get_db(facilitator).get_query_result({
            "type": "facilitator"
        })
        for document in db:
            try:
                if not document['develop_mode'] and not document["training_mode"]:
                    # print("Facilitator is valid", document)
                    return True
            except:
                return False
        return False

    def handle(self, *args, **options):
        # Your command logic here

        village_priorities_tasks_name = [
            "Soutenir la communauté dans la sélection des priorités par sous-composante (1.1, 1.2 et 1.3) à soumettre à la discussion du CCD lors de la réunion cantonale d'arbitrage", # COSO, FA-COSO
        ]

        self.nsc = NoSQLClient()
        facilitator_dbs = self.nsc.list_all_databases('facilitator')
        for db_name in facilitator_dbs:
            if self.check_for_valid_facilitator(db_name):
                # Getting only priorities tasks validated
                db = self.nsc.get_db(db_name).get_query_result({
                    "type": "task",
                    "phase_name": "PLANIFICATION",
                    "validated": True, # Get only tasks validated
                    "name": {
                        "$in": village_priorities_tasks_name
                    }
                })

                ranking_priority = {
                    "coso": 0,
                    "fa-coso": 1,
                    "purs": 2
                }
                priorities_document = sorted([document for document in db if document.get('name') in village_priorities_tasks_name], key=lambda x: ranking_priority.get(x.get("project_name", "").lower(), 99))
                
                for document in priorities_document:
                    update_or_create_priorities_document(document)
                    
        self.stdout.write(self.style.SUCCESS('Successfully executed mycommand!'))



def update_or_create_priorities_document(priorities_document):
    # Extract the administrative_level_id from the priorities document
    adm_id = priorities_document['administrative_level_id']

    administrative_levels = AdministrativeLevel.objects.filter(id=adm_id)
    if administrative_levels.exists():
        administrative_level = administrative_levels.first()

        if 'form_response' in priorities_document:

            if priorities_document.get('form_response'):

                prioritesDuVillage = None
                if 'sousComposante11' in priorities_document['form_response'][0]: # COSO, FA-COSO
                    prioritesDuVillage = priorities_document['form_response'][0]['sousComposante11']['prioritesDuVillage']

                if prioritesDuVillage:
                    for idx, priority in enumerate(prioritesDuVillage):
                        """
                            Ex. priority
                            priority = {
                                "contributionClimatique": "Réduction de l'abattage anarchique des arbres ", 
                                "coutEstime": 50000000, 
                                "nombreEstimeDeBeneficiaires": 1800, 
                                "priorite": "Autre", 
                                "proposePar": "Hommes et Femmes", 
                                "siAutreVeuillezDecrire": "Clôture de l'EPP Gando centre "
                            }
                        """

                        subprojects = Subproject.objects.filter(
                            cvd__headquarters_village=administrative_level,
                            component__name__icontains="Composante 1.1"
                        )
                        similarity_threshold = 60 # Seuil de confiance
                        priority_clean_value = normalize_text(extract_priority_description(priority["priorite"] if priority.get("priorite") != "Autre" else priority.get("siAutreVeuillezDecrire")))
                        for subproject in subprojects:

                            ref_value = normalize_text(extract_priority_description(str(subproject.type_of_subproject).strip()))
                            if priority_clean_value:
                                score = fuzz.token_set_ratio(priority_clean_value, ref_value)
                                if score >= similarity_threshold:

                                    updated = False
                                    if not subproject.priority:
                                        subproject.priority = priority
                                        updated = True

                                    if not subproject.estimated_number_of_beneficiaries and priority.get("nombreEstimeDeBeneficiaires"):
                                        subproject.estimated_number_of_beneficiaries = priority["nombreEstimeDeBeneficiaires"]
                                        updated = True

                                    if updated:
                                        subproject.save()

                                        print(f"Matched Priority: '{priority['priorite']}' with Subproject: '{subproject.type_of_subproject}' (Score: {score}). Administrative Level ID: {administrative_level.name} ; {subproject.location_subproject_realized.name}")

