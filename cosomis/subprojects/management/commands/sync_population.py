from django.core.management.base import BaseCommand
from no_sql_client import NoSQLClient
from administrativelevels.models import AdministrativeLevel
from subprojects.models import Subproject

class Command(BaseCommand):
    help = 'Description of your command'

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
        for db_name in facilitator_dbs:
            if self.check_for_valid_facilitator(db_name):
                db = self.nsc.get_db(db_name).get_query_result({
                    "type": "task",
                    "phase_name": "VISITES PREALABLES",
                    "name": "Etablissement du profil du village",
                })
                for document in db:
                    update_or_create_adm_document(self.nsc, document)
        self.stdout.write(self.style.SUCCESS('Successfully executed mycommand!'))

def update_or_create_adm_document(client, population_document):

    # Access the 'purs_test' database

    # Extract the administrative_level_id from the priorities document
    adm_id = population_document['administrative_level_id']

    administrative_levels = AdministrativeLevel.objects.filter(id=adm_id)
    if administrative_levels.exists():
        administrative_level = administrative_levels.first()

        extracted_population_data = None

        # Extract priorities from the priorities document
        if 'form_response' in population_document:
            extracted_population_data = extract_population_data(population_document)
            
        if not extracted_population_data:
            return

        subprojects = Subproject.objects.filter(
            cvd__headquarters_village=administrative_level,
            component__name__icontains="Composante 1.1"
        )
        
        for subproject in subprojects:
            updated = False

            if not subproject.population and extracted_population_data['population']:
                subproject.population = extracted_population_data['population']
                updated = True

            if not subproject.direct_beneficiaries_men and extracted_population_data['population_nombre_h']:
                subproject.direct_beneficiaries_men = extracted_population_data['population_nombre_h']
                updated = True

            if not subproject.direct_beneficiaries_women and extracted_population_data['population_nombre_f']:
                subproject.direct_beneficiaries_women = extracted_population_data['population_nombre_f']
                updated = True

            if updated:
                subproject.save()

            print(f"Subproject: '{subproject.type_of_subproject}'. Administrative Level ID: {administrative_level.name} ; {subproject.location_subproject_realized.name}")


def extract_population_data(form):

    old_forms = form.get('old_forms')
    old_form_response = old_forms[-1].get("form_response") if old_forms else []

    extracted_population_data = {
    'population': None,
    'population_nombre_h': None,
    'population_nombre_f': None,

    'population_refugees_young_h': None,
    'population_refugees_young_f': None,
    'population_refugees_young': None,
    'population_refugees_old_h': None,
    'population_refugees_old_f': None,
    'population_refugees_old': None,
    'population_refugees': None,

    'population_internally_displaced_persons_young_h': None,
    'population_internally_displaced_persons_young_f': None,  
    'population_internally_displaced_persons_young': None,
    'population_internally_displaced_persons_old_h': None,
    'population_internally_displaced_persons_old_f': None,
    'population_internally_displaced_persons_old': None,
    'population_internally_displaced_persons': None,

    'population_host_communities_young_h': None,
    'population_host_communities_young_f': None,
    'population_host_communities_young': None,
    'population_host_communities_old_h': None,
    'population_host_communities_old_f': None,
    'population_host_communities_old': None,
    'population_host_communities': None,

    'population_young_h': None,
    'population_young_f': None,
    'population_young': None,
    'population_old_h': None,
    'population_old_f': None,
    'population_old': None,

    'total_house_holds': None,
    'nombre_ethniques': None
    }

    if form.get('form_response'):
        extracted_population_data = extract_population_from_form_response(form['form_response'], extracted_population_data)

    if old_form_response:
        extracted_population_data = extract_population_from_form_response(old_form_response, extracted_population_data)
                

    return extracted_population_data



def extract_population_from_form_response(form_response, extracted_population_data):
    for entry in form_response:

        if "donnees" in entry and entry["donnees"]:
            extracted_population_data['population_young'] = extracted_population_data['population_young'] if extracted_population_data['population_young'] else entry["donnees"].get("populationPersonnesJeunes", {}).get("populationPersonnesJeunesTotal", 0)

        if "population" in entry and entry["population"]:
            extracted_population_data['population'] = extracted_population_data['population'] if extracted_population_data['population'] else entry["population"].get("populationTotaleDuVillage", 0)
            extracted_population_data['population_nombre_h'] = extracted_population_data['population_nombre_h'] if extracted_population_data['population_nombre_h'] else entry["population"].get("populationNombreDeHommes", 0)
            extracted_population_data['population_nombre_f'] = extracted_population_data['population_nombre_f'] if extracted_population_data['population_nombre_f'] else entry["population"].get("populationNombreDeFemmes", 0)

        if "generalitiesSurVillage" in entry and entry["generalitiesSurVillage"]:
            extracted_population_data['population'] = extracted_population_data['population'] if extracted_population_data['population'] else entry["generalitiesSurVillage"].get("populationVillage", 0)
            extracted_population_data['population_refugees_young_h'] = extracted_population_data['population_refugees_young_h'] if extracted_population_data['population_refugees_young_h'] else entry["generalitiesSurVillage"].get("totalHommesMoins35Refugie", 0)
            extracted_population_data['population_refugees_young_f'] = extracted_population_data['population_refugees_young_f'] if extracted_population_data['population_refugees_young_f'] else entry["generalitiesSurVillage"].get("totalFemmesMoins35Refugie", 0)
            extracted_population_data['population_refugees_young'] = extracted_population_data['population_refugees_young_h'] + extracted_population_data['population_refugees_young_f']
            extracted_population_data['population_refugees_old_h'] = extracted_population_data['population_refugees_old_h'] if extracted_population_data['population_refugees_old_h'] else entry["generalitiesSurVillage"].get("totalHommesPlus35Refugie", 0)
            extracted_population_data['population_refugees_old_f'] = extracted_population_data['population_refugees_old_f'] if extracted_population_data['population_refugees_old_f'] else entry["generalitiesSurVillage"].get("totalFemmesPlus35Refugie", 0)
            extracted_population_data['population_refugees_old'] = extracted_population_data['population_refugees_old_h'] + extracted_population_data['population_refugees_old_f']
            extracted_population_data['population_refugees'] = extracted_population_data['population_refugees_young'] + extracted_population_data['population_refugees_old']

            extracted_population_data['population_internally_displaced_persons_young_h'] = extracted_population_data['population_internally_displaced_persons_young_h'] if extracted_population_data['population_internally_displaced_persons_young_h'] else entry["generalitiesSurVillage"].get("totalHommesMoins35DeplaceInterne", 0)
            extracted_population_data['population_internally_displaced_persons_young_f'] = extracted_population_data['population_internally_displaced_persons_young_f'] if extracted_population_data['population_internally_displaced_persons_young_f'] else entry["generalitiesSurVillage"].get("totalFemmesMoins35DeplaceInterne", 0)
            extracted_population_data['population_internally_displaced_persons_young'] = extracted_population_data['population_internally_displaced_persons_young_h'] + extracted_population_data['population_internally_displaced_persons_young_f']
            extracted_population_data['population_internally_displaced_persons_old_h'] = extracted_population_data['population_internally_displaced_persons_old_h'] if extracted_population_data['population_internally_displaced_persons_old_h'] else entry["generalitiesSurVillage"].get("totalHommesPlus35DeplaceInterne", 0)
            extracted_population_data['population_internally_displaced_persons_old_f'] = extracted_population_data['population_internally_displaced_persons_old_f'] if extracted_population_data['population_internally_displaced_persons_old_f'] else entry["generalitiesSurVillage"].get("totalFemmesPlus35DeplaceInterne", 0)
            extracted_population_data['population_internally_displaced_persons_old'] = extracted_population_data['population_internally_displaced_persons_old_h'] + extracted_population_data['population_internally_displaced_persons_old_f']
            extracted_population_data['population_internally_displaced_persons'] = extracted_population_data['population_internally_displaced_persons_young'] + extracted_population_data['population_internally_displaced_persons_old']

            extracted_population_data['population_host_communities_young_h'] = extracted_population_data['population_host_communities_young_h'] if extracted_population_data['population_host_communities_young_h'] else entry["generalitiesSurVillage"].get("totalHommesMoins35CommunauteAcceuil", 0)
            extracted_population_data['population_host_communities_young_f'] = extracted_population_data['population_host_communities_young_f'] if extracted_population_data['population_host_communities_young_f'] else entry["generalitiesSurVillage"].get("totalFemmesMoins35CommunauteAcceuil", 0)
            extracted_population_data['population_host_communities_young'] = extracted_population_data['population_host_communities_young_h'] + extracted_population_data['population_host_communities_young_f']
            extracted_population_data['population_host_communities_old_h'] = extracted_population_data['population_host_communities_old_h'] if extracted_population_data['population_host_communities_old_h'] else entry["generalitiesSurVillage"].get("totalHommesPlus35CommunauteAcceuil", 0)
            extracted_population_data['population_host_communities_old_f'] = extracted_population_data['population_host_communities_old_f'] if extracted_population_data['population_host_communities_old_f'] else entry["generalitiesSurVillage"].get("totalFemmesPlus35CommunauteAcceuil", 0)
            extracted_population_data['population_host_communities_old'] = extracted_population_data['population_host_communities_old_h'] + extracted_population_data['population_host_communities_old_f']
            extracted_population_data['population_host_communities'] = extracted_population_data['population_host_communities_young'] + extracted_population_data['population_host_communities_old']

            extracted_population_data['population_young_h'] = extracted_population_data['population_young_h'] if extracted_population_data['population_young_h'] else entry["generalitiesSurVillage"].get("totalHommesMoins35", 0)
            extracted_population_data['population_young_h'] = extracted_population_data['population_young_h'] if extracted_population_data['population_young_h'] else (extracted_population_data['population_refugees_young_h'] + extracted_population_data['population_internally_displaced_persons_young_h'] + extracted_population_data['population_host_communities_young_h'] if extracted_population_data['population_refugees_young_h'] != None and extracted_population_data['population_internally_displaced_persons_young_h'] != None and extracted_population_data['population_host_communities_young_h'] != None else None)

            extracted_population_data['population_young_f'] = extracted_population_data['population_young_f'] if extracted_population_data['population_young_f'] else entry["generalitiesSurVillage"].get("totalFemmesMoins35", 0)
            extracted_population_data['population_young_f'] = extracted_population_data['population_young_f'] if extracted_population_data['population_young_f'] else (extracted_population_data['population_refugees_young_f'] + extracted_population_data['population_internally_displaced_persons_young_f'] + extracted_population_data['population_host_communities_young_f'] if extracted_population_data['population_refugees_young_f'] != None and extracted_population_data['population_internally_displaced_persons_young_f'] != None and extracted_population_data['population_host_communities_young_f'] != None else None)
            extracted_population_data['population_young'] = extracted_population_data['population_young'] if extracted_population_data['population_young'] else ((extracted_population_data['population_young_f'] if extracted_population_data['population_young_f'] else 0) + (extracted_population_data['population_young_h'] if extracted_population_data['population_young_h'] else 0))
            extracted_population_data['population_old_h'] = extracted_population_data['population_old_h'] if extracted_population_data['population_old_h'] else entry["generalitiesSurVillage"].get("totalHommesPlus35", 0)
            extracted_population_data['population_old_h'] = extracted_population_data['population_old_h'] if extracted_population_data['population_old_h'] else (extracted_population_data['population_refugees_old_h'] + extracted_population_data['population_internally_displaced_persons_old_h'] + extracted_population_data['population_host_communities_old_h'] if extracted_population_data['population_refugees_old_h'] != None and extracted_population_data['population_internally_displaced_persons_old_h'] != None and extracted_population_data['population_host_communities_old_h'] != None else None)

            extracted_population_data['population_old_f'] = extracted_population_data['population_old_f'] if extracted_population_data['population_old_f'] else entry["generalitiesSurVillage"].get("totalFemmesPlus35", 0)
            extracted_population_data['population_old_f'] = extracted_population_data['population_old_f'] if extracted_population_data['population_old_f'] else (extracted_population_data['population_refugees_old_f'] + extracted_population_data['population_internally_displaced_persons_old_f'] + extracted_population_data['population_host_communities_old_f'] if extracted_population_data['population_refugees_old_f'] != None and extracted_population_data['population_internally_displaced_persons_old_f'] != None and extracted_population_data['population_host_communities_old_f'] != None else None)
            extracted_population_data['population_old'] = extracted_population_data['population_old'] if extracted_population_data['population_old'] else ((extracted_population_data['population_old_f'] if extracted_population_data['population_old_f'] else 0) + (extracted_population_data['population_old_h'] if extracted_population_data['population_old_h'] else 0))

            extracted_population_data['population_nombre_h'] = extracted_population_data['population_nombre_h'] if extracted_population_data['population_nombre_h'] else (extracted_population_data['population_young_h'] + extracted_population_data['population_old_h'] if extracted_population_data['population_young_h'] != None and extracted_population_data['population_old_h'] != None else None)
            extracted_population_data['population_nombre_f'] = extracted_population_data['population_nombre_f'] if extracted_population_data['population_nombre_f'] else (extracted_population_data['population_young_f'] + extracted_population_data['population_old_f'] if extracted_population_data['population_young_f'] != None and extracted_population_data['population_old_f'] != None else None)

            extracted_population_data['total_house_holds'] = extracted_population_data['total_house_holds'] if extracted_population_data['total_house_holds'] else entry["generalitiesSurVillage"].get("totalHouseHolds", 0)
            extracted_population_data['nombre_ethniques'] = extracted_population_data['nombre_ethniques'] if extracted_population_data['nombre_ethniques'] else entry["generalitiesSurVillage"].get("nombreEthniques", 0)
    
    return extracted_population_data

