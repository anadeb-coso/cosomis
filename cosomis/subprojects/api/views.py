from rest_framework.views import APIView
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from usermanager.api.auth.login import CheckUserSerializer
from subprojects.serializers import SubprojectWithChildrenLinkedSerializer
from subprojects.models import Subproject
from assignments.functions import get_subprojects_by_facilitator_id_and_project_id
from .custom import CustomPagination


class RestGetSubprojectsByUser(APIView):
    throttle_classes = ()
    permission_classes = ()
    # parser_classes = (parsers.FormParser, parsers.MultiPartParser, parsers.JSONParser,)
    # renderer_classes = (renderers.JSONRenderer,)
    serializer_class = CheckUserSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data

        administrativelevel_id = request.GET.get("administrativelevel_id", None)
        cvd_id = request.GET.get("cvd_id", None)
        project_id = request.GET.get("project_id", None)

        search = request.GET.get("search", None)
        page_number = request.GET.get("page", None)
        subprojects = []

        if not hasattr(user, 'no_sql_user'):
            if search:
                if search == "All":
                    subprojects = Subproject.objects.filter()
                search = search.upper()
                subprojects =    Subproject.objects.filter(
                        Q(full_title_of_approved_subproject__icontains=search) | 
                        Q(location_subproject_realized__name__icontains=search) | 
                        Q(lsubproject_sector__icontains=search) | 
                        Q(type_of_subproject__icontains=search) | 
                        Q(works_type__icontains=search) | 
                        Q(cvd__name__icontains=search) | 
                        Q(facilitator_name__icontains=search)
                    )
            else:
                subprojects =    Subproject.objects.filter()
        else:
            subprojects = get_subprojects_by_facilitator_id_and_project_id(user.id, 1)

        if administrativelevel_id:
            administrativelevel_id = int(administrativelevel_id)
            subprojects = subprojects.filter(
                Q(link_to_subproject=None, location_subproject_realized__id=administrativelevel_id) | 
                Q(link_to_subproject=None, location_subproject_realized__parent__id=administrativelevel_id) | 
                Q(link_to_subproject=None, canton__id=administrativelevel_id)
            )
            # print(subprojects)
        
        elif cvd_id:
            cvd_id = int(cvd_id)
            subprojects = subprojects.filter(
                Q(link_to_subproject=None, cvd__id=cvd_id)
            )
        
        elif project_id:
            project_id = int(project_id)
            subprojects = subprojects.filter(
                Q(link_to_subproject__id=project_id)
            )
        else:
            subprojects = subprojects.filter(
                link_to_subproject=None
            )
        
        paginator = CustomPagination()
        paginated_data = paginator.paginate_queryset(subprojects, request)
        serializer = SubprojectWithChildrenLinkedSerializer(paginated_data, many=True)
        
        return paginator.get_paginated_response(serializer.data)
    


class RestGetSubprojectByUser(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, pk, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data

        try:
            return Response(
                SubprojectWithChildrenLinkedSerializer(Subproject.objects.get(id=pk)).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        

class SaveSubprojectsGeoLocation(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, pk, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data

        try:
            subproject = Subproject.objects.get(id=pk)
            subproject.latitude = request.data['latitude']
            subproject.longitude = request.data['longitude']
            subproject = subproject.save_and_return_object()
            
            return Response(
                SubprojectWithChildrenLinkedSerializer(subproject).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )
        