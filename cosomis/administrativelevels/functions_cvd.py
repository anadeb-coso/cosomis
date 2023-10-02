from django.utils.translation import gettext_lazy as _
from django.db.models import Q
import os
from sys import platform
from datetime import datetime
import pandas as pd

from administrativelevels.models import CVD
from financial.models.bank import Bank
from financial.models.allocation import AdministrativeLevelAllocation
from financial.models.financial import BankTransfer


def get_value(elt):
    return elt if not pd.isna(elt) else None

def save_cvd_instead_of_csv_file_datas_in_db(datas_file: dict, project_id=1) -> str:
    """Function to save CVD instead of the CSV datas in database"""
    
    at_least_one_save = False # Variable to determine if at least one is saved
    at_least_one_error = False # Variable to determine if at least one error is occurred

    datas = {
        "REGION" : {}, "PREFECTURE" : {}, "COMMUNE" : {}, "CANTON" : {}, 
        "ID CVD": {}, "CVD": {}, "VILLAGES" : {}, "BANQUE": {}, "CODE BANQUE": {},
        "CODE GUICHET": {}, "N° DE COMPTE": {}, "RIB": {}, 
        "Nom du président du CVD": {}, "Tél du Président du CVD": {}, 
        "Nom du trésorier du CVD": {}, "Tél du trésorier du CVD": {}, 
        "Nom du secrétaire du CVD": {}, "Tél du secrétaire du CVD": {}
    }

    if datas_file:
        count = 0
        long = len(list(datas_file.values())[0])
        while count < long:
            try:
                cvd_id = get_value(datas_file["ID CVD"][count])
                cvd_name = get_value(datas_file["CVD"][count])
                bank = get_value(datas_file["BANQUE"][count])
                bank_code = get_value(datas_file["CODE BANQUE"][count])
                guichet_code = get_value(datas_file["CODE GUICHET"][count])
                account_number = get_value(datas_file["N° DE COMPTE"][count])
                rib = get_value(datas_file["RIB"][count])
                rib = (str(int(rib)) if int(rib) > 9 else f'0{int(rib)}') if rib else None
                president_name_of_the_cvd, president_phone_of_the_cvd = None, None
                treasurer_name_of_the_cvd, treasurer_phone_of_the_cvd = None, None
                secretary_name_of_the_cvd, secretary_phone_of_the_cvd = None, None
                
                try:
                    president_name_of_the_cvd = get_value(datas_file["Nom du président du CVD"][count])
                except Exception as exc:
                    pass
                try:
                    president_phone_of_the_cvd = get_value(datas_file["Tél du Président du CVD"][count])
                except Exception as exc:
                    pass
                try:
                    treasurer_name_of_the_cvd = get_value(datas_file["Nom du trésorier du CVD"][count])
                except Exception as exc:
                    pass
                try:
                    treasurer_phone_of_the_cvd = get_value(datas_file["Tél du trésorier du CVD"][count])
                except Exception as exc:
                    pass
                try:
                    secretary_name_of_the_cvd = get_value(datas_file["Nom du secrétaire du CVD"][count])
                except Exception as exc:
                    pass
                try:
                    secretary_phone_of_the_cvd = get_value(datas_file["Tél du secrétaire du CVD"][count])
                except Exception as exc:
                    pass
                

                
                
                try:
                    amount = get_value(datas_file["Montant alloué"][count])
                except Exception as exc:
                    pass
                try:
                    amount_in_dollars = get_value(datas_file["Montant alloué en dollars"][count])
                except Exception as exc:
                    pass
                try:
                    amount_after_signature_of_contracts = get_value(datas_file["Montant alloué apres signature"][count])
                except Exception as exc:
                    pass
                try:
                    amount_in_dollars_after_signature_of_contracts = get_value(datas_file["Montant alloué apres signature en dollars"][count])
                except Exception as exc:
                    pass
                try:
                    amount_transferred = get_value(datas_file["Montant viré"][count])
                except Exception as exc:
                    pass
                try:
                    amount_transferred_in_dollars = get_value(datas_file["Montant viré en dollars"][count])
                except Exception as exc:
                    pass


                
                cvd = CVD.objects.filter(id=cvd_id).first()
                if cvd:
                    if cvd_name != None:
                        cvd.name = cvd_name
                    cvd.bank = Bank.objects.filter(Q(name=bank) | Q(abbreviation=bank)).first()
                    if bank_code != None:
                        cvd.bank_code = bank_code
                    if guichet_code != None:
                        cvd.guichet_code = guichet_code
                    if account_number != None:
                        cvd.account_number = account_number
                    if rib != None:
                        cvd.rib = rib
                    if president_name_of_the_cvd != None:
                        cvd.president_name_of_the_cvd = president_name_of_the_cvd
                    if president_phone_of_the_cvd != None:
                        cvd.president_phone_of_the_cvd = president_phone_of_the_cvd
                    if treasurer_name_of_the_cvd != None:
                        cvd.treasurer_name_of_the_cvd = treasurer_name_of_the_cvd
                    if treasurer_phone_of_the_cvd != None:
                        cvd.treasurer_phone_of_the_cvd = treasurer_phone_of_the_cvd
                    if secretary_name_of_the_cvd != None:
                        cvd.secretary_name_of_the_cvd = secretary_name_of_the_cvd
                    if secretary_phone_of_the_cvd != None:
                        cvd.secretary_phone_of_the_cvd = secretary_phone_of_the_cvd
                    cvd = cvd.save_and_return_object()


                    try:
                        if amount != None:
                            allocation = AdministrativeLevelAllocation.objects.filter(cvd_id=cvd.id, amount=amount).first()
                            if not allocation:
                                allocation = AdministrativeLevelAllocation()
                                allocation.cvd = cvd
                                allocation.project_id = project_id
                                allocation.component_id = 2
                                allocation.amount = amount

                            if amount_in_dollars:
                                allocation.amount_in_dollars = amount_in_dollars
                            if amount_after_signature_of_contracts:
                                allocation.amount_after_signature_of_contracts = amount_after_signature_of_contracts
                            if amount_in_dollars_after_signature_of_contracts:
                                allocation.amount_in_dollars_after_signature_of_contracts = amount_in_dollars_after_signature_of_contracts
                            
                            allocation.save()
                    except:
                        pass
                    
                    try:
                        if amount_transferred:
                            bank_transfer = BankTransfer.objects.filter(cvd_id=cvd.id, amount_transferred=amount_transferred).first()
                            if not bank_transfer:
                                bank_transfer = BankTransfer()
                                bank_transfer.cvd = cvd
                                bank_transfer.project_id = project_id
                                bank_transfer.amount_transferred = amount_transferred
                            if amount_transferred_in_dollars:
                                bank_transfer.amount_transferred_in_dollars = amount_transferred_in_dollars
                            bank_transfer.save()
                            
                            at_least_one_save = True
                    except:
                        pass

            except Exception as exc:
                at_least_one_error = True
                print(exc)

            count += 1

    message = ""
    if at_least_one_save and not at_least_one_error:
        message = _("Success!")
    elif not at_least_one_save and not at_least_one_error:
        message = _("No items have been saved!")
    elif not at_least_one_save and at_least_one_error:
        message = _("A problem has occurred!")
    elif at_least_one_save and at_least_one_error:
        message = _("Some element(s) have not been saved!")

    return message


def get_cvd_under_file_excel_or_csv(file_type, administrative_levels_ids) -> str:

    datas = {
        "REGION" : {}, "PREFECTURE" : {}, "COMMUNE" : {}, "CANTON" : {}, 
        "ID CVD": {}, "CVD": {}, "VILLAGES" : {}, "BANQUE": {}, "CODE BANQUE": {},
        "CODE GUICHET": {}, "N° DE COMPTE": {}, "RIB": {}, 
        "Nom du président du CVD": {}, "Tél du Président du CVD": {}, 
        "Nom du trésorier du CVD": {}, "Tél du trésorier du CVD": {}, 
        "Nom du secrétaire du CVD": {}, "Tél du secrétaire du CVD": {}
    }

    cvds = CVD.objects.filter(
        headquarters_village__id__in=administrative_levels_ids
    ).order_by(
        'headquarters_village__parent__parent__parent__parent__name', 
        'headquarters_village__parent__parent__parent__name', 
        'headquarters_village__parent__parent__name', 
        'headquarters_village__parent__name', 'name'
        )

    count = 0
    for elt in cvds:
        
        try:
            datas["REGION"][count] = elt.headquarters_village.parent.parent.parent.parent.name
        except Exception as exc:
            datas["REGION"][count] = None
        
        try:
            datas["PREFECTURE"][count] = elt.headquarters_village.parent.parent.parent.name
        except Exception as exc:
            datas["PREFECTURE"][count] = None
        
        try:
            datas["COMMUNE"][count] = elt.headquarters_village.parent.parent.name
        except Exception as exc:
            datas["COMMUNE"][count] = None
        
        try:
            datas["CANTON"][count] = elt.headquarters_village.parent.name
        except Exception as exc:
            datas["CANTON"][count] = None
        
        try:
            datas["ID CVD"][count] = elt.id
            datas["CVD"][count] = elt.name
        except Exception as exc:
            datas["ID CVD"][count] = None
            datas["CVD"][count] = elt.name
        
        datas["VILLAGES"][count] = "; ".join([village.name for village in elt.get_villages()])

        datas["BANQUE"][count] = elt.bank
        datas["CODE BANQUE"][count] = elt.bank_code
        datas["CODE GUICHET"][count] = elt.guichet_code
        datas["N° DE COMPTE"][count] = elt.account_number
        datas["RIB"][count] = elt.rib
        datas["Nom du président du CVD"][count] = elt.president_name_of_the_cvd
        datas["Tél du Président du CVD"][count] = elt.president_phone_of_the_cvd
        datas["Nom du trésorier du CVD"][count] = elt.treasurer_name_of_the_cvd
        datas["Tél du trésorier du CVD"][count] = elt.treasurer_phone_of_the_cvd
        datas["Nom du secrétaire du CVD"][count] = elt.secretary_name_of_the_cvd
        datas["Tél du secrétaire du CVD"][count] = elt.secretary_phone_of_the_cvd
        
        count += 1

    if not os.path.exists("media/"+file_type+"/cvds"):
        os.makedirs("media/"+file_type+"/cvds")

    file_name = "cvds_"

    if file_type == "csv":
        file_path = file_type+"/cvds/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".csv"
        pd.DataFrame(datas).to_csv("media/"+file_path)
    else:
        file_path = file_type+"/cvds/" + file_name + str(datetime.today().replace(microsecond=0)).replace("-", "").replace(":", "").replace(" ", "_") +".xlsx"
        pd.DataFrame(datas).to_excel("media/"+file_path)

    if platform == "win32":
        # windows
        return file_path.replace("/", "\\\\")
    else:
        return file_path