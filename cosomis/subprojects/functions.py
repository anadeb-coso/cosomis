from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from datetime import datetime, date as type_date
import pandas as pd
import copy
import re as re_module
import sys, os
from sys import platform

from administrativelevels.libraries import functions as libraries_functions
from administrativelevels.models import AdministrativeLevel, CVD
from subprojects.models import Subproject, Project, Component
from cosomis.utils import (
    link_infrastures_to_subproject, copy_cvd_to_list_of_beneficiary_villages,
    attribute_project_to_subprojects, attribute_component_to_subprojects,
    save_subproject_tracking
)


def get_value(elt):
    # return elt if not pd.isna(elt) else None
    _elt  = elt if not pd.isna(elt) else None
    if _elt and _elt.__str__() == "00:00:00":
        return None
        
    return _elt

def exists_id(liste, id):
    for o in liste:
        if o.id == id:
            return True
    return False


def get_adminstrative_level_by_name(ad_name, canton_str: str):
    try:
        return AdministrativeLevel.objects.get(name=ad_name, type="Village", parent__name=canton_str)
    except AdministrativeLevel.DoesNotExist as exc:
        try:
            return AdministrativeLevel.objects.get(
                name=libraries_functions.strip_accents(ad_name), type="Village", parent__name=canton_str
            )
        except AdministrativeLevel.DoesNotExist as exc:
            try:
                return AdministrativeLevel.objects.get(name=ad_name.replace(" ", ""), type="Village", parent__name=canton_str)
            except AdministrativeLevel.DoesNotExist as exc:
                try:
                    return AdministrativeLevel.objects.get(
                        name=libraries_functions.strip_accents(ad_name.replace(" ", "")), type="Village", parent__name=canton_str
                    )
                except AdministrativeLevel.DoesNotExist as exc:
                    try:
                        return AdministrativeLevel.objects.get(
                            name=libraries_functions.strip_accents(ad_name.replace("-", " ")), type="Village", parent__name=canton_str
                        )
                    except AdministrativeLevel.DoesNotExist as exc:
                        try:
                            return AdministrativeLevel.objects.get(
                                name=libraries_functions.strip_accents(ad_name.replace(" ", "-")), type="Village", parent__name=canton_str
                            )
                        except AdministrativeLevel.DoesNotExist as exc:
                            try:
                                return AdministrativeLevel.objects.get(
                                    name=libraries_functions.strip_accents(ad_name.replace(" ", "-")), type="Village", parent__name=canton_str
                                )
                            except AdministrativeLevel.DoesNotExist as exc:
                                return None
                            except AdministrativeLevel.MultipleObjectsReturned as exc:
                                return None
                        except AdministrativeLevel.MultipleObjectsReturned as exc:
                            return None
                    except AdministrativeLevel.MultipleObjectsReturned as exc:
                        return None
                
                except AdministrativeLevel.MultipleObjectsReturned as exc:
                    return None

            except AdministrativeLevel.MultipleObjectsReturned as exc:
                return None

        except AdministrativeLevel.MultipleObjectsReturned as exc:
            return None

    except AdministrativeLevel.MultipleObjectsReturned as exc:
        return None

def get_adminstrative_level_by_name_with_slash(ad_name: str, canton_str: str):
    villages_name = re_module.split('[&,;/+]| Et ', ad_name.title()) #ad_name.split("/")
    print(villages_name)
    for village_name in villages_name:
        v = get_adminstrative_level_by_name(village_name.upper(), canton_str)
        if v:
            try:
                return v.cvd.headquarters_village
            except:
                return v
    return None



def save_csv_datas_subprojects_in_db(datas_file: dict, cvd_ids=[], canton_ids=[]) -> str:
    """Function to save the CSV datas in database"""
    
    at_least_one_save = False # Variable to determine if at least one is saved
    at_least_one_error = False # Variable to determine if at least one error is occurred
    at_least_error_name = False # Variable to determine if the name of village is wrong
    text_errors = ""
    list_villages_not_found = []
    list_villages_not_found_full_infos = []
    list_villages_multi_obj_found = []
    nbr_subproject_not_associate_to_priority = 0
    text_subproject_not_associate_to_priority = ""
    list_objects_exist = []
    nbr_other_errors = 0
    columns = [
        "Sous-projets prioritaire de la sous-composante 1.1 (infrastructures communautaires)", 
        "Sous-projets prioritaire de la sous-composante 1.3 (Besoins des jeunes)"
    ]
    _components = {
        '1': 'COMPOSANTE 1', '1.1': 'COMPOSANTE 1.1', '1.2': 'COMPOSANTE 1.2', 
        '1.2a': 'COMPOSANTE 1.2a', '1.2b': 'COMPOSANTE 1.2b', '1.3': 'COMPOSANTE 1.3', 
        '2': 'COMPOSANTE 2', '3': 'COMPOSANTE 3', '4': 'COMPOSANTE 4', '5': 'COMPOSANTE 5'
    }
    
    if datas_file:
        count = 0
        long = len(list(datas_file.values())[0])
        while count < long:
        
            
            try:
                canton_file_data = str(datas_file["CANTON"][count]).upper()
                _village = str(datas_file["VILLAGE/CDV"][count])
                __village = _village.upper()
                number = get_value(datas_file["N°"][count])
                joint_subproject_number = get_value(datas_file["num_kit"][count])
                intervention_unit = get_value(datas_file["UNITE D'INTERVENTION"][count])
                facilitator_name = get_value(datas_file["NOM DE L'AC"][count])
                wave = get_value(datas_file["VAGUE"][count])
                lot = get_value(datas_file["LOT"][count])
                subproject_sector = get_value(datas_file["SECTEUR BENEFICIAIRE–SP"][count])
                type_of_subproject = get_value(datas_file["TYPE D'OUVRAGE (INFRASTRUCTURE)"][count])
                full_title_of_approved_subproject = get_value(datas_file["INTITULE COMPLET DU SOUS-PROJET APPROUVES (Description)"][count])
                works_type = get_value(datas_file["TYPE DE TRAVAUX"][count])
                estimated_cost = get_value(datas_file["COUT ESTIMATIF"][count])
                level_of_achievement_donation_certificate = get_value(datas_file["NIVEAU D'OBTENTION ATTESTATION DE DONATION"][count])
                approval_date_cora = get_value(datas_file["DATE D'APPROBATION CORA"][count])
                date_of_signature_of_contract_for_construction_supervisors = get_value(datas_file["DATE SIGNATURE CONTRAT CONTROLEURS DE TRAVAUX BTP (CT)"][count])
                amount_of_the_contract_for_construction_supervisors = get_value(datas_file["MONTANT DU CONTRAT CONTROLEURS DE TRAVAUX BTP (CT)"][count])
                date_signature_contract_controllers_in_SES = get_value(datas_file["DATE SIGNATURE CONTRAT CONTROLEURS EN SES (CSES)"][count])
                amount_of_the_controllers_contract_in_SES = get_value(datas_file["MONTANT DU CONTRAT CONTROLEURS EN SES (CSES)"][count])
                convention = get_value(datas_file["CONVENTION"][count])
                contract_number_of_work_companies = get_value(datas_file["N° CONTRAT ENTREPRISES DE TRAVAUX (ET)"][count])
                name_of_the_awarded_company_works_companies = get_value(datas_file["NOM DE L'ENTREPRISE ATTRIBUTAIRE ENTREPRISES DE TRAVAUX (ET)"][count])
                date_signature_contract_work_companies = get_value(datas_file["DATE SIGNATURE CONTRAT ENTREPRISES DE TRAVAUX (ET)"][count])
                contract_amount_work_companies = get_value(datas_file["MONTANT DU CONTRAT ENTREPRISES DE TRAVAUX (ET)"][count])
                name_of_company_awarded_efme = get_value(datas_file["NOM DE L'ENTREPRISE ATTRIBUTAIRE ENTREPRISES DE FOURNITURE DE MOBILIERS ET EQUIPEMENTS (EFME)"][count])
                date_signature_contract_efme = get_value(datas_file["DATE SIGNATURE CONTRAT ENTREPRISES DE FOURNITURE DE MOBILIERS ET EQUIPEMENTS (EFME)"][count])
                contract_companies_amount_for_efme = get_value(datas_file["MONTANT DU CONTRAT ENTREPRISES DE FOURNITURE DE MOBILIERS ET EQUIPEMENTS (EFME)"][count])
                date_signature_contract_facilitator = get_value(datas_file["DATE SIGNATURE CONTRAT ANIMATEUR COMMUNAUTAIRE (AC)"][count])
                amount_of_the_facilitator_contract = get_value(datas_file["MONTANT DU CONTRAT ANIMATEUR COMMUNAUTAIRE (AC)"][count])
                launch_date_of_the_construction_site_in_the_village = get_value(datas_file["DATE DE LANCEMENT DU CHANTIER DANS LE VILLAGE (DATE NOTIFICATION DE L'ORDRE DE SERVICE)"][count])
                current_level_of_physical_realization_of_the_work = get_value(datas_file["NIVEAU ACTUEL DE REALISATION PHYSIQUE DE L'OUVRAGE"][count])
                length_of_the_track = get_value(datas_file["LONGUEUR DE LA PISTE (Km)"][count])
                depth_of_drilling = get_value(datas_file["PRONFONDEUR DU FORAGE (m)"][count])
                drilling_flow_rate = get_value(datas_file["DEBIT DU FORAGE (m3)"][count])
                current_status_of_the_site = get_value(datas_file["""STATUT ACTUEL DU CHANTIER 
(Travaux en cours, Arrêt travaux, Abandon travaux, Réception technique, Réception provisoire etc,)"""][count])
                expected_duration_of_the_work = get_value(datas_file["DUREE PREVUE DE REALISATION DES TRAVAUX (Mois)"][count])
                expected_end_date_of_the_contract = get_value(datas_file["DATE PREVUE DE FIN DU CONTRAT"][count])
                total_contract_amount_paid = get_value(datas_file["MONTANT TOTAL DU MARCHE PAYE (Contrôle technique + Contrôle sauvegardes + Entreprise BTP + Entreprise Mobiliers + AC)"][count])
                amount_of_the_care_and_maintenance_fund_expected_to_be_mobilized = get_value(datas_file["MONTANT DU FONDS D'ENTRETIEN ET DE MAINTENANCE (EMI)  PREVU POUR ETRE MOBILISE"][count])
                care_and_maintenance_amount_on_village_account = get_value(datas_file["MONTANT DU FONDS D'ENTRETIEN ET DE MAINTENANCE (EMI)  MOBILISE ET DEPOSE SUR LE COMPTE DU VILLAGE"][count])
                existence_of_maintenance_and_upkeep_plan_developed_by_community = get_value(datas_file["""Existence d'un Plan d'Entretien et de Maintenance (Plan EMI) élaboré par la Communauaté 
(Si Oui mettre 1; Si non mettre 0)"""][count])
                date_of_technical_acceptance_of_work_contracts = get_value(datas_file["DATES DE RECEPTION TECHNIQUE DES MARCHE DE TRAVAUX (BTP OU FORAGE)"][count])
                technical_acceptance_date_for_efme_contracts = get_value(datas_file["DATES DE RECEPTION TECHNIQUE DES MARCHE DE FOURNITURE DE MOBILIERS ET EQUIPEMENTS"][count])
                date_of_provisional_acceptance_of_work_contracts = get_value(datas_file["DATES DE RECEPTION PROVISOIRE DES MARCHE DE TRAVAUX (BTP OU FORAGE)"][count])
                provisional_acceptance_date_for_efme_contracts = get_value(datas_file["DATES DE RECEPTION PROVISOIRE DES MARCHE DE FOURNITURE DE MOBILIERS ET EQUIPEMENTS"][count])
                official_handover_date_of_the_microproject_to_the_community = get_value(datas_file["DATE DE REMISE OFFICIELLE DU MICROPROJET A LA COMMUNAUTE"][count])
                official_handover_date_of_the_microproject_to_the_sector = get_value(datas_file["DATE DE REMISE OFFICIELLE DU MICROPROJET AU SECTORIEL"][count])
                comments = get_value(datas_file["COMMENTAIRES"][count])
                longitude = get_value(datas_file["Longitude (x)"][count])
                latitude = get_value(datas_file["Latitude (y)"][count])
                
                population = get_value(datas_file["POPULATION"][count])
                direct_beneficiaries_men = get_value(datas_file["H (BENEFICIAIRES DIRECTS)"][count])
                direct_beneficiaries_women = get_value(datas_file["F (BENEFICIAIRES DIRECTS)"][count])
                indirect_beneficiaries_men = get_value(datas_file["H (BENEFICIAIRES INDIRECTS)"][count])
                indirect_beneficiaries_women = get_value(datas_file["F (BENEFICIAIRES INDIRECTS)"][count])

                women_s_group = get_value(datas_file["Groupe des femmes"][count])
                youth_group = get_value(datas_file["Groupe des jeunes"][count])
                breeders_farmers_group = get_value(datas_file["Groupe des éleveurs/Agriculteurs"][count])
                ethnic_minority_group = get_value(datas_file["Groupe des minorités ethniques"][count])
                
                has_latrine_blocs = get_value(datas_file["Blocs latrine? (Oui, Non)"][count])
                number_of_latrine_blocks = get_value(datas_file["Nombre de blocs latrine (de 3 cabines)"][count])
                number_of_classrooms = get_value(datas_file["Nombre de salle de classes"][count])
                has_fence = get_value(datas_file["Clôture"][count])


                list_of_villages_crossed_by_the_track_or_electrification = get_value(datas_file["LISTE DE VILLAGES TRAVERSÉ PAR LA PISTE OU L'ÉLECTRIFICATION"][count])
                
                
                # for village in __village.split("/"):
                # village = village.strip()
                village = __village.strip()
                _is_object_error = False
                is_link_to_subproject = False
                subproject_to_link = None
                administrative_level = None
                administrative_level_canton = None
                subproject = None
                if village in ("CCD", "TOUTE LA COMMUNAUTE"):
                    pass
                else:
                    try:
                        administrative_level = AdministrativeLevel.objects.get(name=village, type="Village", parent__name=canton_file_data)
                    except AdministrativeLevel.DoesNotExist as exc:
                        try:
                            administrative_level = AdministrativeLevel.objects.get(
                                name=libraries_functions.strip_accents(village), type="Village", parent__name=canton_file_data
                            )
                        except AdministrativeLevel.DoesNotExist as exc:
                            try:
                                administrative_level = AdministrativeLevel.objects.get(name=village.replace(" ", ""), type="Village", parent__name=canton_file_data)
                            except AdministrativeLevel.DoesNotExist as exc:
                                try:
                                    administrative_level = AdministrativeLevel.objects.get(
                                        name=libraries_functions.strip_accents(village.replace(" ", "")), type="Village", parent__name=canton_file_data
                                    )
                                except AdministrativeLevel.DoesNotExist as exc:
                                    try:
                                        administrative_level = AdministrativeLevel.objects.get(
                                            name=libraries_functions.strip_accents(village.replace("-", " ")), type="Village", parent__name=canton_file_data
                                        )
                                    except AdministrativeLevel.DoesNotExist as exc:
                                        try:
                                            administrative_level = AdministrativeLevel.objects.get(
                                                name=libraries_functions.strip_accents(village.replace(" ", "-")), type="Village", parent__name=canton_file_data
                                            )
                                        except AdministrativeLevel.DoesNotExist as exc:
                                            _is_object_error = True
                                            if _village not in list_villages_not_found:
                                                list_villages_not_found.append(_village)
                                                list_villages_not_found_full_infos.append({
                                                    "REGION": get_value(datas_file["REGION"][count]),
                                                    "PREFECTURE": get_value(datas_file["PREFECTURE"][count]),
                                                    "COMMUNE": get_value(datas_file["COMMUNE"][count]),
                                                    "CANTON": get_value(datas_file["CANTON"][count]),
                                                    "VILLAGE/CDV": get_value(datas_file["VILLAGE/CDV"][count])
                                                })
                                            text_errors += (f'\nLine N°{count} [{_village}]: {exc.__str__()}' if text_errors else f'Line N°{count} [{_village}]: {exc.__str__()}')
                                            at_least_error_name = True
                                            at_least_one_error = True
                                        except AdministrativeLevel.MultipleObjectsReturned as exc:
                                            raise AdministrativeLevel.MultipleObjectsReturned()
                                    except AdministrativeLevel.MultipleObjectsReturned as exc:
                                        raise AdministrativeLevel.MultipleObjectsReturned()
                                
                                except AdministrativeLevel.MultipleObjectsReturned as exc:
                                    raise AdministrativeLevel.MultipleObjectsReturned()

                            except AdministrativeLevel.MultipleObjectsReturned as exc:
                                raise AdministrativeLevel.MultipleObjectsReturned()

                        except AdministrativeLevel.MultipleObjectsReturned as exc:
                            raise AdministrativeLevel.MultipleObjectsReturned()

                    except AdministrativeLevel.MultipleObjectsReturned as exc:
                        _is_object_error = True
                        if _village not in list_villages_multi_obj_found:
                            list_villages_multi_obj_found.append(_village)
                        at_least_error_name = True
                        at_least_one_error = True
                        text_errors += (f'\nLine N°{count} [{_village}]: {exc.__str__()}' if text_errors else f'Line N°{count} [{_village}]: {exc.__str__()}')

                    if _is_object_error and not administrative_level and \
                        ("/" in village.title() or "," in village.title() or ";" in village.title() or " Et " in village.title() or "&" in village.title() or "+" in village.title()):

                        administrative_level = get_adminstrative_level_by_name_with_slash(village, canton_file_data)

                        if not administrative_level:
                            _is_object_error = True
                        else:
                            del list_villages_not_found_full_infos[-1]
                            del list_villages_not_found[-1]
                            _is_object_error = False
                        print(administrative_level)
                if not _is_object_error:
                    
                    if administrative_level and ((cvd_ids and administrative_level.cvd_id not in cvd_ids) or (canton_ids and administrative_level.cvd_id not in canton_ids)):
                        continue #Continue without save the object if the cvd ids or the cantan ids are specific and their village current is different
                    
                    estimated_cost = float(estimated_cost) if estimated_cost else 0.0
                    
                    # _list_chars = column.split(" ")
                    # for char in _list_chars:
                    #     if char in list(_components.keys()):
                    #         _list_data = str(data).split("-")
                    #         if _list_data[0].isdigit():
                    #             name_priority = (str(data)[(len(_list_data[0])+1):]).strip()
                    #         else:
                    #             name_priority = str(data).strip()
                    #         try:
                    #             component = Component.objects.get(name=_components[char].upper())
                    #         except Exception as exc:
                    #             component = None

                    if village in ("CCD", "TOUTE LA COMMUNAUTE"):
                        subprojects = Subproject.objects.filter(
                            number=number
                            # full_title_of_approved_subproject=full_title_of_approved_subproject
                            )
                        canton = get_value(datas_file["CANTON"][count])
                        
                        if canton:
                            canton = canton.upper()
                            try:
                                administrative_level_canton = AdministrativeLevel.objects.get(name=canton, type="Canton")
                            except AdministrativeLevel.DoesNotExist as exc:
                                try:
                                    administrative_level_canton = AdministrativeLevel.objects.get(
                                        name=libraries_functions.strip_accents(canton), type="Canton"
                                    )
                                except AdministrativeLevel.DoesNotExist as exc:
                                    try:
                                        administrative_level_canton = AdministrativeLevel.objects.get(name=canton.replace(" ", ""), type="Canton")
                                    except AdministrativeLevel.DoesNotExist as exc:
                                        try:
                                            administrative_level_canton = AdministrativeLevel.objects.get(
                                                name=libraries_functions.strip_accents(canton.replace(" ", "")), type="Canton"
                                            )
                                        except AdministrativeLevel.DoesNotExist as exc:
                                            try:
                                                administrative_level_canton = AdministrativeLevel.objects.get(
                                                    name=libraries_functions.strip_accents(canton.replace("-", " ")), type="Canton"
                                                )
                                            except AdministrativeLevel.DoesNotExist as exc:
                                                _is_object_error = True
                                                if canton not in list_villages_not_found:
                                                    list_villages_not_found.append(canton)
                                                    list_villages_not_found_full_infos.append({
                                                        "REGION": get_value(datas_file["REGION"][count]),
                                                        "PREFECTURE": get_value(datas_file["PREFECTURE"][count]),
                                                        "COMMUNE": get_value(datas_file["COMMUNE"][count]),
                                                        "CANTON": get_value(datas_file["CANTON"][count]),
                                                        "VILLAGE/CDV": get_value(datas_file["VILLAGE/CDV"][count])
                                                    })
                                                text_errors += (f'\nLine N°{count} [{canton}]: {exc.__str__()}' if text_errors else f'Line N°{count} [{canton}]: {exc.__str__()}')
                                                at_least_error_name = True
                                                at_least_one_error = True
                                            except AdministrativeLevel.MultipleObjectsReturned as exc:
                                                raise AdministrativeLevel.MultipleObjectsReturned()
                                            
                                        except AdministrativeLevel.MultipleObjectsReturned as exc:
                                            raise AdministrativeLevel.MultipleObjectsReturned()

                                    except AdministrativeLevel.MultipleObjectsReturned as exc:
                                        raise AdministrativeLevel.MultipleObjectsReturned()

                                except AdministrativeLevel.MultipleObjectsReturned as exc:
                                    raise AdministrativeLevel.MultipleObjectsReturned()

                            except AdministrativeLevel.MultipleObjectsReturned as exc:
                                _is_object_error = True
                                if canton not in list_villages_multi_obj_found:
                                    list_villages_multi_obj_found.append(canton)
                                at_least_error_name = True
                                at_least_one_error = True
                                text_errors += (f'\nLine N°{count} [{canton}]: {exc.__str__()}' if text_errors else f'Line N°{count} [{canton}]: {exc.__str__()}')
                        
                        # for sub in subprojects:
                        #     if administrative_level_canton and not sub.link_to_subproject:
                        #         is_link_to_subproject = True
                        #         subproject = sub
                        #     if administrative_level_canton and sub.canton and sub.canton.id == administrative_level_canton.id:
                        #         subproject = sub
                        #         is_link_to_subproject = False
                        #         break
                        subproject = subprojects.first()

                    else:
                        subprojects = Subproject.objects.filter(
                            number=number
                            # full_title_of_approved_subproject=full_title_of_approved_subproject,
                            # location_subproject_realized=administrative_level, 
                            # subproject_sector=subproject_sector,
                            # type_of_subproject=type_of_subproject
                            )
                        # if subproject:
                        #     subproject = list(subproject)[0]
                        subproject = subprojects.first()

                    # if is_link_to_subproject:
                    #     subproject_to_link = copy.copy(subproject)
                    #     subproject = None

                    if not subproject:
                        subproject = Subproject()
                        # subproject.link_to_subproject = subproject_to_link
                    try:
                        _expected_duration_of_the_work = float(str(expected_duration_of_the_work).split(' ')[0].split('m')[0].split('M')[0])
                    except:
                        _expected_duration_of_the_work = None
                    
                    
                    _current_level_of_physical_realization_of_the_works = str(current_level_of_physical_realization_of_the_work).split("%")
                    if _current_level_of_physical_realization_of_the_works:
                        _current_level_of_physical_realization_of_the_work = _current_level_of_physical_realization_of_the_works[0]
                        if not _current_level_of_physical_realization_of_the_work \
                                or not str(_current_level_of_physical_realization_of_the_work).replace('.','',1).replace(',','',1).isdigit():
                            _current_level_of_physical_realization_of_the_work = current_level_of_physical_realization_of_the_work
                        else:
                            _current_level_of_physical_realization_of_the_work = float(_current_level_of_physical_realization_of_the_work.replace(',', '0')) * 100
                    else:
                        _current_level_of_physical_realization_of_the_work = current_level_of_physical_realization_of_the_work

                    subproject.location_subproject_realized = administrative_level
                    subproject.number = number
                    subproject.joint_subproject_number = joint_subproject_number
                    # subproject.intervention_unit = intervention_unit #
                    subproject.facilitator_name = facilitator_name
                    subproject.wave = wave
                    subproject.lot = lot
                    subproject.subproject_sector = subproject_sector
                    subproject.type_of_subproject = type_of_subproject
                    subproject.full_title_of_approved_subproject = full_title_of_approved_subproject
                    subproject.works_type = works_type
                    subproject.estimated_cost = estimated_cost
                    subproject.level_of_achievement_donation_certificate = level_of_achievement_donation_certificate
                    subproject.approval_date_cora = approval_date_cora
                    subproject.date_of_signature_of_contract_for_construction_supervisors = date_of_signature_of_contract_for_construction_supervisors
                    subproject.amount_of_the_contract_for_construction_supervisors = amount_of_the_contract_for_construction_supervisors
                    subproject.date_signature_contract_controllers_in_SES = date_signature_contract_controllers_in_SES
                    subproject.amount_of_the_controllers_contract_in_SES = amount_of_the_controllers_contract_in_SES
                    subproject.convention = convention
                    subproject.contract_number_of_work_companies = contract_number_of_work_companies
                    subproject.name_of_the_awarded_company_works_companies = name_of_the_awarded_company_works_companies
                    subproject.date_signature_contract_work_companies = date_signature_contract_work_companies
                    subproject.contract_amount_work_companies = contract_amount_work_companies
                    subproject.name_of_company_awarded_efme = name_of_company_awarded_efme
                    subproject.date_signature_contract_efme = date_signature_contract_efme
                    subproject.contract_companies_amount_for_efme = contract_companies_amount_for_efme
                    subproject.date_signature_contract_facilitator = date_signature_contract_facilitator
                    subproject.amount_of_the_facilitator_contract = amount_of_the_facilitator_contract
                    subproject.launch_date_of_the_construction_site_in_the_village = launch_date_of_the_construction_site_in_the_village
                    subproject.current_level_of_physical_realization_of_the_work = _current_level_of_physical_realization_of_the_work
                    subproject.length_of_the_track = length_of_the_track
                    subproject.depth_of_drilling = depth_of_drilling
                    subproject.drilling_flow_rate = drilling_flow_rate
                    subproject.current_status_of_the_site = current_status_of_the_site
                    subproject.expected_duration_of_the_work = _expected_duration_of_the_work
                    subproject.expected_end_date_of_the_contract = expected_end_date_of_the_contract
                    subproject.total_contract_amount_paid = total_contract_amount_paid
                    subproject.amount_of_the_care_and_maintenance_fund_expected_to_be_mobilized = amount_of_the_care_and_maintenance_fund_expected_to_be_mobilized
                    subproject.care_and_maintenance_amount_on_village_account = care_and_maintenance_amount_on_village_account
                    subproject.existence_of_maintenance_and_upkeep_plan_developed_by_community = bool(existence_of_maintenance_and_upkeep_plan_developed_by_community) if existence_of_maintenance_and_upkeep_plan_developed_by_community else False
                    subproject.date_of_technical_acceptance_of_work_contracts = date_of_technical_acceptance_of_work_contracts
                    subproject.technical_acceptance_date_for_efme_contracts = technical_acceptance_date_for_efme_contracts
                    subproject.date_of_provisional_acceptance_of_work_contracts = date_of_provisional_acceptance_of_work_contracts
                    subproject.provisional_acceptance_date_for_efme_contracts = provisional_acceptance_date_for_efme_contracts
                    subproject.official_handover_date_of_the_microproject_to_the_community = official_handover_date_of_the_microproject_to_the_community
                    subproject.official_handover_date_of_the_microproject_to_the_sector = official_handover_date_of_the_microproject_to_the_sector
                    subproject.comments = comments
                    if longitude and latitude:
                        subproject.latitude = latitude
                        subproject.longitude = longitude
                    
                    # subproject.population = population #
                    # subproject.direct_beneficiaries_men = direct_beneficiaries_men #
                    # subproject.direct_beneficiaries_women = direct_beneficiaries_women #
                    # subproject.indirect_beneficiaries_men = indirect_beneficiaries_men #
                    # subproject.indirect_beneficiaries_women = indirect_beneficiaries_women #
                    
                    if women_s_group != None:
                        subproject.women_s_group = bool(women_s_group)
                    if youth_group != None:
                        subproject.youth_group = bool(youth_group)
                    if breeders_farmers_group != None:
                        subproject.breeders_farmers_group = bool(breeders_farmers_group)
                    if ethnic_minority_group != None:
                        subproject.ethnic_minority_group = bool(ethnic_minority_group)
                        
                    if has_latrine_blocs != None:
                        subproject.has_latrine_blocs = True if str(has_latrine_blocs).upper() in ("OUI", 1) else False
                    if number_of_latrine_blocks != None:
                        subproject.number_of_latrine_blocks = number_of_latrine_blocks
                    if number_of_classrooms != None:
                        subproject.number_of_classrooms = number_of_classrooms
                    if has_fence != None:
                        subproject.has_fence = True if str(has_fence).upper() in ("OUI", 1) else False

                    subproject = subproject.save_and_return_object()
                    
                    if village in ("CCD", "TOUTE LA COMMUNAUTE") and administrative_level_canton:
                        subproject.canton = administrative_level_canton

                        if list_of_villages_crossed_by_the_track_or_electrification:
                            liste = str(list_of_villages_crossed_by_the_track_or_electrification).split(";")
                            for ad_name in liste:
                                ad = get_adminstrative_level_by_name(ad_name.strip(), canton_file_data)
                                if ad:
                                    subproject.list_of_villages_crossed_by_the_track_or_electrification.add(ad)
                        
                    elif administrative_level and administrative_level.cvd:
                        subproject.cvd  = administrative_level.cvd
                    

                    subproject.save()


            except Exception as exc:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                text_errors += f'\nLine N°{count} [{_village}]: {exc.__str__()}, {exc_type}, {fname}, {exc_tb.tb_lineno}'
                nbr_other_errors += 1
                at_least_one_error = True
                print(exc)

            count += 1
            # if count == 1:
            #     break
    print(count)
    
    subprojects = Subproject.objects.all()
    link_infrastures_to_subproject() #Link each infrastructure to their subproject
    copy_cvd_to_list_of_beneficiary_villages() #Link villages to theirs subprojects
    attribute_project_to_subprojects(
        subprojects, Project.objects.get(id=1)
    ) #Link projects to COSO project
    attribute_component_to_subprojects(
        subprojects, Component.objects.get(id=2)
    ) #Link projects to Component 1.1
    
    save_subproject_tracking() #Update Subproject Step-level
    
    message = ""
    if at_least_one_save and not at_least_one_error:
        message = _("Success!")
    elif not at_least_one_save and not at_least_one_error:
        message = _("No items have been saved!")
    elif not at_least_one_save and at_least_one_error:
        if at_least_error_name:
            message = _("A problem has occurred! The name(s) of the village(s) is wrong.")
        else:
            message = _("A problem has occurred!")
    elif at_least_one_save and at_least_one_error:
        if at_least_error_name:
            message = _("Some element(s) have not been saved! The name(s) of the village(s) is wrong.")
        else:
            message = _("Some element(s) have not been saved!")

    summary_errors = "##########################################################Summary###################################################################\n"
    summary_errors += f'\nNumber of object not found errors: {len(list_villages_not_found)} ==> {list_villages_not_found}'
    summary_errors += f'\n\nNumber of Multiple object found errors: {len(list_villages_multi_obj_found)} ==> {list_villages_multi_obj_found}'
    summary_errors += f'\n\nNumber of other errors: {nbr_other_errors}'

    if text_subproject_not_associate_to_priority:
        summary_errors += "\n\n\n##########################################################Object Subproject don't save###################################################################\n"
        summary_errors += f"\nNumber of the subprojects don't save : {nbr_subproject_not_associate_to_priority}"
        summary_errors += text_subproject_not_associate_to_priority

    if list_objects_exist:
        summary_errors += "\n\n\n##########################################################Object already exist###################################################################\n"
        summary_errors += f"\nNumber : {len(list_objects_exist)}"
        summary_errors += f"\n{list_objects_exist}"

    summary_errors += "\n\n\n##########################################################Messages###################################################################\n"
    summary_errors += "\n" + message

    summary_errors += "\n\n\n##########################################################Details###################################################################\n"
    summary_errors += "\n" + text_errors

    if not os.path.exists("media/logs/errors"):
        os.makedirs("media/logs/errors")
    file_path = "logs/errors/upload_subprojects_logs_errors_" + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") + ".txt"
    
    f = open("media/"+file_path, "a")
    f.write(summary_errors)
    f.close()

    return (message, file_path.replace("/", "\\\\") if platform == "win32" else file_path)

    #Excel error
    # datas = {
    #     "REGION": {},
    #     "PREFECTURE": {},
    #     "COMMUNE": {},
    #     "CANTON": {},
    #     "VILLAGE/CDV": {}
    # }
    # count = 0
    # file_type = "excel"
    # _type = "Village"
    # value_of_type = "all"
    # for v_error in list_villages_not_found_full_infos:
    #     datas["REGION"][count] = v_error.get("REGION")
    #     datas["PREFECTURE"][count] = v_error.get("PREFECTURE")
    #     datas["COMMUNE"][count] = v_error.get("COMMUNE")
    #     datas["CANTON"][count] = v_error.get("CANTON")
    #     datas["VILLAGE/CDV"][count] = v_error.get("VILLAGE/CDV")
    #     count += 1

    # if not os.path.exists("media/"+file_type+"/subprojects"):
    #     os.makedirs("media/"+file_type+"/subprojects")

    # file_name = "subprojects_" + _type.lower() + "_" + ((value_of_type.lower() + "_") if value_of_type else "")

    # if file_type == "csv":
    #     file_path = file_type+"/subprojects/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".csv"
    #     pd.DataFrame(datas).to_csv("media/"+file_path)
    # else:
    #     file_path = file_type+"/subprojects/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".xlsx"
    #     pd.DataFrame(datas).to_excel("media/"+file_path)

    # if platform == "win32":
    #     # windows
    #     return "", file_path.replace("/", "\\\\")
    # else:
    #     return "", file_path
    #End Excel error
    





def get_subprojects_under_file_excel_or_csv(file_type="excel", params={"type":"All", "value_of_type":"", "sector": "All", "subproject_type": "All"}) -> str:
    _type = params.get("type").capitalize() if params.get("type") else ""
    if file_type not in ("csv", "excel") or _type not in ("All", "Region", "Prefecture", "Commune", "Canton", "Village"):
        return ""

    datas = {
        "N°": {},
        "num_kit": {},
        "Longitude (x)": {},
        "Latitude (y)": {},
        "REGION": {},
        "PREFECTURE": {},
        "COMMUNE": {},
        "CANTON": {},
        "VILLAGE/CDV": {},
        "UNITE D'INTERVENTION": {},
        "POPULATION": {},
        "H (BENEFICIAIRES DIRECTS)": {},
        "F (BENEFICIAIRES DIRECTS)": {},
        "T (BENEFICIAIRES DIRECTS)": {},
        "H (BENEFICIAIRES INDIRECTS)": {},
        "F (BENEFICIAIRES INDIRECTS)": {},
        "T (BENEFICIAIRES INDIRECTS)": {},
        "T_Benef_H": {},
        "T_Benef_F": {},
        "TOTAL (Bénéficiaires)": {},
        "NOM DE L'AC": {},
        "VAGUE": {},
        "LOT": {},
        "SECTEUR BENEFICIAIRE–SP": {},
        "TYPE D'OUVRAGE (INFRASTRUCTURE)": {},
        "LISTE DE VILLAGES TRAVERSÉ PAR LA PISTE OU L'ÉLECTRIFICATION": {},
        "INTITULE COMPLET DU SOUS-PROJET APPROUVES (Description)": {},
        "TYPE DE TRAVAUX": {},
        "COUT ESTIMATIF": {},
        "NIVEAU D'OBTENTION ATTESTATION DE DONATION": {},
        "DATE D'APPROBATION CORA": {},
        "DATE SIGNATURE CONTRAT CONTROLEURS DE TRAVAUX BTP (CT)": {},
        "MONTANT DU CONTRAT CONTROLEURS DE TRAVAUX BTP (CT)": {},
        "DATE SIGNATURE CONTRAT CONTROLEURS EN SES (CSES)": {},
        "MONTANT DU CONTRAT CONTROLEURS EN SES (CSES)": {},
        "CONVENTION": {},
        "N° CONTRAT ENTREPRISES DE TRAVAUX (ET)": {},
        "NOM DE L'ENTREPRISE ATTRIBUTAIRE ENTREPRISES DE TRAVAUX (ET)": {},
        "DATE SIGNATURE CONTRAT ENTREPRISES DE TRAVAUX (ET)": {},
        "MONTANT DU CONTRAT ENTREPRISES DE TRAVAUX (ET)": {},
        "NOM DE L'ENTREPRISE ATTRIBUTAIRE ENTREPRISES DE FOURNITURE DE MOBILIERS ET EQUIPEMENTS (EFME)": {},
        "DATE SIGNATURE CONTRAT ENTREPRISES DE FOURNITURE DE MOBILIERS ET EQUIPEMENTS (EFME)": {},
        "MONTANT DU CONTRAT ENTREPRISES DE FOURNITURE DE MOBILIERS ET EQUIPEMENTS (EFME)": {},
        "DATE SIGNATURE CONTRAT ANIMATEUR COMMUNAUTAIRE (AC)": {},
        "MONTANT DU CONTRAT ANIMATEUR COMMUNAUTAIRE (AC)": {},
        "DATE DE LANCEMENT DU CHANTIER DANS LE VILLAGE (DATE NOTIFICATION DE L'ORDRE DE SERVICE)": {},
        "NIVEAU ACTUEL DE REALISATION PHYSIQUE DE L'OUVRAGE": {},
        "LONGUEUR DE LA PISTE (Km)": {},
        "PRONFONDEUR DU FORAGE (m)": {},
        "DEBIT DU FORAGE (m3)": {},
        """STATUT ACTUEL DU CHANTIER 
(Travaux en cours, Arrêt travaux, Abandon travaux, Réception technique, Réception provisoire etc,)""": {},
        "DUREE PREVUE DE REALISATION DES TRAVAUX (Mois)": {},
        "DATE PREVUE DE FIN DU CONTRAT": {},
        "MONTANT TOTAL DU MARCHE PAYE (Contrôle technique + Contrôle sauvegardes + Entreprise BTP + Entreprise Mobiliers + AC)": {},
        "MONTANT DU FONDS D'ENTRETIEN ET DE MAINTENANCE (EMI)  PREVU POUR ETRE MOBILISE": {},
        "MONTANT DU FONDS D'ENTRETIEN ET DE MAINTENANCE (EMI)  MOBILISE ET DEPOSE SUR LE COMPTE DU VILLAGE": {},
        """Existence d'un Plan d'Entretien et de Maintenance (Plan EMI) élaboré par la Communauaté 
(Si Oui mettre 1; Si non mettre 0)""": {},
        "DATES DE RECEPTION TECHNIQUE DES MARCHE DE TRAVAUX (BTP OU FORAGE)": {},
        "DATES DE RECEPTION TECHNIQUE DES MARCHE DE FOURNITURE DE MOBILIERS ET EQUIPEMENTS": {},
        "DATES DE RECEPTION PROVISOIRE DES MARCHE DE TRAVAUX (BTP OU FORAGE)": {},
        "DATES DE RECEPTION PROVISOIRE DES MARCHE DE FOURNITURE DE MOBILIERS ET EQUIPEMENTS": {},
        "DATE DE REMISE OFFICIELLE DU MICROPROJET A LA COMMUNAUTE": {},
        "DATE DE REMISE OFFICIELLE DU MICROPROJET AU SECTORIEL": {},
        "Groupe des femmes": {},
        "Groupe des jeunes": {},
        "Groupe des éleveurs/Agriculteurs": {},
        "Groupe des minorités ethniques": {},
        "COMMENTAIRES": {},
    }

    # administratives_levels = []
    # value_of_type = params.get("value_of_type").upper() if params.get("value_of_type") else ""
    # if _type == "All":
    #     administratives_levels = AdministrativeLevel.objects.filter(type="Village")
    # elif _type == "Region":
    #     for region in AdministrativeLevel.objects.filter(type=_type, name=value_of_type):
    #         for prefecture in AdministrativeLevel.objects.filter(parent=region):
    #             for commune in AdministrativeLevel.objects.filter(parent=prefecture):
    #                 for canton in AdministrativeLevel.objects.filter(parent=commune):
    #                     [administratives_levels.append(village) for village in canton.administrativelevel_set.get_queryset()]
    # elif _type == "Prefecture":
    #     for prefecture in AdministrativeLevel.objects.filter(type=_type, name=value_of_type):
    #         for commune in AdministrativeLevel.objects.filter(parent=prefecture):
    #             for canton in AdministrativeLevel.objects.filter(parent=commune):
    #                 [administratives_levels.append(village) for village in canton.administrativelevel_set.get_queryset()]
    # elif _type == "Commune":
    #     for commune in AdministrativeLevel.objects.filter(type=_type, name=value_of_type):
    #         for canton in AdministrativeLevel.objects.filter(parent=commune):
    #             [administratives_levels.append(village) for village in canton.administrativelevel_set.get_queryset()]
    # elif _type == "Canton":
    #     for canton in AdministrativeLevel.objects.filter(type=_type, name=value_of_type):
    #         [administratives_levels.append(village) for village in canton.administrativelevel_set.get_queryset()]
    # elif _type == "Village":
    #     administratives_levels = AdministrativeLevel.objects.filter(type=_type, name=value_of_type)

    # Subprojects = []
    # sector = params.get("sector")
    # subproject_type = params.get("subproject_type")
    # for adm_level in administratives_levels:
    #     if sector != "All" and subproject_type != "All":
    #         [Subprojects.append(o) for o in Subproject.objects.filter(Q(cvd=adm_level.cvd, subproject_sector=sector, type_of_subproject=subproject_type) | Q(canton=adm_level.parent, subproject_sector=sector, type_of_subproject=subproject_type))]
    #     elif sector != "All" and subproject_type == "All":
    #         [Subprojects.append(o) for o in Subproject.objects.filter(Q(cvd=adm_level.cvd, subproject_sector=sector) | Q(canton=adm_level.parent, subproject_sector=sector))]
    #     elif sector == "All" and subproject_type != "All":
    #         [Subprojects.append(o) for o in Subproject.objects.filter(Q(cvd=adm_level.cvd, type_of_subproject=subproject_type) | Q(canton=adm_level.parent, type_of_subproject=subproject_type))]
    #     else:
    #         if not Subprojects:
    #             [Subprojects.append(o) for o in Subproject.objects.filter(Q(location_subproject_realized_id=adm_level.id) | Q(canton_id=adm_level.parent_id))]
    #         for s in Subprojects:
    #             [Subprojects.append(o) for o in Subproject.objects.filter(Q(location_subproject_realized_id=adm_level.id) | Q(canton_id=adm_level.parent_id)) if s.id != o.id]


    cvds = []
    value_of_type = params.get("value_of_type").upper() if params.get("value_of_type") else ""
    if _type == "All":
        cvds = CVD.objects.all()
    elif _type == "Region":
        for region in AdministrativeLevel.objects.filter(type=_type, name=value_of_type):
            for prefecture in AdministrativeLevel.objects.filter(parent=region):
                for commune in AdministrativeLevel.objects.filter(parent=prefecture):
                    for canton in AdministrativeLevel.objects.filter(parent=commune):
                        for g in canton.geographicalunit_set.get_queryset():
                            [cvds.append(c) for c in g.cvd_set.get_queryset()]
    elif _type == "Prefecture":
        for prefecture in AdministrativeLevel.objects.filter(type=_type, name=value_of_type):
            for commune in AdministrativeLevel.objects.filter(parent=prefecture):
                for canton in AdministrativeLevel.objects.filter(parent=commune):
                    for g in canton.geographicalunit_set.get_queryset():
                        [cvds.append(c) for c in g.cvd_set.get_queryset()]
    elif _type == "Commune":
        for commune in AdministrativeLevel.objects.filter(type=_type, name=value_of_type):
            for canton in AdministrativeLevel.objects.filter(parent=commune):
                for g in canton.geographicalunit_set.get_queryset():
                    [cvds.append(c) for c in g.cvd_set.get_queryset()]
    elif _type == "Canton":
        for canton in AdministrativeLevel.objects.filter(type=_type, name=value_of_type):
            for g in canton.geographicalunit_set.get_queryset():
                [cvds.append(c) for c in g.cvd_set.get_queryset()]
    elif _type == "Village":
        ads = AdministrativeLevel.objects.filter(type=_type, name=value_of_type)
        [cvds.append(ad.cvd) for ad in ads]

    
    _subprojects = []
    sector = params.get("sector")
    subproject_type = params.get("subproject_type")
    for cvd in cvds:
        if sector != "All" and subproject_type != "All":
            [_subprojects.append(o) for o in Subproject.objects.filter(Q(cvd=cvd, subproject_sector=sector, type_of_subproject=subproject_type) | Q(location_subproject_realized=cvd.headquarters_village, subproject_sector=sector, type_of_subproject=subproject_type) | Q(canton=cvd.get_canton(), subproject_sector=sector, type_of_subproject=subproject_type))]
        elif sector != "All" and subproject_type == "All":
            [_subprojects.append(o) for o in Subproject.objects.filter(Q(cvd=cvd, subproject_sector=sector) | Q(location_subproject_realized=cvd.headquarters_village, subproject_sector=sector) | Q(canton=cvd.get_canton(), subproject_sector=sector))]
        elif sector == "All" and subproject_type != "All":
            [_subprojects.append(o) for o in Subproject.objects.filter(Q(cvd=cvd, type_of_subproject=subproject_type) | Q(location_subproject_realized=cvd.headquarters_village, type_of_subproject=subproject_type) | Q(canton=cvd.get_canton(), type_of_subproject=subproject_type))]
        else:
            [_subprojects.append(o) for o in Subproject.objects.filter(Q(cvd=cvd) | Q(location_subproject_realized=cvd.headquarters_village) | Q(canton_id=cvd.get_canton()))]

    subprojects = []
    for s in _subprojects:
        if not exists_id(subprojects, s.id):
            subprojects.append(s)
            
    subprojects = sorted(subprojects, key=lambda o: o.number)
    

    count = 0
    for elt in subprojects:
        
        try:
            datas["REGION"][count] = elt.get_canton().parent.parent.parent.name
        except Exception as exc:
            datas["REGION"][count] = None
        
        try:
            datas["PREFECTURE"][count] = elt.get_canton().parent.parent.name
        except Exception as exc:
            datas["PREFECTURE"][count] = None
        
        try:
            datas["COMMUNE"][count] = elt.get_canton().parent.name
        except Exception as exc:
            datas["COMMUNE"][count] = None
        
        try:
            datas["CANTON"][count] = elt.get_canton().name
        except Exception as exc:
            datas["CANTON"][count] = None
        
        try:
            datas["VILLAGE/CDV"][count] = elt.get_village().name
        except Exception as exc:
            datas["VILLAGE/CDV"][count] = None
        

        datas["N°"][count] = elt.number
        datas["num_kit"][count] = elt.joint_subproject_number
        datas["Longitude (x)"][count] = elt.longitude
        datas["Latitude (y)"][count] = elt.latitude
        datas["UNITE D'INTERVENTION"][count] = elt.intervention_unit
        datas["POPULATION"][count] = elt.population
        datas["H (BENEFICIAIRES DIRECTS)"][count] = elt.direct_beneficiaries_men
        datas["F (BENEFICIAIRES DIRECTS)"][count] = elt.direct_beneficiaries_women
        datas["T (BENEFICIAIRES DIRECTS)"][count] = (elt.direct_beneficiaries_men if elt.direct_beneficiaries_men else 0) + (elt.direct_beneficiaries_women if elt.direct_beneficiaries_women else 0)
        datas["H (BENEFICIAIRES INDIRECTS)"][count] = elt.indirect_beneficiaries_men
        datas["F (BENEFICIAIRES INDIRECTS)"][count] = elt.indirect_beneficiaries_women
        datas["T (BENEFICIAIRES INDIRECTS)"][count] = (elt.indirect_beneficiaries_men if elt.indirect_beneficiaries_men else 0) + (elt.indirect_beneficiaries_women if elt.indirect_beneficiaries_women else 0)
        datas["T_Benef_H"][count] = (elt.direct_beneficiaries_men if elt.direct_beneficiaries_men else 0) + (elt.indirect_beneficiaries_men if elt.indirect_beneficiaries_men else 0)
        datas["T_Benef_F"][count] = (elt.direct_beneficiaries_women if elt.direct_beneficiaries_women else 0) + (elt.indirect_beneficiaries_women if elt.indirect_beneficiaries_women else 0)
        datas["TOTAL (Bénéficiaires)"][count] = datas["T_Benef_H"][count] + datas["T_Benef_F"][count]

        datas["NOM DE L'AC"][count] = elt.facilitator_name
        datas["VAGUE"][count] = elt.wave
        datas["LOT"][count] = elt.lot
        datas["SECTEUR BENEFICIAIRE–SP"][count] = elt.subproject_sector
        datas["TYPE D'OUVRAGE (INFRASTRUCTURE)"][count] = elt.type_of_subproject

        list_of_villages_crossed_by_the_track_or_electrification_str = ""
        list_of_villages_crossed_by_the_track_or_electrification = elt.list_of_villages_crossed_by_the_track_or_electrification.all()
        _count = 0
        length = len(list_of_villages_crossed_by_the_track_or_electrification)
        for v in elt.list_of_villages_crossed_by_the_track_or_electrification.all():
            _count += 1
            list_of_villages_crossed_by_the_track_or_electrification_str += v.name
            if length != _count:
                list_of_villages_crossed_by_the_track_or_electrification_str += " ; "
        datas["LISTE DE VILLAGES TRAVERSÉ PAR LA PISTE OU L'ÉLECTRIFICATION"][count] = list_of_villages_crossed_by_the_track_or_electrification_str

        datas["INTITULE COMPLET DU SOUS-PROJET APPROUVES (Description)"][count] = elt.full_title_of_approved_subproject
        datas["TYPE DE TRAVAUX"][count] = elt.works_type
        datas["COUT ESTIMATIF"][count] = elt.estimated_cost
        datas["NIVEAU D'OBTENTION ATTESTATION DE DONATION"][count] = elt.level_of_achievement_donation_certificate
        datas["DATE D'APPROBATION CORA"][count] = elt.approval_date_cora
        datas["DATE SIGNATURE CONTRAT CONTROLEURS DE TRAVAUX BTP (CT)"][count] = elt.date_of_signature_of_contract_for_construction_supervisors
        datas["MONTANT DU CONTRAT CONTROLEURS DE TRAVAUX BTP (CT)"][count] = elt.amount_of_the_contract_for_construction_supervisors
        datas["DATE SIGNATURE CONTRAT CONTROLEURS EN SES (CSES)"][count] = elt.date_signature_contract_controllers_in_SES
        datas["MONTANT DU CONTRAT CONTROLEURS EN SES (CSES)"][count] = elt.amount_of_the_controllers_contract_in_SES
        datas["CONVENTION"][count] = elt.convention
        datas["N° CONTRAT ENTREPRISES DE TRAVAUX (ET)"][count] = elt.contract_number_of_work_companies
        datas["NOM DE L'ENTREPRISE ATTRIBUTAIRE ENTREPRISES DE TRAVAUX (ET)"][count] = elt.name_of_the_awarded_company_works_companies
        datas["DATE SIGNATURE CONTRAT ENTREPRISES DE TRAVAUX (ET)"][count] = elt.date_signature_contract_work_companies
        datas["MONTANT DU CONTRAT ENTREPRISES DE TRAVAUX (ET)"][count] = elt.contract_amount_work_companies
        datas["NOM DE L'ENTREPRISE ATTRIBUTAIRE ENTREPRISES DE FOURNITURE DE MOBILIERS ET EQUIPEMENTS (EFME)"][count] = elt.name_of_company_awarded_efme
        datas["DATE SIGNATURE CONTRAT ENTREPRISES DE FOURNITURE DE MOBILIERS ET EQUIPEMENTS (EFME)"][count] = elt.date_signature_contract_efme
        datas["MONTANT DU CONTRAT ENTREPRISES DE FOURNITURE DE MOBILIERS ET EQUIPEMENTS (EFME)"][count] = elt.contract_companies_amount_for_efme
        datas["DATE SIGNATURE CONTRAT ANIMATEUR COMMUNAUTAIRE (AC)"][count] = elt.date_signature_contract_facilitator
        datas["MONTANT DU CONTRAT ANIMATEUR COMMUNAUTAIRE (AC)"][count] = elt.amount_of_the_facilitator_contract
        datas["DATE DE LANCEMENT DU CHANTIER DANS LE VILLAGE (DATE NOTIFICATION DE L'ORDRE DE SERVICE)"][count] = elt.launch_date_of_the_construction_site_in_the_village
        datas["NIVEAU ACTUEL DE REALISATION PHYSIQUE DE L'OUVRAGE"][count] = elt.current_level_of_physical_realization_of_the_work
        datas["LONGUEUR DE LA PISTE (Km)"][count] = elt.length_of_the_track
        datas["PRONFONDEUR DU FORAGE (m)"][count] = elt.depth_of_drilling
        datas["DEBIT DU FORAGE (m3)"][count] = elt.drilling_flow_rate
        datas["""STATUT ACTUEL DU CHANTIER 
(Travaux en cours, Arrêt travaux, Abandon travaux, Réception technique, Réception provisoire etc,)"""][count] = elt.current_status_of_the_site
        datas["DUREE PREVUE DE REALISATION DES TRAVAUX (Mois)"][count] = elt.expected_duration_of_the_work
        datas["DATE PREVUE DE FIN DU CONTRAT"][count] = elt.expected_end_date_of_the_contract
        datas["MONTANT TOTAL DU MARCHE PAYE (Contrôle technique + Contrôle sauvegardes + Entreprise BTP + Entreprise Mobiliers + AC)"][count] = elt.total_contract_amount_paid
        datas["MONTANT DU FONDS D'ENTRETIEN ET DE MAINTENANCE (EMI)  PREVU POUR ETRE MOBILISE"][count] = elt.amount_of_the_care_and_maintenance_fund_expected_to_be_mobilized
        datas["MONTANT DU FONDS D'ENTRETIEN ET DE MAINTENANCE (EMI)  MOBILISE ET DEPOSE SUR LE COMPTE DU VILLAGE"][count] = elt.care_and_maintenance_amount_on_village_account
        datas["""Existence d'un Plan d'Entretien et de Maintenance (Plan EMI) élaboré par la Communauaté 
(Si Oui mettre 1; Si non mettre 0)"""][count] = 1 if elt.existence_of_maintenance_and_upkeep_plan_developed_by_community else 0
        datas["DATES DE RECEPTION TECHNIQUE DES MARCHE DE TRAVAUX (BTP OU FORAGE)"][count] = elt.date_of_technical_acceptance_of_work_contracts
        datas["DATES DE RECEPTION TECHNIQUE DES MARCHE DE FOURNITURE DE MOBILIERS ET EQUIPEMENTS"][count] = elt.technical_acceptance_date_for_efme_contracts
        datas["DATES DE RECEPTION PROVISOIRE DES MARCHE DE TRAVAUX (BTP OU FORAGE)"][count] = elt.date_of_provisional_acceptance_of_work_contracts
        datas["DATES DE RECEPTION PROVISOIRE DES MARCHE DE FOURNITURE DE MOBILIERS ET EQUIPEMENTS"][count] = elt.provisional_acceptance_date_for_efme_contracts
        datas["DATE DE REMISE OFFICIELLE DU MICROPROJET A LA COMMUNAUTE"][count] = elt.official_handover_date_of_the_microproject_to_the_community
        datas["DATE DE REMISE OFFICIELLE DU MICROPROJET AU SECTORIEL"][count] = elt.official_handover_date_of_the_microproject_to_the_sector

        datas["Groupe des femmes"][count] = 1 if elt.women_s_group else (0 if elt.women_s_group == False else "")
        datas["Groupe des jeunes"][count] = 1 if elt.youth_group else (0 if elt.youth_group == False else "")
        datas["Groupe des éleveurs/Agriculteurs"][count] = 1 if elt.breeders_farmers_group else (0 if elt.breeders_farmers_group == False else "")
        datas["Groupe des minorités ethniques"][count] = 1 if elt.ethnic_minority_group else (0 if elt.ethnic_minority_group == False else "")

        datas["Blocs latrine? (Oui, Non)"][count] = "Oui" if elt.has_latrine_blocs else ("Non" if elt.has_latrine_blocs == False else "")
        datas["Nombre de blocs latrine (de 3 cabines)"][count] = elt.number_of_latrine_blocks if elt.number_of_latrine_blocks else ""
        datas["Nombre de salle de classes"][count] = elt.number_of_classrooms if elt.number_of_classrooms else ""
        datas["Clôture"][count] = "Oui" if elt.has_fence else ("Non" if elt.has_fence == False else "")


        datas["COMMENTAIRES"][count] = elt.comments
        
        count += 1

    if not os.path.exists("media/"+file_type+"/subprojects"):
        os.makedirs("media/"+file_type+"/subprojects")

    file_name = "subprojects_" + _type.lower() + "_" + ((value_of_type.lower() + "_") if value_of_type else "")

    if file_type == "csv":
        file_path = file_type+"/subprojects/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".csv"
        pd.DataFrame(datas).to_csv("media/"+file_path)
    else:
        file_path = file_type+"/subprojects/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".xlsx"
        pd.DataFrame(datas).to_excel("media/"+file_path)

    if platform == "win32":
        # windows
        return file_path.replace("/", "\\\\")
    else:
        return file_path