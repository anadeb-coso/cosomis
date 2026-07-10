from rest_framework.views import APIView
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from django.db.models import Prefetch
from django.conf import settings

from usermanager.api.auth.login import CheckUserSerializer
from subprojects.serializers import (
    SubprojectWithChildrenLinkedSerializer, SaveSubprojectSerializer,
    SubprojectStandardSerializer, SubprojectWithChildrenLinkedSerializerSimple,
    SubprojectWithChildrenLinkedSerializerSimpleWithPriorities
)
from subprojects.models import Subproject, Project, SubprojectFile
from assignments.functions import get_subprojects_by_facilitator_id_and_project_id
from .custom import CustomPagination
from cosomis.constants import STRUCTURE_NOT_START_STATUS, STRUCTURE_IN_PROGRESS_STATUS, STRUCTURE_COMPLETED_STATUS, STRUCTURE_COMPLETED_ALL_STATUS


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
        subproject_id = request.GET.get("subproject_id", None)
        project_name = request.GET.get("project_name", None)
        project  = Project.objects.filter(name=project_name).first()

        search = request.GET.get("search", None)
        page_number = request.GET.get("page", None)
        subprojects = []

        if not hasattr(user, 'no_sql_user'):
            # subprojects = Subproject.objects.filter(projects__in=[project.id if project else 1]).get_actifs()
            if search:
                # if search == "All":
                #     subprojects = Subproject.objects.filter(projects__in=[project.id if project else 1]).get_actifs()
                search = search.upper()
                subprojects = Subproject.objects.filter(
                        Q(full_title_of_approved_subproject__icontains=search) | 
                        Q(location_subproject_realized__name__icontains=search) | 
                        Q(lsubproject_sector__icontains=search) | 
                        Q(type_of_subproject__icontains=search) | 
                        Q(works_type__icontains=search) | 
                        Q(cvd__name__icontains=search) | 
                        Q(facilitator_name__icontains=search),
                        projects__in=[project.id if project else 1]
                    ).get_actifs()
            else:
                subprojects = Subproject.objects.filter(projects__in=[project.id if project else 1]).get_actifs()
        else:
            subprojects = get_subprojects_by_facilitator_id_and_project_id(user.id, project.id if project else 1)

        if administrativelevel_id:
            administrativelevel_id = int(administrativelevel_id)
            subprojects = subprojects.filter(
                Q(link_to_subproject=None, location_subproject_realized__id=administrativelevel_id) | 
                Q(link_to_subproject=None, location_subproject_realized__parent__id=administrativelevel_id) | 
                Q(link_to_subproject=None, canton__id=administrativelevel_id)
            )
            
        
        elif cvd_id:
            cvd_id = int(cvd_id)
            subprojects = subprojects.filter(
                Q(link_to_subproject=None, cvd__id=cvd_id)
            )
        
        elif subproject_id:
            subproject_id = int(subproject_id)
            subprojects = subprojects.filter(
                Q(link_to_subproject__id=subproject_id)
            )
        else:
            subprojects = subprojects.filter(
                link_to_subproject=None
            )
        
        paginator = CustomPagination()
        paginated_data = paginator.paginate_queryset(subprojects.distinct(), request)
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
            subproject = subproject.save_and_return_object(user=user)
            
            return Response(
                SubprojectWithChildrenLinkedSerializer(subproject).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        
class RestSaveSubproject(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        s = CheckUserSerializer(data).data
        request.data['pk'] = request.data.get('id', None)
        subproject = Subproject.objects.get(id=request.data['pk'])
        
        if 'has_latrine_blocs' in request.data:
            del request.data['has_latrine_blocs']
        if 'number_of_latrine_blocks' in request.data:
            del request.data['number_of_latrine_blocks']
        if 'has_fence' in request.data:
            del request.data['has_fence']
        
        s = SubprojectStandardSerializer(instance=subproject,data=request.data)
        s.is_valid(raise_exception=True)
        # sub = Subproject.objects.get(id=request.data['pk'])
        
        # try:
        o = s.save()
        o.save(user=data)
        return Response(
            SubprojectWithChildrenLinkedSerializer(Subproject.objects.get(id=request.data['pk'])).data, 
            status=status.HTTP_200_OK
        )
        # except Exception as exc:
        #     return Response(
        #         {'error': exc.__str__()}, 
        #         status=status.HTTP_404_NOT_FOUND
        #     )



class RestGetSubprojectsByUserSimple(APIView):
    throttle_classes = ()
    permission_classes = ()
    # parser_classes = (parsers.FormParser, parsers.MultiPartParser, parsers.JSONParser,)
    # renderer_classes = (renderers.JSONRenderer,)
    serializer_class = CheckUserSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data

        infrastructures_status = request.data.get("infrastructures_status", STRUCTURE_COMPLETED_STATUS) # "Identifié", "En cours", "Achevé", "Réception technique", "Réception provisoire", "Réception définitive"
        include_inactif = request.data.get("include_inactif", None)
        administrativelevel_id = request.data.get("administrativelevel_id", None)
        cvd_id = request.data.get("cvd_id", None)
        subproject_id = request.data.get("subproject_id", None)
        project_name = request.data.get("project_name", None)
        project  = Project.objects.filter(name=project_name).first()
        include_none_infrastructure = request.data.get("include_none_infrastructure", False)
        

        search = request.GET.get("search", None)
        page_number = request.GET.get("page", None)
        subprojects = []
        
        query = Q()

        if not include_none_infrastructure:
            query &= Q(~(Q(number_of_infrastructures=0) | Q(number_of_infrastructures=None)))

        if project:
            query &= Q(projects__in=[project.id])

        if administrativelevel_id:
            administrativelevel_id = int(administrativelevel_id)
            query &= Q(
                Q(location_subproject_realized__id=administrativelevel_id) | 
                Q(location_subproject_realized__parent__id=administrativelevel_id) | 
                Q(canton__id=administrativelevel_id)
            )
        
        if cvd_id:
            cvd_id = int(cvd_id)
            query &= Q(cvd__id=cvd_id)
        
        if subproject_id:
            subproject_id = int(subproject_id)
            query &= Q(id=subproject_id)

        if infrastructures_status != "__all__":
            query &= Q(
                current_status_of_the_site__in=infrastructures_status
            )
        
        file_query = Q()
        for elt in STRUCTURE_COMPLETED_ALL_STATUS:
            file_query |= Q(subproject_step__wording__icontains=elt)
            file_query |= Q(name__icontains=elt)
            file_query |= Q(description__icontains=elt)
        
        if include_inactif:
            subprojects = Subproject.objects.filter(
                query
            )
        else:
            subprojects = Subproject.objects.filter(
                query
            ).get_actifs()

        subprojects.order_by("id").prefetch_related(
            Prefetch('subprojectfile_set', queryset=SubprojectFile.objects.filter(
                Q(
                    Q(
                        subproject_step__wording__in=STRUCTURE_COMPLETED_STATUS,
                    ) | 
                    Q(
                        name__in=STRUCTURE_COMPLETED_STATUS,
                    ) | 
                    Q(
                        description__in=STRUCTURE_COMPLETED_STATUS,
                    ) | 
                    file_query
                )
            ).exclude(
                Q(url__icontains=".pdf") | Q(url__icontains=".doc")
            ), to_attr='photos')
        ).distinct()
        
        paginator = CustomPagination()
        paginated_data = paginator.paginate_queryset(subprojects, request)

        if user and hasattr(user, 'email') and user.email == settings.PURS_USER_DEV_EMAIL:
            serializer = SubprojectWithChildrenLinkedSerializerSimpleWithPriorities(paginated_data, many=True)
        else:
            serializer = SubprojectWithChildrenLinkedSerializerSimple(paginated_data, many=True)
        
        return paginator.get_paginated_response(serializer.data)