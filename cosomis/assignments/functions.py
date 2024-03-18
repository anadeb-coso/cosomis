from .models import AssignAdministrativeLevelToFacilitator
from administrativelevels.models import AdministrativeLevel
from subprojects.models import Subproject
from cosomis.types import _QS
from cosomis.call_objects_from_other_db import grm_objects_call
from authentication.models import User as GrmUser

def get_subprojects_by_facilitator_id_and_project_id(facilitator_id, project_id) -> _QS:
    assigns_to_facilitator = AssignAdministrativeLevelToFacilitator.objects.filter(
        facilitator_id=facilitator_id, project_id=project_id, activated=True
    )

    subprojects = []
    for assign in assigns_to_facilitator:
        if assign.administrative_level and assign.administrative_level.cvd and \
            assign.administrative_level.cvd.headquarters_village and \
            assign.administrative_level.cvd.headquarters_village.id == assign.administrative_level.id:
            for subproject in assign.administrative_level.get_list_subprojects():
                if project_id in subproject.get_projects_ids():
                    subprojects.append(subproject)

    return Subproject.objects.filter(pk__in=[s.pk for s in subprojects])

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
    all_administrative_ids = grm_objects_call.get_object(GrmUser, email=facilitator.email).governmentworker.all_administrative_ids
    _administrativelevels = AdministrativeLevel.objects.filter(
        id__in=all_administrative_ids
    )
    
    administrativelevels = [adl for adl in _administrativelevels if (not parent_id or (parent_id and adl.parent and adl.parent_id==parent_id))]
    
    if type_adl in ("Village", "Canton"):
        if type_adl == "Canton":
            administrativelevels = list(set([adl.parent for adl in administrativelevels if adl.parent and (not parent_id or (parent_id and adl.parent.parent and adl.parent.parent_id==parent_id))]))
    else:
        administrativelevels = []

    return AdministrativeLevel.objects.filter(pk__in=[a.pk for a in administrativelevels])


def combine_administrativelevels_assigned_by_facilitator_stabilized_and_project_id(facilitator, project_id, type_adl="Village", parent_id=None) -> _QS:
    administrative_levels_stabilized = [] #get_stabilized_administrativelevels_of_facilitators_by_project_id(facilitator, project_id, type_adl.title())
    administrative_levels_assigned_for_cdd_process = get_administrativelevels_by_facilitator_id_and_project_id(facilitator.id, project_id, type_adl.title())

    return list(
        set(
            list(administrative_levels_stabilized) + list(administrative_levels_assigned_for_cdd_process)
        )
    )