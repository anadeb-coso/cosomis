from .models import AssignAdministrativeLevelToFacilitator
from administrativelevels.models import AdministrativeLevel
from subprojects.models import Subproject
from cosomis.types import _QS
from cosomis.call_objects_from_other_db import grm_objects_call
from authentication.models import User as GrmUser
from no_sql_client import NoSQLClient
from authentication.models import Facilitator
from administrativelevels.functions_adl import get_cascade_adls_by_administrative_level_id

def get_subprojects_by_facilitator_id_and_project_id(facilitator_id, project_id) -> _QS:
    # assigns_to_facilitator = AssignAdministrativeLevelToFacilitator.objects.filter(
    #     facilitator_id=facilitator_id, project_id=project_id, activated=True
    # )

    # subprojects = []
    # # for assign in assigns_to_facilitator:
    # #     if assign.administrative_level and assign.administrative_level.cvd and \
    # #         assign.administrative_level.cvd.headquarters_village and \
    # #         assign.administrative_level.cvd.headquarters_village.id == assign.administrative_level.id:
    # #         for subproject in assign.administrative_level.get_list_subprojects():
    # #             if project_id in subproject.get_projects_ids():
    # #                 subprojects.append(subproject)
    
    # for adl in combine_administrativelevels_assigned_by_facilitator_stabilized_and_project_id(
    #     Facilitator.objects.using('cdd').get(id=facilitator_id), project_id
    # ):
    #     for subproject in adl.get_list_subprojects():
    #         if project_id in subproject.get_projects_ids():
    #             subprojects.append(subproject)
    adls = combine_administrativelevels_assigned_by_facilitator_stabilized_and_project_id(
        Facilitator.objects.using('cdd').get(id=facilitator_id), project_id
    )
    subprojects = [subproject for adl in adls for subproject in adl.get_list_subprojects() if project_id in subproject.get_projects_ids()]

    return Subproject.objects.filter(pk__in=[s.pk for s in subprojects]).get_actifs()


# def get_subprojects_by_facilitator_id_and_project_id(facilitator_id, project_id) -> _QS:
#     facilitator = Facilitator.objects.using('cdd').get(id=facilitator_id)

#     # Récupérer tous les sous-projets liés aux niveaux administratifs du facilitateur
#     administrative_levels = combine_administrativelevels_assigned_by_facilitator_stabilized_and_project_id(facilitator, project_id)
    
#     # Rassembler les IDs des sous-projets associés à ce projet
#     subproject_ids = set()
#     for adl in administrative_levels:
#         subproject_ids.update(
#             sp.pk for sp in adl.get_list_subprojects() if project_id in sp.get_projects_ids()
#         )

#     return Subproject.objects.filter(pk__in=subproject_ids).get_actifs()


def get_administrativelevels_by_facilitator_id_and_project_id(facilitator_id, project_id, type_adl="Village", parent_id=None) -> _QS:
    assigns_to_facilitator = AssignAdministrativeLevelToFacilitator.objects.filter(
        facilitator_id=facilitator_id, project_id=project_id, activated=True
    )
    
    administrativelevels = [assign.administrative_level for assign in assigns_to_facilitator if assign.administrative_level and (not parent_id or (parent_id and assign.administrative_level.parent and assign.administrative_level.parent_id==parent_id))]
    
    if type_adl in ("Village", "Canton"):
        if type_adl == "Canton":
            administrativelevels = list(set([adl.parent for adl in administrativelevels if adl.parent and (not parent_id or (parent_id and adl.parent.parent and adl.parent.parent_id==parent_id))]))
    else:
        administrativelevels = []

    return AdministrativeLevel.objects.filter(pk__in=[a.pk for a in administrativelevels])


def get_stabilized_administrativelevels_of_facilitators_by_project_id(facilitator, project_id, type_adl="Village", parent_id=None) -> _QS:
    # all_administrative_ids = grm_objects_call.get_object(GrmUser, email=facilitator.email).governmentworker.all_administrative_ids
    
    nsc = NoSQLClient()
    eadls = nsc.get_db('eadls')
    facilitators_stabilized = eadls.get_query_result({
        "type": 'adl',
        "representative.email": facilitator.email
    })[:]
    
    administrativelevels = []
    all_administrative_ids = []
    if facilitators_stabilized:
        all_administrative_ids = facilitators_stabilized[0]['administrative_regions']
        if 'additional_administrative_regions' in facilitators_stabilized[0] and facilitators_stabilized[0]['additional_administrative_regions']:
            if not all_administrative_ids:
                all_administrative_ids = []
            all_administrative_ids = all_administrative_ids + facilitators_stabilized[0]['additional_administrative_regions']
    #     _administrativelevels = AdministrativeLevel.objects.filter(
    #         id__in=[int(elt) for elt in all_administrative_ids if str(elt).isdigit()]
    #     )
    #     if type_adl == "Village" and _administrativelevels and _administrativelevels[0].type == 'Canton':
    #         administrativelevels_v = []
    #         for a in _administrativelevels:
    #             administrativelevels_v += list(a.children)
    #         _administrativelevels = administrativelevels_v
    #     elif type_adl == "Canton" and _administrativelevels and _administrativelevels[0].type == 'Canton':
    #         administrativelevels_v = []
    #         for a in _administrativelevels:
    #             administrativelevels_v += list(a.children)
    #         _administrativelevels = administrativelevels_v
    
    #     administrativelevels = [adl for adl in _administrativelevels if (not parent_id or (parent_id and adl.parent and adl.parent_id==parent_id))]
        
    #     if type_adl in ("Village", "Canton"):
    #         if type_adl == "Canton":
    #             administrativelevels = list(set([adl for adl in administrativelevels if adl.parent and (not parent_id or (parent_id and adl.parent.parent and adl.parent.parent_id==parent_id))]))
    #     else:
    #         administrativelevels = []

    # return AdministrativeLevel.objects.filter(pk__in=[a.pk for a in administrativelevels])

    return get_cascade_adls_by_administrative_level_id(list(set(all_administrative_ids)), type_adl, parent_id)


def combine_administrativelevels_assigned_by_facilitator_stabilized_and_project_id(facilitator, project_id, type_adl="Village", parent_id=None) -> _QS:
    administrative_levels_stabilized = get_stabilized_administrativelevels_of_facilitators_by_project_id(facilitator, project_id, type_adl.title(), parent_id)
    administrative_levels_assigned_for_cdd_process = get_administrativelevels_by_facilitator_id_and_project_id(facilitator.id, project_id, type_adl.title(), parent_id)

    return list(
        set(
            list(administrative_levels_stabilized) + list(administrative_levels_assigned_for_cdd_process)
        )
    )