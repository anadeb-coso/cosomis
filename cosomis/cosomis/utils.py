import datetime
from datetime import timedelta
from django.utils import timezone

from subprojects.models import Subproject, Component, SubprojectStep, Level, Step, Project
from no_sql_client import NoSQLClient
from authentication.models import Facilitator
from administrativelevels.models import AdministrativeLevel
from assignments.models import AssignAdministrativeLevelToFacilitator
from administrativelevels.libraries.functions import strip_accents
from cosomis.functions import normaliser_chaine
from cosomis.constants import (
    SUB_PROJECT_STATUS_COLOR, IN_PROGRESS_RANKING, IDENTIFIED_RANKING, APPROVED_BY_CORA_RANKING, 
    SELECTED_COMPANY_RANKING, NOT_APPROVED_BY_CORA_RANKING, DAO_LAUNCHED_RANKING, 
    FIRST_CONTRACT_RANKING, SITE_DISCOUNT_RANKING, ABANDONED_RANKING, INTERRUPTED_RANKING,
    COMPLETED_RANKING, RECEPTION_TECHNICAL_RANKING, PROVISIONAL_RECEPTION_RANKING,
    HANDOVER_TO_COMMUNITY_RANKING, FINAL_RECEPTION_RANKING
)


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
    print("Start attribute_component_to_subprojects!")
    for subproject in subprojects:
        # print(subproject.full_title_of_approved_subproject)
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

# `delete_administrative_levels_who_are_not_id_in_sql_db` (utilitaire manuel, jamais câblé à
# une URL/cron) supprimé : il lisait la base CouchDB `administrative_levels`, retirée du
# périmètre applicatif (MIS/MySQL `mis` reste la seule source de vérité pour ce référentiel).

def attribute_project_to_subprojects(subprojects, project):
    print("Start attribute_project_to_subprojects!")
    for subproject in subprojects:
        # print(subproject.full_title_of_approved_subproject)
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
    print("Start link_infrastures_to_subproject!")
    # subprojects = Subproject.objects.all().get_actifs().order_by('number', 'joint_subproject_number')
    # for subproject in subprojects:
    #     for _subproject in subprojects:
    #         if subproject.id != _subproject.id and \
    #             subproject.number < _subproject.number and \
    #                 subproject.joint_subproject_number == _subproject.joint_subproject_number:
    #             # print(_subproject.full_title_of_approved_subproject)
    #             _subproject.link_to_subproject = subproject
    #             _subproject.subproject_type_designation = "Infrastructure"
    #             _subproject.save()
    
    Subproject.objects.all().order_by('number', 'joint_subproject_number').update(link_to_subproject = None, subproject_type_designation = "Subproject")
    # for subproject in subprojects:
    #     subproject.link_to_subproject = None
    #     subproject.subproject_type_designation = "Subproject"
    #     subproject.save()

    subprojects = Subproject.objects.all().order_by('number', 'joint_subproject_number')
        
    for subproject in subprojects:
        if subproject.component and "1.2" in subproject.component.name:
            _subprojects = Subproject.objects.filter(
                joint_subproject_number=subproject.joint_subproject_number
            ).get_actifs().order_by('-estimated_cost')
        else:
            _subprojects = Subproject.objects.filter(
                joint_subproject_number=subproject.joint_subproject_number
            ).get_actifs().order_by('number', 'joint_subproject_number')
        if _subprojects.count() >= 2:
            _subproject = _subprojects.first()
            if _subproject.id != subproject.id:
                subproject.link_to_subproject = _subproject
                subproject.subproject_type_designation = "Infrastructure"
                subproject.save()
                
    # subprojects = Subproject.objects.all().get_actifs().order_by('number', 'joint_subproject_number')
    
    # for subproject in subprojects:
    #     _subprojects = Subproject.objects.filter(
    #         joint_subproject_number=subproject.joint_subproject_number
    #     ).get_actifs().order_by('number', 'joint_subproject_number')
    #     if _subprojects.count() >= 2:
    #         _subproject = _subprojects.first()
    #         if _subproject.id != subproject.id:
    #             subproject.link_to_subproject = _subproject
    #             subproject.subproject_type_designation = "Infrastructure"
    #             subproject.save()
    print()
    print("Done !")


def copy_cvd_to_list_of_beneficiary_villages():
    print("Start copy_cvd_to_list_of_beneficiary_villages!")
    subprojects = Subproject.objects.all()#.get_actifs()
    for subproject in subprojects:
        # print(subproject.full_title_of_approved_subproject)
        if subproject.component and subproject.component.name in ("COMPOSANTE 1.2", "COMPOSANTE 1.3") and not subproject.canton and (subproject.cvd or subproject.location_subproject_realized):
            if subproject.location_subproject_realized and subproject.location_subproject_realized.type == 'Village':
                subproject.canton = subproject.location_subproject_realized.parent
            elif subproject.cvd and subproject.cvd.headquarters_village and subproject.cvd.headquarters_village.type == 'Village':
                subproject.canton = subproject.cvd.headquarters_village.parent

        if subproject.cvd:
            for v in subproject.cvd.get_villages():
                subproject.list_of_beneficiary_villages.add(v)
        
        if subproject.canton:
            for v in subproject.canton.administrativelevel_set.get_queryset():
                subproject.list_of_beneficiary_villages.add(v)
        elif subproject.component and subproject.component in ("COMPOSANTE 1.2", "COMPOSANTE 1.3") and subproject.location_subproject_realized and subproject.location_subproject_realized.type == 'Village' and subproject.location_subproject_realized.parent:
            for v in subproject.location_subproject_realized.parent.administrativelevel_set.get_queryset():
                subproject.list_of_beneficiary_villages.add(v)

        subproject.save()
    print()
    print("Done !")


def set_step(subproject, liste):
    for s in liste:
        subproject_step = subproject.check_step(s)
        if not subproject_step:
            subproject_step = SubprojectStep()
            subproject_step.subproject = subproject
            subproject_step.wording = s.wording
            subproject_step.percent = s.percent
            subproject_step.ranking = s.ranking
            subproject_step.step = s
            
            if subproject.approval_date_cora and s.ranking == IDENTIFIED_RANKING: #1
                subproject_step.begin = subproject.approval_date_cora - datetime.timedelta(days=1)# - datetime.timedelta(days=14)
            elif subproject.approval_date_cora and s.ranking in (NOT_APPROVED_BY_CORA_RANKING, APPROVED_BY_CORA_RANKING): #2 & 3
                subproject_step.begin = subproject.approval_date_cora
            elif subproject.launch_date_of_the_construction_site_in_the_village and s.ranking == IN_PROGRESS_RANKING:# 8
                subproject_step.begin = subproject.launch_date_of_the_construction_site_in_the_village
            elif subproject.date_signature_contract_work_companies and s.ranking in (SELECTED_COMPANY_RANKING, FIRST_CONTRACT_RANKING):
                if s.ranking == FIRST_CONTRACT_RANKING:
                    subproject_step.begin = subproject.date_signature_contract_work_companies # + datetime.timedelta(days=1) #+ datetime.timedelta(days=3)
                else:
                    subproject_step.begin = subproject.date_signature_contract_work_companies - datetime.timedelta(days=1)
            elif subproject.work_completion_date and s.ranking == COMPLETED_RANKING:
                subproject_step.begin = subproject.work_completion_date
            elif subproject.date_of_technical_acceptance_of_work_contracts and s.ranking == RECEPTION_TECHNICAL_RANKING:
                subproject_step.begin = subproject.date_of_technical_acceptance_of_work_contracts
            elif subproject.date_of_provisional_acceptance_of_work_contracts and s.ranking == PROVISIONAL_RECEPTION_RANKING:
                subproject_step.begin = subproject.date_of_provisional_acceptance_of_work_contracts
            elif subproject.official_handover_date_of_the_microproject_to_the_community and s.ranking == HANDOVER_TO_COMMUNITY_RANKING:
                subproject_step.begin = subproject.official_handover_date_of_the_microproject_to_the_community
            elif subproject.date_of_final_acceptance_of_the_work and s.ranking == FINAL_RECEPTION_RANKING:
                subproject_step.begin = subproject.date_of_final_acceptance_of_the_work
            else:
                subproject_step_current = subproject.get_current_subproject_step
                if subproject_step_current:
                    subproject_step.begin = subproject_step_current.begin + datetime.timedelta(days=1) #+ datetime.timedelta(days=7)
                elif subproject_step.ranking > SITE_DISCOUNT_RANKING:
                    _date = subproject.approval_date_cora or subproject.date_signature_contract_work_companies or subproject.launch_date_of_the_construction_site_in_the_village
                    if _date:
                        subproject_step.begin = _date + datetime.timedelta(days=7)
                    else:
                        subproject_step.begin = datetime.datetime.now().date()
                elif subproject.approval_date_cora and subproject_step.ranking <= SITE_DISCOUNT_RANKING:
                    subproject_step.begin = subproject.approval_date_cora + datetime.timedelta(days=1) #+ datetime.timedelta(days=3)
                else:
                    subproject_step.begin = datetime.date(2023, 1, 1)
            subproject_step.save()
        else:
            edit = False
            
            if subproject.approval_date_cora and s.ranking in (NOT_APPROVED_BY_CORA_RANKING, APPROVED_BY_CORA_RANKING): #2 & 3
                subproject_step.begin = subproject.approval_date_cora
                edit = True
            elif subproject.launch_date_of_the_construction_site_in_the_village and s.ranking == IN_PROGRESS_RANKING:# 8
                subproject_step.begin = subproject.launch_date_of_the_construction_site_in_the_village
                edit = True
            elif subproject.date_signature_contract_work_companies and s.ranking in (SELECTED_COMPANY_RANKING, FIRST_CONTRACT_RANKING):
                if s.ranking == FIRST_CONTRACT_RANKING:
                    subproject_step.begin = subproject.date_signature_contract_work_companies
                else:
                    subproject_step.begin = subproject.date_signature_contract_work_companies - datetime.timedelta(days=1)
                edit = True
            elif subproject.work_completion_date and s.ranking == COMPLETED_RANKING:
                subproject_step.begin = subproject.work_completion_date
                edit = True
            elif subproject.date_of_technical_acceptance_of_work_contracts and s.ranking == RECEPTION_TECHNICAL_RANKING:
                subproject_step.begin = subproject.date_of_technical_acceptance_of_work_contracts
                edit = True
            elif subproject.date_of_provisional_acceptance_of_work_contracts and s.ranking == PROVISIONAL_RECEPTION_RANKING:
                subproject_step.begin = subproject.date_of_provisional_acceptance_of_work_contracts
                edit = True
            elif subproject.official_handover_date_of_the_microproject_to_the_community and s.ranking == HANDOVER_TO_COMMUNITY_RANKING:
                subproject_step.begin = subproject.official_handover_date_of_the_microproject_to_the_community
                edit = True
            elif subproject.date_of_final_acceptance_of_the_work and s.ranking == FINAL_RECEPTION_RANKING:
                subproject_step.begin = subproject.date_of_final_acceptance_of_the_work
                edit = True
            
            if edit:
                subproject_step.save()


def save_subproject_tracking(subprojects = Subproject.objects.all().get_actifs()):
    print("Start save_subproject_tracking !")
    # subprojects = Subproject.objects.all().get_actifs()
    sectors = []
    types = []
    step_identifie = Step.objects.get(ranking=IDENTIFIED_RANKING)
    step_not_approved = Step.objects.get(ranking=NOT_APPROVED_BY_CORA_RANKING)
    step_approved = Step.objects.get(ranking=APPROVED_BY_CORA_RANKING)
    step_dao_progress = Step.objects.get(ranking=DAO_LAUNCHED_RANKING)
    step_company_selected = Step.objects.get(ranking=SELECTED_COMPANY_RANKING)
    step_contract_signed = Step.objects.get(ranking=FIRST_CONTRACT_RANKING)
    step_site_handover = Step.objects.get(ranking=SITE_DISCOUNT_RANKING)
    step_progress = Step.objects.get(ranking=IN_PROGRESS_RANKING)
    step_abandon = Step.objects.get(ranking=ABANDONED_RANKING)
    step_interrupted = Step.objects.get(ranking=INTERRUPTED_RANKING)
    step_completed = Step.objects.get(ranking=COMPLETED_RANKING)
    step_technical_acceptance = Step.objects.get(ranking=RECEPTION_TECHNICAL_RANKING)
    step_provisional_acceptance = Step.objects.get(ranking=PROVISIONAL_RECEPTION_RANKING)
    step_handover_to_the_community = Step.objects.get(ranking=HANDOVER_TO_COMMUNITY_RANKING)
    step_final_acceptance = Step.objects.get(ranking=FINAL_RECEPTION_RANKING)

    for subproject in subprojects:
        level_of_physical_realization_of_the_work_percent = None
        if subproject.current_level_of_physical_realization_of_the_work or subproject.current_status_of_the_site:
            current_level = strip_accents(subproject.current_level_of_physical_realization_of_the_work if subproject.current_level_of_physical_realization_of_the_work else "").title()
            current_status_of_the_site = strip_accents(subproject.current_status_of_the_site if subproject.current_status_of_the_site else "").title()
            if (
                normaliser_chaine(current_level) == normaliser_chaine("Reception definitive") or 
                normaliser_chaine(current_status_of_the_site) == normaliser_chaine("Reception definitive") or 
                subproject.date_of_final_acceptance_of_the_work
            ): #Reception definitive
                # print("Reception definitive")
                level_of_physical_realization_of_the_work_percent = 100.0
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress, 
                        step_company_selected, step_contract_signed, step_site_handover,
                        step_progress, step_completed, step_technical_acceptance,
                        step_provisional_acceptance, step_handover_to_the_community,
                        step_final_acceptance
                    ]
                )
            elif (subproject.official_handover_date_of_the_microproject_to_the_community): #Remise de l'ouvrage à la communauté
                # print("Reception provisoire")
                level_of_physical_realization_of_the_work_percent = 100.0
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress, 
                        step_company_selected, step_contract_signed, step_site_handover,
                        step_progress, step_completed, step_technical_acceptance,
                        step_provisional_acceptance, step_handover_to_the_community
                    ]
                )
            elif (
                normaliser_chaine(current_level) == normaliser_chaine("Reception provisoire") or normaliser_chaine(current_status_of_the_site) == normaliser_chaine("Reception provisoire") or 
                subproject.date_of_provisional_acceptance_of_work_contracts
            ): #Reception provisoire
                # print("Reception provisoire")
                level_of_physical_realization_of_the_work_percent = 100.0
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress, 
                        step_company_selected, step_contract_signed, step_site_handover,
                        step_progress, step_completed, step_technical_acceptance,
                        step_provisional_acceptance
                    ]
                )
            elif (
                normaliser_chaine(current_level) == normaliser_chaine("Reception technique") or normaliser_chaine(current_status_of_the_site) == normaliser_chaine("Reception technique") or 
                subproject.date_of_technical_acceptance_of_work_contracts
            ): #Reception technique
                # print("Reception technique")
                level_of_physical_realization_of_the_work_percent = 100.0
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress, 
                        step_company_selected, step_contract_signed, step_site_handover,
                        step_progress, step_completed, step_technical_acceptance
                    ]
                )
            elif (
                normaliser_chaine(current_level) in (normaliser_chaine("Acheve"), normaliser_chaine("Acheve non receptionne")) or 
                normaliser_chaine(current_status_of_the_site)  in (normaliser_chaine("Acheve"), normaliser_chaine("Acheve non receptionne")) or subproject.work_completion_date
            ): #Acheve
                # print("Acheve")
                level_of_physical_realization_of_the_work_percent = 100.0
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress, 
                        step_company_selected, step_contract_signed, step_site_handover,
                        step_progress, step_completed
                    ]
                )
            elif normaliser_chaine(current_level) == normaliser_chaine("Remise du site") or normaliser_chaine(current_status_of_the_site) == normaliser_chaine("Remise du site"): #Remise du site
                # print("Remise du site")
                level_of_physical_realization_of_the_work_percent = 0.0
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress, 
                        step_company_selected, step_contract_signed, step_site_handover
                    ]
                )
            elif normaliser_chaine("se de validation") in normaliser_chaine(current_level) or normaliser_chaine("se de validation") in normaliser_chaine(current_status_of_the_site): #En phase de validation | En phse de validation
                # print("En phase de validation")
                level_of_physical_realization_of_the_work_percent = 0.0
                set_step(subproject, [step_identifie])
            elif normaliser_chaine("notification de l'intention d'attribution") in normaliser_chaine(current_level) or normaliser_chaine("notification de l'intention d'attribution") in normaliser_chaine(current_status_of_the_site): #En  phase  de notification de l'intention d'attribution  | En phse de notification de l'intention d'attribution
                # print("En  phase  de notification de l'intention d'attribution")
                level_of_physical_realization_of_the_work_percent = 0.0
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress, 
                        step_company_selected
                    ]
                )
            elif normaliser_chaine(current_level) == normaliser_chaine("Infructueux") or normaliser_chaine(current_status_of_the_site) == normaliser_chaine("Infructueux"): #Infructueux
                # print("Infructueux")
                level_of_physical_realization_of_the_work_percent = 0.0
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress
                    ]
                )
            elif normaliser_chaine(current_level) == normaliser_chaine("Arret travaux") or normaliser_chaine(current_status_of_the_site) == normaliser_chaine("Arret travaux"):
                # print("Arrêt travaux")
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress, 
                        step_company_selected, step_contract_signed, step_site_handover,
                        step_progress, step_interrupted
                    ]
                )
            elif normaliser_chaine(current_level) == normaliser_chaine("En cours") or normaliser_chaine(current_status_of_the_site) == normaliser_chaine("En cours"):
                # print("En cours")
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress, 
                        step_company_selected, step_contract_signed, step_site_handover,
                        step_progress
                    ]
                )
                
                _percent = 0.0
                _current_level_of_physical_realization_of_the_works = subproject.current_level_of_physical_realization_of_the_work.split("%") if subproject.current_level_of_physical_realization_of_the_work else []
                if _current_level_of_physical_realization_of_the_works:
                    _current_level_of_physical_realization_of_the_work = _current_level_of_physical_realization_of_the_works[0]
                    if not _current_level_of_physical_realization_of_the_work \
                            or not str(_current_level_of_physical_realization_of_the_work).replace('.','',1).replace(',','',1).isdigit():
                        _percent = 0.0
                    else:
                        _percent = float(_current_level_of_physical_realization_of_the_work.replace(',', '0'))
                # print(_percent)
                subproject_step_progress = subproject.get_current_subproject_step
                # if subproject_step_progress.step.has_levels and not subproject_step_progress.check_step(subproject.current_level_of_physical_realization_of_the_work):
                if subproject_step_progress.step.has_levels:
                    level = subproject_step_progress.get_levels().first()
                    if (level and _percent > level.percent) or not level:
                        subproject_level = Level()
                        subproject_level.wording = "En cours"
                        subproject_level.subproject_step = subproject_step_progress
                        subproject_level.percent = _percent
                        subproject_level.begin = datetime.datetime.now().date()
                        subproject_level.save()
                        level_of_physical_realization_of_the_work_percent = _percent
            else:
                if subproject.date_of_final_acceptance_of_the_work:
                    # print("Reception definitive")
                    level_of_physical_realization_of_the_work_percent = 100.0
                    set_step(
                        subproject, 
                        [
                            step_identifie, step_approved, step_dao_progress, 
                            step_company_selected, step_contract_signed, step_site_handover,
                            step_progress, step_completed, step_technical_acceptance,
                            step_provisional_acceptance, step_handover_to_the_community,
                            step_final_acceptance
                        ]
                    )
                elif subproject.official_handover_date_of_the_microproject_to_the_community:
                    # print("Remise de l'ouvrage à la commuanuté")
                    level_of_physical_realization_of_the_work_percent = 100.0
                    set_step(
                        subproject, 
                        [
                            step_identifie, step_approved, step_dao_progress, 
                            step_company_selected, step_contract_signed, step_site_handover,
                            step_progress, step_completed, step_technical_acceptance,
                            step_provisional_acceptance, step_handover_to_the_community
                        ]
                    )
                elif subproject.date_of_provisional_acceptance_of_work_contracts:
                    # print("Reception provisoire")
                    level_of_physical_realization_of_the_work_percent = 100.0
                    set_step(
                        subproject, 
                        [
                            step_identifie, step_approved, step_dao_progress, 
                            step_company_selected, step_contract_signed, step_site_handover,
                            step_progress, step_completed, step_technical_acceptance,
                            step_provisional_acceptance
                        ]
                    )
                elif subproject.date_of_technical_acceptance_of_work_contracts:
                    # print("Reception technique")
                    level_of_physical_realization_of_the_work_percent = 100.0
                    set_step(
                        subproject, 
                        [
                            step_identifie, step_approved, step_dao_progress, 
                            step_company_selected, step_contract_signed, step_site_handover,
                            step_progress, step_completed, step_technical_acceptance
                        ]
                    )
                elif subproject.work_completion_date:
                    # print("Acheve")
                    level_of_physical_realization_of_the_work_percent = 100.0
                    set_step(
                        subproject, 
                        [
                            step_identifie, step_approved, step_dao_progress, 
                            step_company_selected, step_contract_signed, step_site_handover,
                            step_progress, step_completed
                        ]
                    )
                elif subproject.date_signature_contract_work_companies:
                    # print("Contrat signé")
                    level_of_physical_realization_of_the_work_percent = 0.0
                    set_step(subproject, [
                        step_identifie, step_approved, step_dao_progress, 
                        step_company_selected, step_contract_signed
                        ]
                    )
                elif subproject.approval_date_cora:
                    # print("Approuvé")
                    level_of_physical_realization_of_the_work_percent = 0.0
                    set_step(subproject, [step_identifie, step_approved])
                else:
                    # print("Non entamé")
                    level_of_physical_realization_of_the_work_percent = 0.0
                    set_step(subproject, [step_identifie])
        else:
            if subproject.date_of_final_acceptance_of_the_work:
                # print("Reception definitive")
                level_of_physical_realization_of_the_work_percent = 100.0
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress, 
                        step_company_selected, step_contract_signed, step_site_handover,
                        step_progress, step_completed, step_technical_acceptance,
                        step_provisional_acceptance, step_handover_to_the_community,
                        step_final_acceptance
                    ]
                )
            if subproject.official_handover_date_of_the_microproject_to_the_community:
                # print("Remise de l'ouvrage à la commuanuté")
                level_of_physical_realization_of_the_work_percent = 100.0
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress, 
                        step_company_selected, step_contract_signed, step_site_handover,
                        step_progress, step_completed, step_technical_acceptance,
                        step_provisional_acceptance, step_handover_to_the_community
                    ]
                )
            elif subproject.date_of_provisional_acceptance_of_work_contracts:
                # print("Reception provisoire")
                level_of_physical_realization_of_the_work_percent = 100.0
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress, 
                        step_company_selected, step_contract_signed, step_site_handover,
                        step_progress, step_completed, step_technical_acceptance,
                        step_provisional_acceptance
                    ]
                )
            elif subproject.date_of_technical_acceptance_of_work_contracts:
                # print("Reception technique")
                level_of_physical_realization_of_the_work_percent = 100.0
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress, 
                        step_company_selected, step_contract_signed, step_site_handover,
                        step_progress, step_completed, step_technical_acceptance
                    ]
                )
            elif subproject.work_completion_date:
                # print("Acheve")
                level_of_physical_realization_of_the_work_percent = 100.0
                set_step(
                    subproject, 
                    [
                        step_identifie, step_approved, step_dao_progress, 
                        step_company_selected, step_contract_signed, step_site_handover,
                        step_progress, step_completed
                    ]
                )
            elif subproject.date_signature_contract_work_companies:
                # print("Contrat signé")
                level_of_physical_realization_of_the_work_percent = 0.0
                set_step(subproject, [
                    step_identifie, step_approved, step_dao_progress, 
                    step_company_selected, step_contract_signed
                    ]
                )
            elif subproject.approval_date_cora:
                # print("Approuvé")
                level_of_physical_realization_of_the_work_percent = 0.0
                set_step(subproject, [step_identifie, step_approved])
            else:
                # print("Identifié")
                level_of_physical_realization_of_the_work_percent = 0.0
                set_step(subproject, [step_identifie])
        
        if level_of_physical_realization_of_the_work_percent != None:
            subproject.current_level_of_physical_realization_of_the_work_percent = level_of_physical_realization_of_the_work_percent
            subproject.current_level_of_physical_realization_of_the_work_wording = subproject.get_current_subproject_step_and_level_without_percent
    print()
    print("Done !")


# def all_functions_call():
#     print("attribute_component_to_subprojects")
#     attribute_component_to_subprojects(Subproject.objects.all(), Component.objects.get(id=2))
#     print("attribute_project_to_subprojects")
#     attribute_project_to_subprojects(Subproject.objects.all(), Project.objects.get(id=1))
#     print("link_infrastures_to_subproject")
#     link_infrastures_to_subproject()
#     print("copy_cvd_to_list_of_beneficiary_villages")
#     copy_cvd_to_list_of_beneficiary_villages()
#     print("save_subproject_tracking")
#     save_subproject_tracking()



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



# def delete_subproject_step_training():
#     start_date = timezone.make_aware(datetime.datetime(2023, 12, 15), timezone=timezone.get_current_timezone())
#     end_date = timezone.make_aware(datetime.datetime(2024, 3, 18), timezone=timezone.get_current_timezone())
    
#     objects_within_period = SubprojectStep.objects.filter(created_date__range=[start_date, end_date])
#     print(objects_within_period.count())
#     objects_within_period.delete()
    
#     objects_within_period = SubprojectStep.objects.filter(updated_date__range=[start_date, end_date])
#     print(objects_within_period.count())
#     objects_within_period.delete()
    
def change_subproject_attr_val_non_entame_to_identifie():
    print("Start change_subproject_attr_val_non_entame_to_identifie!")
    subprojects = Subproject.objects.filter(current_status_of_the_site='Non entamé')
    for subproject in subprojects:
        # print(subproject.full_title_of_approved_subproject)
        subproject.current_status_of_the_site = "Identifié"
        subproject.save()
    print()
    print("Done !")


def fill_current_level_of_physical_realization_of_the_work_wording():
    print("Start fill_current_level_of_physical_realization_of_the_work_wording!")
    subprojects = Subproject.objects.all().get_actifs()
    for subproject in subprojects:
        step_level = subproject.get_current_subproject_step_and_level_object
        subproject.current_level_of_physical_realization_of_the_work_percent = step_level.percent if step_level and step_level.percent else 0.0

        subproject.current_level_of_physical_realization_of_the_work_wording = subproject.get_current_subproject_step_and_level_without_percent
        
        subproject.save()
    print()
    print("Done !")


def change_subproject_attr_val_entreprise_selectionne_to_entreprise_selectionnee():
    print("Start change_subproject_attr_val_entreprise_selectionne_to_entreprise_selectionnee!")

    vals_edits = {
        'Non approuvé': "Non approuvé par le CORA",
        'Approuvé': "Approuvé par le CORA",
        'Entreprise sélectionné': "Entreprise sélectionnée",
        'Entreprise sélectionné': "Entreprise retenue",
        'Entreprise sélectionnée': "Entreprise retenue"
    }

    for old_val, new_val in vals_edits.items():
        Subproject.objects.filter(current_status_of_the_site=old_val).update(current_status_of_the_site=new_val)
        Step.objects.filter(wording=old_val).update(wording=new_val)
        SubprojectStep.objects.filter(wording=old_val).update(wording=new_val)

    # set color for Step
    for step, color_step in SUB_PROJECT_STATUS_COLOR.items():
        Step.objects.filter(wording=step).update(color=color_step)

    print()
    print("Done !")






# def save_csv_datas_subprojects_in_db(datas_file: dict, cvd_ids=[], canton_ids=[]) -> str:
#     """Function to save the CSV datas in database"""
    
   
#     if datas_file:
#         print(datas_file.keys())
#         count = 0
#         long = len(list(datas_file.values())[0])
#         while count < long:
        
            
#             try:
                
                
#                 # for village in __village.split("/"):
#                 # village = village.strip()
#                 village = __village.strip()
#                 _is_object_error = False
#                 is_link_to_subproject = False
#                 subproject_to_link = None
#                 administrative_level = None
#                 administrative_level_canton = None
#                 subproject = None
                
#                 if not _is_object_error:
                    
#                     if administrative_level and ((cvd_ids and administrative_level.cvd_id not in cvd_ids) or (canton_ids and administrative_level.cvd_id not in canton_ids)):
#                         continue #Continue without save the object if the cvd ids or the cantan ids are specific and their village current is different
                    
#                     estimated_cost = float(estimated_cost) if estimated_cost else 0.0
                    
#                     # _list_chars = column.split(" ")
#                     # for char in _list_chars:
#                     #     if char in list(_components.keys()):
#                     #         _list_data = str(data).split("-")
#                     #         if _list_data[0].isdigit():
#                     #             name_priority = (str(data)[(len(_list_data[0])+1):]).strip()
#                     #         else:
#                     #             name_priority = str(data).strip()
#                     #         try:
#                     #             component = Component.objects.get(name=_components[char].upper())
#                     #         except Exception as exc:
#                     #             component = None

#                     if village in ("CCD", "TOUTE LA COMMUNAUTE"):
#                         subprojects = Subproject.objects.filter(
#                             number=number
#                             # full_title_of_approved_subproject=full_title_of_approved_subproject
#                             )#.get_actifs()
#                         canton = get_value(datas_file["CANTON"][count])
                        
                        

#                     else:
#                         subprojects = Subproject.objects.filter(
#                             number=number
#                             # full_title_of_approved_subproject=full_title_of_approved_subproject,
#                             # location_subproject_realized=administrative_level, 
#                             # subproject_sector=subproject_sector,
#                             # type_of_subproject=type_of_subproject
#                             )#.get_actifs()
#                         # if subproject:
#                         #     subproject = list(subproject)[0]
#                         if number in (48, 375, 480, 526):
#                             print("===============================================================================")
#                             print(type(number))
#                             print(subprojects)
#                         subproject = subprojects.first()

#                     # if is_link_to_subproject:
#                     #     subproject_to_link = copy.copy(subproject)
#                     #     subproject = None

#                     if not subproject:
#                         subproject = Subproject()
#                         # subproject.link_to_subproject = subproject_to_link
#                     try:
#                         _expected_duration_of_the_work = float(str(expected_duration_of_the_work).split(' ')[0].split('m')[0].split('M')[0])
#                     except:
#                         _expected_duration_of_the_work = None
                    
                    
#                     _current_level_of_physical_realization_of_the_works = str(current_level_of_physical_realization_of_the_work).split("%")
#                     if _current_level_of_physical_realization_of_the_works:
#                         _current_level_of_physical_realization_of_the_work = _current_level_of_physical_realization_of_the_works[0]
#                         if not _current_level_of_physical_realization_of_the_work \
#                                 or not str(_current_level_of_physical_realization_of_the_work).replace('.','',1).replace(',','',1).isdigit():
#                             _current_level_of_physical_realization_of_the_work = current_level_of_physical_realization_of_the_work
#                         else:
#                             _current_level_of_physical_realization_of_the_work = float(_current_level_of_physical_realization_of_the_work.replace(',', '0')) * 100
#                     else:
#                         _current_level_of_physical_realization_of_the_work = current_level_of_physical_realization_of_the_work

#                     subproject.location_subproject_realized = administrative_level
#                     subproject.number = number
#                     subproject.joint_subproject_number = joint_subproject_number
#                     # subproject.intervention_unit = intervention_unit #
#                     if facilitator_name:
#                         subproject.facilitator_name = facilitator_name
#                     if wave:
#                         subproject.wave = wave
#                     if lot:
#                         subproject.lot = lot
#                     if subproject_sector:
#                         subproject.subproject_sector = subproject_sector
#                     if type_of_subproject:
#                         subproject.type_of_subproject = type_of_subproject
#                     if full_title_of_approved_subproject:
#                         if str(full_title_of_approved_subproject).upper() != str(subproject.full_title_of_approved_subproject).upper():
#                             subproject.infrastructure_changed = True
#                         subproject.full_title_of_approved_subproject = full_title_of_approved_subproject
#                     if works_type:
#                         subproject.works_type = works_type
#                     if estimated_cost:
#                         subproject.estimated_cost = estimated_cost
#                     if level_of_achievement_donation_certificate:
#                         subproject.level_of_achievement_donation_certificate = level_of_achievement_donation_certificate
#                     if approval_date_cora:
#                         subproject.approval_date_cora = approval_date_cora
#                     if date_of_signature_of_contract_for_construction_supervisors:
#                         subproject.date_of_signature_of_contract_for_construction_supervisors = date_of_signature_of_contract_for_construction_supervisors
#                     if amount_of_the_contract_for_construction_supervisors:
#                         subproject.amount_of_the_contract_for_construction_supervisors = amount_of_the_contract_for_construction_supervisors
#                     if date_signature_contract_controllers_in_SES:
#                         subproject.date_signature_contract_controllers_in_SES = date_signature_contract_controllers_in_SES
#                     if amount_of_the_controllers_contract_in_SES:
#                         subproject.amount_of_the_controllers_contract_in_SES = amount_of_the_controllers_contract_in_SES
#                     if convention:
#                         subproject.convention = convention
#                     if contract_number_of_work_companies:
#                         subproject.contract_number_of_work_companies = contract_number_of_work_companies
#                     if name_of_the_awarded_company_works_companies:
#                         subproject.name_of_the_awarded_company_works_companies = name_of_the_awarded_company_works_companies
#                     if date_signature_contract_work_companies:
#                         subproject.date_signature_contract_work_companies = date_signature_contract_work_companies
#                     if contract_amount_work_companies:
#                         subproject.contract_amount_work_companies = contract_amount_work_companies
#                     if name_of_company_awarded_efme:
#                         subproject.name_of_company_awarded_efme = name_of_company_awarded_efme
#                     if date_signature_contract_efme:
#                         subproject.date_signature_contract_efme = date_signature_contract_efme
#                     if contract_companies_amount_for_efme:
#                         subproject.contract_companies_amount_for_efme = contract_companies_amount_for_efme
#                     if date_signature_contract_facilitator:
#                         subproject.date_signature_contract_facilitator = date_signature_contract_facilitator
#                     if amount_of_the_facilitator_contract:
#                         subproject.amount_of_the_facilitator_contract = amount_of_the_facilitator_contract
#                     if launch_date_of_the_construction_site_in_the_village:
#                         subproject.launch_date_of_the_construction_site_in_the_village = launch_date_of_the_construction_site_in_the_village
#                     if _current_level_of_physical_realization_of_the_work:
#                         subproject.current_level_of_physical_realization_of_the_work = _current_level_of_physical_realization_of_the_work
#                         # _physical_level = str(current_level_of_physical_realization_of_the_work).split(".")[0].split(",")[0]
#                         # if _physical_level.isdigit():
#                         #     subproject.current_level_of_physical_realization_of_the_work_percent = float(_physical_level)
#                         # subproject.current_level_of_physical_realization_of_the_work_wording = subproject.get_current_subproject_step_and_level_without_percent
#                     if length_of_the_track:
#                         subproject.length_of_the_track = length_of_the_track
#                     if depth_of_drilling:
#                         subproject.depth_of_drilling = depth_of_drilling
#                     if drilling_flow_rate:
#                         subproject.drilling_flow_rate = drilling_flow_rate
#                     if current_status_of_the_site:
#                         subproject.current_status_of_the_site = current_status_of_the_site
#                     if _expected_duration_of_the_work:
#                         subproject.expected_duration_of_the_work = _expected_duration_of_the_work
#                     if expected_end_date_of_the_contract:
#                         subproject.expected_end_date_of_the_contract = expected_end_date_of_the_contract
#                     if total_contract_amount_paid:
#                         subproject.total_contract_amount_paid = total_contract_amount_paid
#                     if amount_of_the_care_and_maintenance_fund_expected_to_be_mobilized:
#                         subproject.amount_of_the_care_and_maintenance_fund_expected_to_be_mobilized = amount_of_the_care_and_maintenance_fund_expected_to_be_mobilized
#                     if care_and_maintenance_amount_on_village_account:
#                         subproject.care_and_maintenance_amount_on_village_account = care_and_maintenance_amount_on_village_account
#                     if existence_of_maintenance_and_upkeep_plan_developed_by_community != None:
#                         subproject.existence_of_maintenance_and_upkeep_plan_developed_by_community = bool(existence_of_maintenance_and_upkeep_plan_developed_by_community) if existence_of_maintenance_and_upkeep_plan_developed_by_community else False
#                     if work_completion_date:
#                         subproject.work_completion_date = work_completion_date
#                     if date_of_technical_acceptance_of_work_contracts:
#                         subproject.date_of_technical_acceptance_of_work_contracts = date_of_technical_acceptance_of_work_contracts
#                     if technical_acceptance_date_for_efme_contracts:
#                         subproject.technical_acceptance_date_for_efme_contracts = technical_acceptance_date_for_efme_contracts
#                     if date_of_provisional_acceptance_of_work_contracts:
#                         subproject.date_of_provisional_acceptance_of_work_contracts = date_of_provisional_acceptance_of_work_contracts
#                     if provisional_acceptance_date_for_efme_contracts:
#                         subproject.provisional_acceptance_date_for_efme_contracts = provisional_acceptance_date_for_efme_contracts
#                     if official_handover_date_of_the_microproject_to_the_community:
#                         subproject.official_handover_date_of_the_microproject_to_the_community = official_handover_date_of_the_microproject_to_the_community
#                     if official_handover_date_of_the_microproject_to_the_sector:
#                         subproject.official_handover_date_of_the_microproject_to_the_sector = official_handover_date_of_the_microproject_to_the_sector
#                     # subproject.comments = comments
#                     if longitude and latitude:
#                         subproject.latitude = latitude
#                         subproject.longitude = longitude
                    
#                     if women_s_group != None:
#                         subproject.women_s_group = bool(women_s_group)
#                     if youth_group != None:
#                         subproject.youth_group = bool(youth_group)
#                     if breeders_farmers_group != None:
#                         subproject.breeders_farmers_group = bool(breeders_farmers_group)
#                     if ethnic_minority_group != None:
#                         subproject.ethnic_minority_group = bool(ethnic_minority_group)
                        
#                     if number_of_classrooms != None:
#                         subproject.number_of_classrooms = number_of_classrooms

#                     if infrastructure_changed not in (False, True, None):
#                         subproject.infrastructure_changed = True if str(infrastructure_changed).upper() in ("OUI", "1") else False
#                     if infrastructure_deleted not in (False, True, None):
#                         subproject.infrastructure_deleted = True if str(infrastructure_deleted).upper() in ("OUI", "1") else False
                    

#                     subproject = subproject.save_and_return_object()
                    
#                     if village in ("CCD", "TOUTE LA COMMUNAUTE") and administrative_level_canton:
#                         subproject.canton = administrative_level_canton

#                         if list_of_villages_crossed_by_the_track_or_electrification:
#                             liste = [word.strip() for word in re_module.split(r"/|,|;|\+|\bet\b|-", str(list_of_villages_crossed_by_the_track_or_electrification)) if word.strip()] #str(list_of_villages_crossed_by_the_track_or_electrification).split(";")
#                             for ad_name in liste:
#                                 ad = get_adminstrative_level_by_name(ad_name.strip(), canton_file_data)
#                                 if ad:
#                                     subproject.list_of_villages_crossed_by_the_track_or_electrification.add(ad)
                        
#                     elif administrative_level and administrative_level.cvd:
#                         subproject.cvd  = administrative_level.cvd
                    

#                     subproject.save(user={'is_superuser': True})


#             except Exception as exc:
#                 exc_type, exc_obj, exc_tb = sys.exc_info()
#                 fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
#                 text_errors += f'\nLine N°{count} [{_village}]: {exc.__str__()}, {exc_type}, {fname}, {exc_tb.tb_lineno}'
#                 nbr_other_errors += 1
#                 at_least_one_error = True
#                 print(exc)

#             count += 1
#             # if count == 1:
#             #     break
#     print(count)
    
#     subprojects = Subproject.objects.all()#.get_actifs()
#     link_infrastures_to_subproject() #Link each infrastructure to their subproject
#     copy_cvd_to_list_of_beneficiary_villages() #Link villages to theirs subprojects
#     attribute_project_to_subprojects(
#         subprojects, Project.objects.get(id=1)
#     ) #Link projects to COSO project
#     attribute_component_to_subprojects(
#         subprojects, Component.objects.get(id=2)
#     ) #Link projects to Component 1.1
    
#     save_subproject_tracking() #Update Subproject Step-level
    
    
#     return True


# from subprojects.models import Subproject
# from datetime import date

# today = date.today()
# subprojects = Subproject.objects.filter(updated_date__date=today)
# subprojects.update(infrastructure_deleted=False)

# from django.utils import timezone
# now = timezone.now()
# today_start = timezone.make_aware(timezone.datetime.combine(now.date(), timezone.datetime.min.time()))
# today_end = timezone.make_aware(timezone.datetime.combine(now.date(), timezone.datetime.max.time()))
# subprojects = Subproject.objects.filter(updated_date__range=(today_start, today_end))