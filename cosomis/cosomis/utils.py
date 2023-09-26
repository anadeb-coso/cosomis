import datetime

from subprojects.models import Subproject, Component, SubprojectStep, Level, Step, Project
from no_sql_client import NoSQLClient
from authentication.models import Facilitator
from administrativelevels.models import AdministrativeLevel
from assignments.models import AssignAdministrativeLevelToFacilitator
from administrativelevels.libraries.functions import strip_accents


def get_facilitators_village_liste(develop_mode=False, training_mode=False, no_sql_db=False, only_ids=True):
    administrative_levels = []
    nsc = NoSQLClient()
    if no_sql_db:
        facilitators = Facilitator.objects.using('cdd').filter(develop_mode=develop_mode, training_mode=training_mode, no_sql_db_name=no_sql_db)
    else:
        facilitators = Facilitator.objects.using('cdd').filter(develop_mode=develop_mode, training_mode=training_mode)
    for f in facilitators:
        facilitator_db = nsc.get_db(f.no_sql_db_name)
        # docs = facilitator_db.all_docs(include_docs=True)['rows']
        docs = facilitator_db.get_query_result({"type": 'facilitator'})[:]
        
        if docs:
            # for _doc in docs:
            # doc = _doc.get('doc')
            doc = facilitator_db[docs[0]['_id']]
            # if doc.get('type') == 'facilitator':
            for ad in doc.get('administrative_levels'):
                if only_ids:
                    administrative_levels.append(ad.get('id'))
                else:
                    administrative_levels.append(ad)
    return administrative_levels

def attribute_component_to_subprojects(subprojects, component):
    print("Start !")
    for subproject in subprojects:
        print(subproject.full_title_of_approved_subproject)
        subproject.component = component
        subproject.save()
    print()
    print("Done !")

def delete_administrative_levels_who_are_not_children(ads, _type):
    if _type != "Village":
        for ad in ads.filter(type=_type):
            if len(list(ad.administrativelevel_set.get_queryset())) == 0:
                ad.delete()

def delete_administrative_levels_who_are_not_attribute_to_facilitator():
    facilitators_village_liste = get_facilitators_village_liste()

    print("Start")
    print()
    ads = AdministrativeLevel.objects.all()

    print("Village")
    for ad in ads.filter(type="Village"):
        if str(ad.id) not in facilitators_village_liste:
            ad.delete()

    print("Canton")
    delete_administrative_levels_who_are_not_children(ads, "Canton")

    print("Commune")
    delete_administrative_levels_who_are_not_children(ads, "Commune")

    print("Prefecture")
    delete_administrative_levels_who_are_not_children(ads, "Prefecture")

    print("Region")
    delete_administrative_levels_who_are_not_children(ads, "Region")

    print()
    print("Done !")

def delete_administrative_levels_who_are_not_id_in_sql_db():
    nsc = NoSQLClient()
    adm_db = nsc.get_db("administrative_levels")
    docs = adm_db.all_docs(include_docs=True)['rows']
    count = 0
    for _doc in docs:
        doc = _doc.get('doc')
        if doc.get('type') == 'administrative_level' and doc.get('administrative_id') and doc.get('administrative_id') != "1":
            try:
                AdministrativeLevel.objects.get(id=int(doc.get('administrative_id')))
            except AdministrativeLevel.DoesNotExist:
                administrative_level = adm_db[doc.get('_id')]
                print(administrative_level)
                administrative_level.delete()
                count += 1
    print(count)



def attribute_project_to_subprojects(subprojects, project):
    print("Start !")
    for subproject in subprojects:
        print(subproject.full_title_of_approved_subproject)
        subproject.projects.add(project)
        subproject.save()
    print()
    print("Done !")



def save_facilitator_assignment_in_mis(project_id: int, develop_mode=False, training_mode=False, no_sql_db=False):
    print(">>> Start!")
    nsc = NoSQLClient()
    if no_sql_db:
        facilitators = Facilitator.objects.using('cdd').filter(develop_mode=develop_mode, training_mode=training_mode, no_sql_db_name=no_sql_db)
    else:
        facilitators = Facilitator.objects.using('cdd').filter(develop_mode=develop_mode, training_mode=training_mode)
    for f in facilitators:
        facilitator_db = nsc.get_db(f.no_sql_db_name)
        docs = facilitator_db.get_query_result({"type": 'facilitator'})[:]
        
        if docs:
            doc = facilitator_db[docs[0]['_id']]
            print(doc)
            for ad in doc.get('administrative_levels'):
                id_str = ad.get('id')
                if (id_str and str(id_str).isdigit() and \
                    not AssignAdministrativeLevelToFacilitator.objects.filter(administrative_level_id=int(id_str), project_id=project_id, activated=True)):
                    try:
                        assign = AssignAdministrativeLevelToFacilitator()
                        assign.administrative_level_id = int(id_str)
                        assign.facilitator_id = str(f.id)
                        assign.project_id = project_id
                        assign.save()
                    except Exception as exc:
                        print(exc)
                        input()
    print(">>> Done!")


def link_infrastures_to_subproject():
    print("Start !")
    subprojects = Subproject.objects.all().order_by('number', 'joint_subproject_number')
    for subproject in subprojects:
        for _subproject in subprojects:
            if subproject.id != _subproject.id and \
                subproject.number < _subproject.number and \
                    subproject.joint_subproject_number == _subproject.joint_subproject_number:
                print(_subproject.full_title_of_approved_subproject)
                _subproject.link_to_subproject = subproject
                _subproject.subproject_type_designation = "Infrastructure"
                _subproject.save()
    print()
    print("Done !")


def copy_cvd_to_list_of_beneficiary_villages():
    print("Start !")
    subprojects = Subproject.objects.all()
    for subproject in subprojects:
        print(subproject.full_title_of_approved_subproject)
        if subproject.cvd:
            for v in subproject.cvd.get_villages():
                subproject.list_of_beneficiary_villages.add(v)
        
        if subproject.canton:
            for v in subproject.canton.administrativelevel_set.get_queryset():
                subproject.list_of_beneficiary_villages.add(v)

        subproject.save()
    print()
    print("Done !")


def set_step(subproject, liste):
    for s in liste:
        if not subproject.check_step(s):
            subproject_step = SubprojectStep()
            subproject_step.subproject = subproject
            subproject_step.wording = s.wording
            subproject_step.percent = s.percent
            subproject_step.ranking = s.ranking
            subproject_step.step = s
            
            if subproject.approval_date_cora and s.ranking == 1: #1
                subproject_step.begin = subproject.approval_date_cora - datetime.timedelta(days=14)
            elif subproject.approval_date_cora and s.ranking in (2, 3): #2 & 3
                subproject_step.begin = subproject.approval_date_cora
            elif subproject.launch_date_of_the_construction_site_in_the_village and s.ranking == 8:# 8
                subproject_step.begin = subproject.launch_date_of_the_construction_site_in_the_village
            elif subproject.date_signature_contract_work_companies and s.ranking in (5, 6):
                if s.ranking == 6:
                    subproject_step.begin = subproject.date_signature_contract_work_companies + datetime.timedelta(days=3)
                else:
                    subproject_step.begin = subproject.date_signature_contract_work_companies
            else:
                subproject_step_current = subproject.get_current_subproject_step
                if subproject_step_current:
                    subproject_step.begin = subproject_step_current.begin + datetime.timedelta(days=7)
                elif subproject_step.ranking > 7:
                    subproject_step.begin = datetime.datetime.now().date()
                elif subproject.approval_date_cora and subproject_step.ranking <= 7:
                    subproject_step.begin = subproject.approval_date_cora + datetime.timedelta(days=3)
                else:
                    subproject_step.begin = datetime.date(2023, 1, 1)
            subproject_step.save()
    


def save_subproject_tracking():
    print("Start !")
    subprojects = Subproject.objects.all()
    sectors = []
    types = []
    step_identifie = Step.objects.get(ranking=1)
    step_not_approved = Step.objects.get(ranking=2)
    step_approved = Step.objects.get(ranking=3)
    step_dao_progress = Step.objects.get(ranking=4)
    step_company_selected = Step.objects.get(ranking=5)
    step_contract_signed = Step.objects.get(ranking=6)
    step_site_handover = Step.objects.get(ranking=7)
    step_progress = Step.objects.get(ranking=8)
    step_abandon = Step.objects.get(ranking=9)
    step_interrupted = Step.objects.get(ranking=10)
    step_completed = Step.objects.get(ranking=11)
    step_technical_acceptance = Step.objects.get(ranking=12)
    step_provisional_acceptance = Step.objects.get(ranking=13)
    step_handover_to_the_community = Step.objects.get(ranking=14)
    step_final_acceptance = Step.objects.get(ranking=15)

    for subproject in subprojects:
        if subproject.current_level_of_physical_realization_of_the_work:
            current_level = strip_accents(subproject.current_level_of_physical_realization_of_the_work).title()
            if current_level == "Remise du site".title(): #Remise du site
                print("Remise du site")
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress, 
                        step_company_selected, step_contract_signed, step_site_handover
                    ]
                )
            elif "se de validation".title() in current_level: #En phase de validation | En phse de validation
                print("En phase de validation")
                set_step(subproject, [step_identifie])
            elif "notification de l'intention d'attribution".title() in current_level: #En  phase  de notification de l'intention d'attribution  | En phse de notification de l'intention d'attribution
                print("En  phase  de notification de l'intention d'attribution")
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress, 
                        step_company_selected
                    ]
                )
            elif current_level == "Reception provisoire".title(): #Reception provisoire
                print("Reception provisoire")
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress, 
                        step_company_selected, step_contract_signed, step_site_handover,
                        step_progress, step_completed, step_technical_acceptance,
                        step_provisional_acceptance, step_handover_to_the_community
                    ]
                )
            elif current_level == "Infructueux".title(): #Infructueux
                print("Infructueux")
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress
                    ]
                )
            else:
                print("En cours")
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress, 
                        step_company_selected, step_contract_signed, step_site_handover,
                        step_progress
                    ]
                )
                print(subproject.current_level_of_physical_realization_of_the_work)
                subproject_step_progress = subproject.get_current_subproject_step
                if subproject_step_progress.step.has_levels and not subproject_step_progress.check_step(subproject.current_level_of_physical_realization_of_the_work):
                    subproject_level = Level()
                    subproject_level.wording = subproject.current_level_of_physical_realization_of_the_work
                    subproject_level.subproject_step = subproject_step_progress
                    subproject_level.percent = 35.0
                    subproject_level.begin = datetime.datetime.now().date()
                    subproject_level.save()
                
        else:
            print("Identifié")
            set_step(subproject, [step_identifie])
        
        
    print()
    print("Done !")


def all_functions_call():
    attribute_component_to_subprojects(Subproject.objects.all(), Component.objects.get(id=2))
    # attribute_project_to_subprojects(Subproject.objects.all(), Project.objects.get(id=1))
    # link_infrastures_to_subproject()
    # copy_cvd_to_list_of_beneficiary_villages()
    # save_subproject_tracking()



from django.db import connection
import logging

def set_projects_images():
    with connection.cursor() as cursor:
        try:
            cursor.execute("""
            INSERT INTO `subprojects_subprojectfile` (`id`, `created_date`, `updated_date`, `name`, `url`, `order`, `principal`, `date_taken`, `subproject_id`) VALUES
(3, '2023-04-24 10:21:53.758608', '2023-04-24 10:22:52.616677', 'Forage réception provisoire', 'https://cddfiles.s3.amazonaws.com/proof_of_work/1682080153717.jpg1682331713.4758635?AWSAccessKeyId=AKIAVNBI2LQUFQ6X2VPO&Signature=wBh6fp5Y4eah1rgQTyCXQc9QcEw%3D&Expires=1682335313', 1, 1, '2023-04-21', 748),
(4, '2023-04-24 10:23:54.968777', '2023-04-24 10:23:54.968825', 'Forage réception provisoire', 'https://cddfiles.s3.amazonaws.com/proof_of_work/1682080079370.jpg1682331834.7461157?AWSAccessKeyId=AKIAVNBI2LQUFQ6X2VPO&Signature=WeXyPtSDTibn448RmQrfIADj2oY%3D&Expires=1682335434', 2, 0, '2023-04-21', 748);
            """)
            
        except Exception as exc:
            logging.exception(exc)


    print()
    print("Done !")

