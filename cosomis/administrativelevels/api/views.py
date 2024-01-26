from drf_spectacular.utils import extend_schema
from rest_framework import parsers, renderers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination

from usermanager.api.auth.login import CheckUserSerializer
from administrativelevels.serializers import AdministrativeLevelSerializer, CVDWithAdministrativeLevelSerializer
from administrativelevels.models import AdministrativeLevel, CVD
from assignments.functions import get_administrativelevels_by_facilitator_id_and_project_id
from subprojects.api.custom import CustomPagination
from cosomis.types import _QS


class RestGetAdministrativeLevelByUser(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, type_adl: str, project_id: int, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data

        parent_id = request.GET.get("parent_id", None)
        if parent_id:
            parent_id = int(parent_id)

        administrative_levels: _QS = []
        if not hasattr(user, 'no_sql_user'):
            if type_adl.title() in ("Village", "Canton"):
                if parent_id:
                    administrative_levels = AdministrativeLevel.objects.filter(type=type_adl.title(), parent_id=parent_id)
                else:
                    administrative_levels = AdministrativeLevel.objects.filter(type=type_adl.title())
        else:
            if type_adl.title() in ("Village", "Canton"):
                if parent_id:
                    administrative_levels = get_administrativelevels_by_facilitator_id_and_project_id(user.id, project_id, type_adl=type_adl.title(), parent_id=parent_id)
                else:
                    administrative_levels = get_administrativelevels_by_facilitator_id_and_project_id(user.id, project_id, type_adl.title())
        print(administrative_levels)
        paginator = CustomPagination()
        paginated_data = paginator.paginate_queryset(administrative_levels, request)
        serializer = AdministrativeLevelSerializer(paginated_data, many=True, initial= {'user': user})
        
        return paginator.get_paginated_response(serializer.data)
    


class RestGetACVDByUser(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, project_id: int, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data

        parent_id = request.GET.get("parent_id", None)
        if parent_id:
            parent_id = int(parent_id)

        administrative_levels: _QS = []
        if not hasattr(user, 'no_sql_user'):
            if parent_id:
                administrative_levels = AdministrativeLevel.objects.filter(type="Village", parent_id=parent_id)
            else:
                administrative_levels = AdministrativeLevel.objects.filter(type="Village")
        else:
            if parent_id:
                administrative_levels = get_administrativelevels_by_facilitator_id_and_project_id(user.id, project_id, type_adl="Village", parent_id=parent_id)
            else:
                administrative_levels = get_administrativelevels_by_facilitator_id_and_project_id(user.id, project_id, "Village")
        
        cvds = CVD.objects.filter(
            pk__in=[
                adl.cvd.id for adl in administrative_levels if adl.cvd
            ]
        )


        paginator = CustomPagination()
        paginated_data = paginator.paginate_queryset(cvds, request)
        serializer = CVDWithAdministrativeLevelSerializer(paginated_data, many=True, initial= {'user': user})
        print(serializer.data)
        return paginator.get_paginated_response(serializer.data)