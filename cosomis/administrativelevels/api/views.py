from drf_spectacular.utils import extend_schema
from rest_framework import parsers, renderers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination

from usermanager.api.auth.login import CheckUserSerializer
from administrativelevels.serializers import AdministrativeLevelSerializer, CVDWithAdministrativeLevelSerializer, SimpleAdministrativeLevelSerializer
from administrativelevels.models import AdministrativeLevel, CVD
from assignments.functions import (
    # get_administrativelevels_by_facilitator_id_and_project_id,
    # get_stabilized_administrativelevels_of_facilitators_by_project_id,
    combine_administrativelevels_assigned_by_facilitator_stabilized_and_project_id
)
from subprojects.api.custom import CustomPagination
from cosomis.types import _QS

from subprojects.models import Project


class RestGetAdministrativeLevelByUser(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, type_adl: str, project_name: str, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data
        project  = Project.objects.filter(name=project_name).first()

        parent_id = request.GET.get("parent_id", None)
        if parent_id:
            parent_id = int(parent_id)

        administrative_levels: _QS = []
        if not hasattr(user, 'no_sql_user'):
            if type_adl.title() in ("Village", "Canton"):
                if parent_id:
                    administrative_levels = project.administrative_levels.filter(type=type_adl.title(), parent_id=parent_id).order_by('name')
                else:
                    administrative_levels = project.administrative_levels.filter(type=type_adl.title()).order_by('name')
        else:
            if type_adl.title() in ("Village", "Canton"):
                # if parent_id:
                # administrative_levels_stabilized = get_stabilized_administrativelevels_of_facilitators_by_project_id(user, project_id, type_adl=type_adl.title(), parent_id=parent_id)
                # administrative_levels_assigned_for_cdd_process = get_administrativelevels_by_facilitator_id_and_project_id(user.id, project_id, type_adl=type_adl.title(), parent_id=parent_id)
                # else:
                #     administrative_levels_stabilized = get_stabilized_administrativelevels_of_facilitators_by_project_id(user, project_id, type_adl.title())
                #     administrative_levels_assigned_for_cdd_process = get_administrativelevels_by_facilitator_id_and_project_id(user.id, project_id, type_adl.title())
                # administrative_levels = list(
                #     set(
                #         list(administrative_levels_stabilized) + list(administrative_levels_assigned_for_cdd_process)
                #     )
                # )

                if project:
                    administrative_levels = combine_administrativelevels_assigned_by_facilitator_stabilized_and_project_id(
                        user, project.id, type_adl=type_adl.title(), parent_id=parent_id
                    )
                else:
                    administrative_levels = combine_administrativelevels_assigned_by_facilitator_stabilized_and_project_id(
                        user, 1, type_adl=type_adl.title(), parent_id=parent_id
                    )
                
        paginator = CustomPagination()
        paginated_data = paginator.paginate_queryset(administrative_levels, request)
        serializer = AdministrativeLevelSerializer(paginated_data, many=True, initial= {'user': user, 'project_id': project.id if project else 1})
        
        return paginator.get_paginated_response(serializer.data)
    

class RestGetAdministrativeLevel(APIView):
    throttle_classes = ()
    permission_classes = ()
    
    def post(self, request, *args, **kwargs):
        
        adl_types = [t.title() for t in self.request.data.get('types', [])]
        parents_id = self.request.data.get('parents_id', [])

        project_name = request.GET.get("project_name", None)
        project = None
        projects_names = []
        if project_name:
            project  = Project.objects.filter(name=project_name).first()
            projects_names = [p.name for p in project.build_the_tree_structure()]
        
        if adl_types:
            if parents_id:
                # administrative_levels = project.administrative_levels.filter(type__in=adl_types, parent_id__in=parents_id).order_by('name') if project else AdministrativeLevel.objects.filter(type__in=adl_types, parent_id__in=parents_id).order_by('name')
                administrative_levels = AdministrativeLevel.objects.filter(type__in=adl_types, parent_id__in=parents_id, administrative_levels_projects__name__in=projects_names).distinct().order_by('name') if project else AdministrativeLevel.objects.filter(type__in=adl_types, parent_id__in=parents_id).distinct().order_by('name')
            else:
                # administrative_levels = project.administrative_levels.filter(type__in=adl_types).order_by('name') if project else AdministrativeLevel.objects.filter(type__in=adl_types).order_by('name')
                administrative_levels = AdministrativeLevel.objects.filter(type__in=adl_types, administrative_levels_projects__name__in=projects_names).distinct().order_by('name') if project else AdministrativeLevel.objects.filter(type__in=adl_types).distinct().order_by('name')
        else:
            if parents_id:
                # administrative_levels = project.administrative_levels.filter(parent_id__in=parents_id).order_by('name') if project else AdministrativeLevel.objects.filter(parent_id__in=parents_id).order_by('name')
                administrative_levels = AdministrativeLevel.objects.filter(parent_id__in=parents_id, administrative_levels_projects__name__in=projects_names).distinct().order_by('name') if project else AdministrativeLevel.objects.filter(parent_id__in=parents_id).distinct().order_by('name')
            else:
                # administrative_levels = project.administrative_levels.all().order_by('name') if project else AdministrativeLevel.objects.all().order_by('name')
                administrative_levels = AdministrativeLevel.objects.filter(administrative_levels_projects__name__in=projects_names).distinct().order_by('name') if project else AdministrativeLevel.objects.all().order_by('name')
                
        paginator = CustomPagination()
        paginated_data = paginator.paginate_queryset(administrative_levels, request)
        serializer = SimpleAdministrativeLevelSerializer(paginated_data, many=True)
        
        return paginator.get_paginated_response(serializer.data)

        
class RestGetACVDByUser(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, project_name: str, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data
        project  = Project.objects.filter(name=project_name).first()

        parent_id = request.GET.get("parent_id", None)
        if parent_id:
            parent_id = int(parent_id)

        administrative_levels: _QS = []
        if not hasattr(user, 'no_sql_user'):
            if parent_id:
                administrative_levels = project.administrative_levels.filter(type="Village", parent_id=parent_id).order_by('name')
            else:
                administrative_levels = project.administrative_levels.filter(type="Village").order_by('name')
        else:
            # if parent_id:
            #     administrative_levels = get_administrativelevels_by_facilitator_id_and_project_id(user.id, project_id, type_adl="Village", parent_id=parent_id)
            # else:
            #     administrative_levels = get_administrativelevels_by_facilitator_id_and_project_id(user.id, project_id, "Village")
            
            if project:
                administrative_levels = combine_administrativelevels_assigned_by_facilitator_stabilized_and_project_id(
                    user, project.id, type_adl="Village", parent_id=parent_id
                )
            else:
                administrative_levels = combine_administrativelevels_assigned_by_facilitator_stabilized_and_project_id(
                    user, 1, type_adl="Village", parent_id=parent_id
                )
        cvds = CVD.objects.filter(
            pk__in=[
                adl.cvd.id for adl in administrative_levels if adl.cvd
            ]
        ).order_by('name')


        paginator = CustomPagination()
        paginated_data = paginator.paginate_queryset(cvds, request)
        serializer = CVDWithAdministrativeLevelSerializer(paginated_data, many=True, initial= {'user': user, 'project_id': project.id if project else 1})
        
        return paginator.get_paginated_response(serializer.data)
    

class SaveAdministrativeLevelGeoLocation(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, pk, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data

        try:
            adl = AdministrativeLevel.objects.get(id=pk)
            adl.latitude = request.data['latitude']
            adl.longitude = request.data['longitude']
            adl = adl.save_and_return_object(user=user)
            
            return Response(
                {'success': 'ok'}, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )