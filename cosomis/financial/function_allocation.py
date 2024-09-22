from datetime import datetime
import pandas as pd
import os
from sys import platform
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum, Q

from administrativelevels.models import AdministrativeLevel
from financial.models.allocation import AdministrativeLevelAllocation



def get_value(elt):
    return elt if not pd.isna(elt) else None


def save_csv_datas_cantons_allocations_in_db(datas_file: dict, project_id=1) -> str:
    """Function to save the CSV datas in database"""
    
    at_least_one_save = False # Variable to determine if at least one is saved
    at_least_one_error = False # Variable to determine if at least one error is occurred
    at_least_error_name = False # Variable to determine if the name of canton is wrong
    text_errors = ""
    list_cantons_not_found = []
    list_cantons_not_found_full_infos = []
    list_cantons_multi_obj_found = []
    nbr_allocation_not_associate_to_priority = 0
    text_allocation_not_associate_to_priority = ""
    list_objects_exist = []
    nbr_other_errors = 0
    administrative_level_canton = None
    _is_object_error = False
    
    if datas_file:
        count = 0
        long = len(list(datas_file.values())[0])
        while count < long:
        
            
            try:
                _canton = get_value(datas_file["CANTON"][count])
                if _canton:
                    canton_file_data = str(_canton).upper()
                    allocation_1_1_v1 = get_value(datas_file["Allocation sc 1.1"][count])
                    allocation_1_1_v2 = get_value(datas_file["Allocation sc 1.1 V2"][count])
                    allocation_1_1_cfa = get_value(datas_file["""FCFA
1.1"""][count])
                    allocation_1_2 = get_value(datas_file["Allocation sc 1.2"][count])
                    allocation_1_2_cfa = get_value(datas_file["""FCFA
1.2"""][count])
                    allocation_1_3 = get_value(datas_file["Allocation sc 1.3"][count])
                    allocation_1_3_cfa = get_value(datas_file["""FCFA
1.3"""][count])
                    allocation_1_1 = None
                    if allocation_1_1_v2:
                        allocation_1_1 = allocation_1_1_v2
                    else:
                        allocation_1_1 = allocation_1_1_v1

                    components = {
                        2: {'dollars': allocation_1_1, 'cfa': allocation_1_1_cfa}, 
                        3: {'dollars': allocation_1_2, 'cfa': allocation_1_2_cfa}, 
                        6: {'dollars': allocation_1_3, 'cfa': allocation_1_3_cfa}
                    }
                    
                    try:
                        administrative_level_canton = AdministrativeLevel.objects.get(name=canton_file_data, type="Canton")
                    except AdministrativeLevel.DoesNotExist as exc:
                        _is_object_error = True
                        if canton_file_data not in list_cantons_not_found:
                            list_cantons_not_found.append(canton_file_data)
                            list_cantons_not_found_full_infos.append({
                                "REGION": get_value(datas_file["REGION"][count]),
                                "PREFECTURE": get_value(datas_file["PREFECTURE"][count]),
                                "COMMUNE": get_value(datas_file["COMMUNE"][count]),
                                "CANTON": get_value(datas_file["CANTON"][count])
                            })
                        text_errors += (f'\nLine N°{count} [{canton_file_data}]: {exc.__str__()}' if text_errors else f'Line N°{count} [{canton_file_data}]: {exc.__str__()}')
                        at_least_error_name = True
                        at_least_one_error = True
                    except AdministrativeLevel.MultipleObjectsReturned as exc:
                        _is_object_error = True
                        if canton_file_data not in list_cantons_multi_obj_found:
                            list_cantons_multi_obj_found.append(canton_file_data)
                        at_least_error_name = True
                        at_least_one_error = True
                        text_errors += (f'\nLine N°{count} [{canton_file_data}]: {exc.__str__()}' if text_errors else f'Line N°{count} [{canton_file_data}]: {exc.__str__()}')
                    
                    

                    if not _is_object_error and administrative_level_canton:
                        for k_id, v_money in components.items():
                            allocation = AdministrativeLevelAllocation()

                            allocation.administrative_level = administrative_level_canton
                            allocation.project_id = project_id
                            allocation.component_id = k_id
                            allocation.amount = v_money['cfa']
                            allocation.amount_in_dollars = v_money['dollars']
                            allocation.save(user={'is_superuser': True})


            except Exception as exc:
                text_errors += f'\nLine N°{count} [{canton_file_data}]: {exc.__str__()}'
                nbr_other_errors += 1
                at_least_one_error = True
                print(exc)    

            count += 1
            
    message = ""
    if at_least_one_save and not at_least_one_error:
        message = _("Success!")
    elif not at_least_one_save and not at_least_one_error:
        message = _("No items have been saved!")
    elif not at_least_one_save and at_least_one_error:
        if at_least_error_name:
            message = _("A problem has occurred! The name(s) of the canton(s) is wrong.")
        else:
            message = _("A problem has occurred!")
    elif at_least_one_save and at_least_one_error:
        if at_least_error_name:
            message = _("Some element(s) have not been saved! The name(s) of the canton(s) is wrong.")
        else:
            message = _("Some element(s) have not been saved!")

    summary_errors = "##########################################################Summary###################################################################\n"
    summary_errors += f'\nNumber of object not found errors: {len(list_cantons_not_found)} ==> {list_cantons_not_found}'
    summary_errors += f'\n\nNumber of Multiple object found errors: {len(list_cantons_multi_obj_found)} ==> {list_cantons_multi_obj_found}'
    summary_errors += f'\n\nNumber of other errors: {nbr_other_errors}'

    if text_allocation_not_associate_to_priority:
        summary_errors += "\n\n\n##########################################################Object AdministrativeLevelAllocation don't save###################################################################\n"
        summary_errors += f"\nNumber of the allocations don't save : {nbr_allocation_not_associate_to_priority}"
        summary_errors += text_allocation_not_associate_to_priority

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
    file_path = "logs/errors/upload_allocations_logs_errors_" + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") + ".txt"
    
    f = open("media/"+file_path, "a")
    f.write(summary_errors)
    f.close()

    return (message, file_path.replace("/", "\\\\") if platform == "win32" else file_path)



def sum_allocation_amount_by_component(component_id, is_administrative_level=True):
    return AdministrativeLevelAllocation.objects.filter(
            Q(administrative_level__isnull=False) if is_administrative_level else Q(cvd__isnull=False),
            component_id=component_id
        ).aggregate(Sum('amount'))['amount__sum']

def sum_allocation_amount_in_dollars_by_component(component_id, is_administrative_level=True):
    return AdministrativeLevelAllocation.objects.filter(
            Q(administrative_level__isnull=False) if is_administrative_level else Q(cvd__isnull=False),
            component_id=component_id
        ).aggregate(Sum('amount_in_dollars'))['amount_in_dollars__sum']

def sum_allocation_amount_by_administrative_level(administrative_level_id, is_administrative_level=True):
    return AdministrativeLevelAllocation.objects.filter(
            Q(administrative_level_id=administrative_level_id) if is_administrative_level else Q(cvd_id=administrative_level_id)
        ).aggregate(Sum('amount'))['amount__sum']

def sum_allocation_amount_in_dollars_by_administrative_level(administrative_level_id, is_administrative_level=True):
    return AdministrativeLevelAllocation.objects.filter(
            Q(administrative_level_id=administrative_level_id) if is_administrative_level else Q(cvd_id=administrative_level_id)
        ).aggregate(Sum('amount_in_dollars'))['amount_in_dollars__sum']

def sum_allocation_amount(is_administrative_level=True):
    return AdministrativeLevelAllocation.objects.filter(
        Q(administrative_level__isnull=False) if is_administrative_level else Q(cvd__isnull=False)
    ).aggregate(Sum('amount'))['amount__sum']

def sum_allocation_amount_in_dollars(is_administrative_level=True):
    return AdministrativeLevelAllocation.objects.filter(
        Q(administrative_level__isnull=False) if is_administrative_level else Q(cvd__isnull=False)
    ).aggregate(Sum('amount_in_dollars'))['amount_in_dollars__sum']