from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
import json
from subprojects.models import Subproject
from subprojects.sheet.functions import normalize_subproject_dict
from .utils import *
from cosomis.utils import save_subproject_tracking


@csrf_exempt
@require_http_methods(["GET"])
def subproject_list(request):
    if request.method == 'GET':
        
        subprojects_query = Subproject.objects.get_objects_by_general_filtre(request, None).get_actifs()#.prefetch_related(*m2m_fields_names)

        # Récuprération de la valeur de 'number' du sous-projet ayant 'number' le plus élevé
        highest_number = Subproject.objects.order_by('-number').values('number').first()
        highest_number = highest_number['number'] if highest_number else 0

        # Récuprération de la valeur de 'joint_subproject_number' du sous-projet ayant 'joint_subproject_number' le plus élevé
        highest_kit_joint_number = Subproject.objects.order_by('-joint_subproject_number').values('joint_subproject_number').first()
        highest_kit_joint_number = highest_kit_joint_number['joint_subproject_number'] if highest_kit_joint_number else 0
        
        subprojects_query_values = subprojects_query.values(*fields_list)
        subprojects_query_list = list(subprojects_query)
        count = 0
        for item in subprojects_query_values:
            # Gestion des champs ManyToMany
            for m2m_name in m2m_fields_names:
                try:
                    
                    subproject = subprojects_query_list[count]
                    m2m_values = getattr(subproject, m2m_name).all()
                    
                    item[m2m_name] = [
                        f"""[{elt.id}].{
                                (elt.name + ' (' + elt.parent.name + ')' if hasattr(elt, 'parent') and elt.parent else elt.name) if hasattr(elt, 'name') else (
                                    elt.full_title_of_approved_subproject if hasattr(elt, 'full_title_of_approved_subproject') else (
                                        elt.wording if hasattr(elt, 'wording') else elt.libelle
                                    )
                                )
                            }"""
                        for elt in m2m_values
                    ]
                except Exception as e:
                    item[m2m_name] = []
                    
            # Gestion des champs ForeignKey
            for fk_name, fk_model_name, fk_type, related_field_name in final_fk_fields:
                fk_id_field = f"{fk_name}__id"
                if fk_model_name.lower() == 'Subproject'.lower():
                    item[fk_name] = f"[{item.pop(fk_id_field, None)}.{item.pop(f'{fk_name}__location_subproject_realized__name', None)} ({item.pop(f'{fk_name}__location_subproject_realized__parent__name', None)})].{item.pop(related_field_name, None)}"
                elif fk_model_name in model_has_parent_attribute:
                    item[fk_name] = f"[{item.pop(fk_id_field, None)}].{item.pop(related_field_name, None)} ({item.pop(f'{fk_name}__parent__name', None)})"
                else:
                    item[fk_name] = f"[{item.pop(fk_id_field, None)}].{item.pop(related_field_name, None)}" 
                if any(x in item[fk_name] for x in ["[None].None", "[None].", ".None", "None."]):
                    item[fk_name] = ""
            count += 1
            
        return JsonResponse({
            'subprojects': list(subprojects_query_values),
            'last_numbers_info': _("Current highest subproject number is %(highest_number)s and highest joint subproject number is %(highest_kit_joint_number)s.") % {'highest_number': highest_number, 'highest_kit_joint_number': highest_kit_joint_number}
        }, safe=False)
    

@csrf_exempt
@require_http_methods(["POST"])
def subproject_create_or_update(request):
    
    if request.method == 'POST':
        try:
            _data = json.loads(request.body)

            data = _data['subproject']
            update_data = _data['update_data']
            
            data = normalize_subproject_dict(data)

            # Vérification des champs obligatoires
            missing_fields = [verbose_name for field, verbose_name in subproject_required_fields if field not in data or data[field] in [None, "", []]]
            if missing_fields:
                return JsonResponse({'error': f'{_("Required fields are missing or empty:")} {", ".join(str(f) for f in missing_fields)}'}, status=400)

            m2m_data = {k: data.pop(k, []) for k in subproject_m2m_fields_names if k in data}

            sp_id = data.pop("id", None)
            
            if sp_id:
                subproject, created = Subproject.objects.update_or_create(
                    id=sp_id,
                    defaults=data
                )
            else:
                subproject = Subproject.objects.create(**data)
                created = True
            
            edit = False
            
            if any(item for item in ['link_to_subproject', 'subproject_type_designation', 'joint_subproject_number'] if item in update_data):
                
                if subproject.link_to_subproject and subproject.subproject_type_designation == 'Subproject':
                    subproject.link_to_subproject = None
                    edit = True
                else:
                    subproject.subproject_type_designation = "Infrastructure"
                    if subproject.joint_subproject_number and subproject.subproject_type_designation != 'Subproject':
                        related_subproject = Subproject.objects.filter(
                            joint_subproject_number=subproject.joint_subproject_number,
                            infrastructure_deleted=False,
                            subproject_type_designation='Subproject'
                        ).exclude(id=subproject.id).first()
                        if related_subproject:
                            subproject.link_to_subproject = related_subproject
                            edit = True
                    elif subproject.link_to_subproject and subproject.subproject_type_designation != 'Subproject':
                        related_subproject = Subproject.objects.filter(
                            link_to_subproject_id=subproject.link_to_subproject.id,
                            infrastructure_deleted=False,
                            subproject_type_designation='Subproject'
                        ).exclude(id=subproject.id).first()
                        if related_subproject:
                            subproject.joint_subproject_number = related_subproject.joint_subproject_number
                    edit = True

            if 'location_subproject_realized' in update_data:
                if subproject.location_subproject_realized and subproject.location_subproject_realized.cvd:
                    subproject.cvd = subproject.location_subproject_realized.cvd
                    edit = True

                if subproject.component and subproject.component.name in ("COMPOSANTE 1.2", "COMPOSANTE 1.3") and not subproject.canton and (subproject.cvd or subproject.location_subproject_realized):
                    if subproject.location_subproject_realized and subproject.location_subproject_realized.type == 'Village':
                        subproject.canton = subproject.location_subproject_realized.parent
                        edit = True
                    elif subproject.cvd and subproject.cvd.headquarters_village and subproject.cvd.headquarters_village.type == 'Village':
                        subproject.canton = subproject.cvd.headquarters_village.parent
                        edit = True
                
                if subproject.canton:
                    for v in subproject.canton.administrativelevel_set.get_queryset():
                        subproject.list_of_beneficiary_villages.add(v)
                    edit = True
                elif subproject.cvd:
                    for v in subproject.cvd.get_villages():
                        subproject.list_of_beneficiary_villages.add(v)
                    edit = True
                elif subproject.component and subproject.component in ("COMPOSANTE 1.2", "COMPOSANTE 1.3") and subproject.location_subproject_realized and subproject.location_subproject_realized.type == 'Village' and subproject.location_subproject_realized.parent:
                    for v in subproject.location_subproject_realized.parent.administrativelevel_set.get_queryset():
                        subproject.list_of_beneficiary_villages.add(v)
                    edit = True

            if any(item for item in [
                    'current_level_of_physical_realization_of_the_work', 'current_status_of_the_site',
                    'official_handover_date_of_the_microproject_to_the_community', 'date_of_provisional_acceptance_of_work_contracts',
                    'date_of_technical_acceptance_of_work_contracts', 'work_completion_date', 'date_signature_contract_work_companies',
                    'approval_date_cora'
                ] if item in update_data) or not subproject.get_current_subproject_step:
                save_subproject_tracking([subproject])


            if edit:
                subproject.save(user=request.user)

            # Affectation des M2M
            for field_name, ids in m2m_data.items():
                getattr(subproject, field_name).set(ids)  # set remplace toute la liste
            
            # Récuprération de la valeur de 'number' du sous-projet ayant 'number' le plus élevé
            highest_number = Subproject.objects.order_by('-number').values('number').first()
            highest_number = highest_number['number'] if highest_number else 0

            # Récuprération de la valeur de 'joint_subproject_number' du sous-projet ayant 'joint_subproject_number' le plus élevé
            highest_kit_joint_number = Subproject.objects.order_by('-joint_subproject_number').values('joint_subproject_number').first()
            highest_kit_joint_number = highest_kit_joint_number['joint_subproject_number'] if highest_kit_joint_number else 0

            return JsonResponse({
                'id': subproject.id, 'message': _("Subproject successfully registered") if created else _("Subproject successfully modified"),
                'last_numbers_info': _("Current highest subproject number is %(highest_number)s and highest joint subproject number is %(highest_kit_joint_number)s.") % {'highest_number': highest_number, 'highest_kit_joint_number': highest_kit_joint_number}
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
@require_http_methods(["DELETE"])
def subproject_delete(request, pk):
    
    if request.method == 'DELETE':
    
        try:
            subproject = Subproject.objects.get(pk=pk)
        except Subproject.DoesNotExist:
            return JsonResponse({'error': _("Subproject not found")}, status=404)
    
        subproject.delete()

        # Récuprération de la valeur de 'number' du sous-projet ayant 'number' le plus élevé
        highest_number = Subproject.objects.order_by('-number').values('number').first()
        highest_number = highest_number['number'] if highest_number else 0

        # Récuprération de la valeur de 'joint_subproject_number' du sous-projet ayant 'joint_subproject_number' le plus élevé
        highest_kit_joint_number = Subproject.objects.order_by('-joint_subproject_number').values('joint_subproject_number').first()
        highest_kit_joint_number = highest_kit_joint_number['joint_subproject_number'] if highest_kit_joint_number else 0
        
        return JsonResponse({
            'message': _("Subproject successfully deleted"),
            'last_numbers_info': _("Current highest subproject number is %(highest_number)s and highest joint subproject number is %(highest_kit_joint_number)s.") % {'highest_number': highest_number, 'highest_kit_joint_number': highest_kit_joint_number}
        })
    

# @csrf_exempt
# @require_http_methods(["PUT"])
# def subproject_bulk_update(request):
#     try:
#         data = json.loads(request.body)
#         for item_data in data:
#             subproject_id = item_data.pop('id')
#             subproject = Subproject.objects.get(pk=subproject_id)
#             for field, value in item_data.items():
#                 setattr(subproject, field, value)
#             subproject.save()
#         return JsonResponse({'message': 'Modifications sauvegardées avec succès'})
#     except Exception as e:
#         return JsonResponse({'error': str(e)}, status=400)
    


def spreadsheet_view(request):
    return render(request, 'sheet/spreadsheet.html')