from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q, Count

from usermanager.api.auth.login import CheckUserSerializer
from subprojects.serializers import SubprojectSerializerSimple
from subprojects.models import Subproject, Project
from assignments.functions import (
    get_subprojects_by_facilitator_id_and_project_id,
    combine_administrativelevels_assigned_by_facilitator_stabilized_and_project_id,
)
from .custom import CustomPagination
from cosomis.constants import (
    STRUCTURE_IN_PROGRESS_STATUS,
    STRUCTURE_COMPLETED_STATUS,
    COMPLETED_RANKING,
    STRUCTURE_COMPLETED_ALL_STATUS,
    ABANDONED_LIST,
    INTERRUPTED_LIST,
    CONTRACT_TERMINATED_LIST,
    NOT_APPROVED_BY_CORA_LIST
)


# A Subproject row only represents a real infrastructure when number_of_infrastructures
# is set and non-zero (see CLAUDE.md's "Diagnostic des activités" spec).
INFRASTRUCTURE_QUALIFYING_Q = Q(~(Q(number_of_infrastructures=0) | Q(number_of_infrastructures=None)))

INFRASTRUCTURE_UNQUALIFYING_Q = Q((Q(number_of_infrastructures=0) | Q(number_of_infrastructures=None)))

# Statuts intermédiaires "DAO lancé" -> "En cours" listés séparément à la demande de l'utilisateur.
# "Remise en cours" est fondu dans "En cours" (même regroupement que STRUCTURE_IN_PROGRESS_STATUS).
STATUS_DISPLAY_ALIASES = {
    "Remise en cours": "En cours",
}

file_query_for_subproject = Q()
for elt in STRUCTURE_COMPLETED_ALL_STATUS:
    file_query_for_subproject |= Q(subprojectfile__subproject_step__wording__icontains=elt)
    file_query_for_subproject |= Q(subprojectfile__name__icontains=elt)
    file_query_for_subproject |= Q(subprojectfile__description__icontains=elt)

def _resolve_zone(user, project):
    project_id = project.id if project else 1

    if hasattr(user, 'no_sql_user'):
        subprojects = get_subprojects_by_facilitator_id_and_project_id(user.id, project_id)
        cantons = list(combine_administrativelevels_assigned_by_facilitator_stabilized_and_project_id(
            user, project_id, type_adl="Canton"
        ))
        villages = list(combine_administrativelevels_assigned_by_facilitator_stabilized_and_project_id(
            user, project_id, type_adl="Village"
        ))
    else:
        subprojects = Subproject.objects.filter(projects__in=[project_id]).get_actifs()
        if project:
            cantons = list(project.administrative_levels.filter(type="Canton"))
            villages = list(project.administrative_levels.filter(type="Village"))
        else:
            cantons = []
            villages = []

    cvd_ids = set(adl.cvd_id for adl in villages if adl.cvd_id)

    return subprojects, cantons, villages, cvd_ids


def _status_breakdown(base_qs):
    subproject_counts = dict(
        base_qs.filter(subproject_type_designation="Subproject")
        .values_list("current_status_of_the_site")
        .annotate(n=Count("id"))
        .values_list("current_status_of_the_site", "n")
    )
    infrastructure_counts = dict(
        base_qs.filter(INFRASTRUCTURE_QUALIFYING_Q)
        .values_list("current_status_of_the_site")
        .annotate(n=Count("id"))
        .values_list("current_status_of_the_site", "n")
    )

    un_infrastructure_counts = dict(
        base_qs.filter(INFRASTRUCTURE_UNQUALIFYING_Q)
        .values_list("current_status_of_the_site")
        .annotate(n=Count("id"))
        .values_list("current_status_of_the_site", "n")
    )

    breakdown = {}
    for raw_status in set(subproject_counts) | set(infrastructure_counts) | set(un_infrastructure_counts):
        display_status = STATUS_DISPLAY_ALIASES.get(raw_status, raw_status)
        entry = breakdown.setdefault(
            display_status,
            {"status": display_status, "subprojects_count": 0, "infrastructures_count": 0, "un_infrastructures_count": 0},
        )
        entry["subprojects_count"] += subproject_counts.get(raw_status, 0)
        entry["infrastructures_count"] += infrastructure_counts.get(raw_status, 0)
        entry["un_infrastructures_count"] += un_infrastructure_counts.get(raw_status, 0)

    return sorted(breakdown.values(), key=lambda e: e["status"] or "")


def _anomalies(base_qs):
    qualifying_qs = base_qs #.filter(INFRASTRUCTURE_QUALIFYING_Q)

    completed_qs = qualifying_qs.filter(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS)
    completed_missing_geoloc_count = completed_qs.filter(
        Q(latitude__isnull=True) | Q(latitude=0) | Q(latitude=0.0) | Q(longitude__isnull=True) | Q(longitude=0) | Q(longitude=0.0)
    ).count()
    completed_missing_images_count = completed_qs.annotate(
        completed_images_count=Count(
            "subprojectfile",
            filter=Q(
                Q(subprojectfile__subproject_step__wording__in=STRUCTURE_COMPLETED_STATUS) |
                Q(subprojectfile__name__in=STRUCTURE_COMPLETED_STATUS) |
                Q(subprojectfile__description__in=STRUCTURE_COMPLETED_STATUS) |
                file_query_for_subproject
            ) & ~Q(
                subprojectfile__url__icontains=".pdf"
            ) & ~Q(
                subprojectfile__url__icontains=".doc"
            ),
            distinct=True,
        )
    ).filter(completed_images_count__lt=3).count()

    in_progress_qs = qualifying_qs.filter(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS)
    in_progress_missing_geoloc_count = in_progress_qs.filter(
        Q(latitude__isnull=True) | Q(latitude=0) | Q(latitude=0.0) | Q(longitude__isnull=True) | Q(longitude=0) | Q(longitude=0.0)
    ).count()

    in_progress_missing_current_image_count = 0
    stalled_in_progress_count = 0
    for subproject in in_progress_qs:
        current_level = subproject.get_current_level_object
        if not (current_level and current_level.get_images().exists()):
            in_progress_missing_current_image_count += 1
        if subproject.is_delayed_update:
            stalled_in_progress_count += 1

    invalidated_files_infrastructures_count = qualifying_qs.filter(
        subprojectfile__validated=False
    ).distinct().count()

    abandoned_count = qualifying_qs.filter(current_status_of_the_site__in=ABANDONED_LIST)
    interrupted_count = qualifying_qs.filter(current_status_of_the_site__in=INTERRUPTED_LIST)
    contracts_currently_terminated_count = qualifying_qs.filter(current_level_of_physical_realization_of_the_work_wording__in=CONTRACT_TERMINATED_LIST)
    unapproved_infrastructure_count = qualifying_qs.filter(current_level_of_physical_realization_of_the_work_wording__in=NOT_APPROVED_BY_CORA_LIST)

    return {
        "completed_missing_images_count": completed_missing_images_count,
        "completed_missing_geoloc_count": completed_missing_geoloc_count,
        "in_progress_missing_current_image_count": in_progress_missing_current_image_count,
        "in_progress_missing_geoloc_count": in_progress_missing_geoloc_count,
        "invalidated_files_infrastructures_count": invalidated_files_infrastructures_count,
        "stalled_in_progress_count": stalled_in_progress_count,
        "abandoned_count": abandoned_count,
        "interrupted_count": interrupted_count,
        "contracts_currently_terminated_count": contracts_currently_terminated_count,
        "unapproved_infrastructure_count": unapproved_infrastructure_count,
    }


class RestGetSubprojectsDiagnosticSummaryByUser(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data

        project_name = request.GET.get("project_name", None)
        project = Project.objects.filter(name=project_name).first()

        base_qs, cantons, villages, cvd_ids = _resolve_zone(user, project)

        data = {
            "coverage": {
                "cantons_count": len(cantons),
                "cvds_count": len(cvd_ids),
                "villages_count": len(villages),
            },
            "totals": {
                "subprojects_count": base_qs.filter(subproject_type_designation="Subproject").count(),
                "infrastructures_count": base_qs.filter(INFRASTRUCTURE_QUALIFYING_Q).count(),
                "un_infrastructures_count": base_qs.filter(INFRASTRUCTURE_UNQUALIFYING_Q).count(),
            },
            "status_breakdown": _status_breakdown(base_qs),
            "anomalies": _anomalies(base_qs),
        }

        return Response(data, status=status.HTTP_200_OK)


class RestGetSubprojectsDiagnosticListByUser(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data

        project_name = request.GET.get("project_name", None)
        project = Project.objects.filter(name=project_name).first()

        filter_type = request.GET.get("filter_type", None)
        status_value = request.GET.get("status", None)
        designation = request.GET.get("designation", None)  # 'subproject' | 'infrastructure' | 'un_infrastructure' | None

        base_qs, *_rest = _resolve_zone(user, project)

        if designation == "subproject":
            qs = base_qs.filter(subproject_type_designation="Subproject")
        elif designation == "un_infrastructure":
            qs = base_qs.filter(INFRASTRUCTURE_UNQUALIFYING_Q)
        elif designation == "infrastructure":
            qs = base_qs.filter(INFRASTRUCTURE_QUALIFYING_Q)
        else:
            qs = base_qs

        if filter_type == "status":
            if status_value == "En cours":
                qs = qs.filter(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS)
            else:
                qs = qs.filter(current_status_of_the_site=status_value)

        elif filter_type == "completed_missing_images":
            qs = qs.filter(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).annotate(
                completed_images_count=Count(
                    "subprojectfile",
                    filter=Q(
                        Q(subprojectfile__subproject_step__wording__in=STRUCTURE_COMPLETED_STATUS) |
                        Q(subprojectfile__name__in=STRUCTURE_COMPLETED_STATUS) |
                        Q(subprojectfile__description__in=STRUCTURE_COMPLETED_STATUS) |
                        file_query_for_subproject
                    ) & ~Q(
                        subprojectfile__url__icontains=".pdf"
                    ) & ~Q(
                        subprojectfile__url__icontains=".doc"
                    ),
                    distinct=True,
                )
            ).filter(completed_images_count__lt=3)

        elif filter_type == "completed_missing_geoloc":
            qs = qs.filter(current_status_of_the_site__in=STRUCTURE_COMPLETED_STATUS).filter(
                Q(latitude__isnull=True) | Q(latitude=0) | Q(latitude=0.0) | Q(longitude__isnull=True) | Q(longitude=0) | Q(longitude=0.0)
            )

        elif filter_type == "in_progress_missing_current_image":
            qs = qs.filter(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS)
            ids = [
                sp.id for sp in qs
                if not (sp.get_current_level_object and sp.get_current_level_object.get_images().exists())
            ]
            qs = Subproject.objects.filter(pk__in=ids)

        elif filter_type == "in_progress_missing_geoloc":
            qs = qs.filter(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS).filter(
                Q(latitude__isnull=True) | Q(latitude=0) | Q(latitude=0.0) | Q(longitude__isnull=True) | Q(longitude=0) | Q(longitude=0.0)
            )

        elif filter_type == "invalidated_files":
            qs = qs.filter(subprojectfile__validated=False)

        elif filter_type == "stalled_in_progress":
            qs = qs.filter(current_status_of_the_site__in=STRUCTURE_IN_PROGRESS_STATUS)
            ids = [sp.id for sp in qs if sp.is_delayed_update]
            qs = Subproject.objects.filter(pk__in=ids)

        elif filter_type == "abandoned":
            qs = qs.filter(current_status_of_the_site__in=ABANDONED_LIST)
        
        elif filter_type == "interrupted":
            qs = qs.filter(current_status_of_the_site__in=INTERRUPTED_LIST)
        
        elif filter_type == "contracts_currently_terminated":
            qs = qs.filter(current_level_of_physical_realization_of_the_work_wording__in=CONTRACT_TERMINATED_LIST)
        
        elif filter_type == "unapproved_infrastructure":
            qs = qs.filter(current_level_of_physical_realization_of_the_work_wording__in=NOT_APPROVED_BY_CORA_LIST)

        paginator = CustomPagination()
        paginated_data = paginator.paginate_queryset(qs.order_by("id").distinct(), request)
        serializer = SubprojectSerializerSimple(paginated_data, many=True)

        return paginator.get_paginated_response(serializer.data)
