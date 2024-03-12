from rest_framework.views import APIView
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from usermanager.api.auth.login import CheckUserSerializer
from subprojects.serializers import SubprojectStepSerializer, StepSerializer, LevelSerializer
from subprojects.models import Subproject, Step, SubprojectStep, Level
from assignments.functions import get_subprojects_by_facilitator_id_and_project_id
from .custom import CustomPagination


class RestGetSteps(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data

        try:
            return Response(
                StepSerializer(
                    Step.objects.all().order_by('ranking'),
                    many=True).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )

class RestGetSubprojectSteps(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, subproject_id, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data

        try:
            return Response(
                SubprojectStepSerializer(
                    Subproject.objects.get(id=subproject_id).get_subproject_steps(),
                    many=True).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
class RestSaveSubprojectStep(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = SubprojectStepSerializer
    
    def post(self, request, *args, **kwargs):
        id = request.data.get('id')
        if id:
            serializer = self.serializer_class(SubprojectStep.objects.get(id=id), data=request.data, context={'request': request})
        else:
            serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        serializer.save()
        step = validated_data.get('step')
        subproject = validated_data.get('subproject')
        
        if step.ranking < 8 and step.ranking != 2:
            subproject.current_status_of_the_site = "Identifié"
        elif step.ranking == 9:
            subproject.current_status_of_the_site = "Abandon"
        elif step.ranking == 10:
            subproject.current_status_of_the_site = "Arrêt"
        elif step.ranking == 14:
            subproject.current_status_of_the_site = "Réception provisoire"
        else:
            subproject.current_status_of_the_site = step.wording
        
        if step.ranking == 3:
            subproject.approval_date_cora = validated_data.get('begin')
            
        subproject.current_level_of_physical_realization_of_the_work = str(step.percent if step.percent else step.wording)
        subproject.save()

        try:
            return Response(
                SubprojectStepSerializer(
                    Subproject.objects.get(id=subproject.id).get_subproject_steps(),
                    many=True).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )


class RestGetSubprojectLevels(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, subproject_id, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data

        try:
            return Response(
                LevelSerializer(
                    Level.objects.filter(subproject_step__subproject__id=subproject_id),
                    many=True).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )
        

class RestSaveSubprojectLevel(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = LevelSerializer
    
    def post(self, request, *args, **kwargs):
        id = request.data.get('id')
        if id:
            serializer = self.serializer_class(Level.objects.get(id=id), data=request.data, context={'request': request})
        else:
            serializer = self.serializer_class(data=request.data, context={'request': request})
        # print(request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        serializer.save()
        subproject_step = validated_data.get('subproject_step')
        subproject = subproject_step.subproject
        percent = validated_data.get('percent')

        subproject.current_status_of_the_site = "En cours"
        subproject.current_level_of_physical_realization_of_the_work = str(percent if percent else "0")
        subproject.save()

        try:
            return Response(
                LevelSerializer(
                    Level.objects.filter(subproject_step__subproject__id=subproject.id),
                    many=True).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )