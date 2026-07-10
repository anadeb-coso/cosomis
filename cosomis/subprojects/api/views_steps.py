from rest_framework.views import APIView
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from usermanager.api.auth.login import CheckUserSerializer
from subprojects.serializers import SubprojectStepSerializer, StepSerializer, LevelSerializer
from subprojects.models import Subproject, Step, SubprojectStep, Level
from assignments.functions import get_subprojects_by_facilitator_id_and_project_id
from .custom import CustomPagination
from subprojects.api.functions import convert_str_percent_to_float
from cosomis.constants import (
    STRUCTURE_IN_PROGRESS_STATUS, STRUCTURE_IN_PROGRESS_RANKING_LIST, IN_PROGRESS_RANKING, 
    APPROVED_BY_CORA_RANKING, NOT_APPROVED_BY_CORA_RANKING, ABANDONED_RANKING,
    INTERRUPTED_RANKING, COMPLETED_RANKING, RECEPTION_TECHNICAL_RANKING, PROVISIONAL_RECEPTION_RANKING, 
    HANDOVER_TO_COMMUNITY_RANKING, FINAL_RECEPTION_RANKING, OTHERS_CONTRACT_RANKING, FIRST_CONTRACT_RANKING
)


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
        o = serializer.save() #user=request.data.get('user')
        o.save(user=request.data.get('user'))
        step = validated_data.get('step')
        subproject = validated_data.get('subproject')
        
        _step = subproject.get_current_subproject_step
        if _step:
            if _step.ranking < IN_PROGRESS_RANKING and _step.ranking != NOT_APPROVED_BY_CORA_RANKING:
                subproject.current_status_of_the_site = "Identifié"
            elif _step.ranking == ABANDONED_RANKING:
                subproject.current_status_of_the_site = "Abandon"
            elif _step.ranking == INTERRUPTED_RANKING:
                subproject.current_status_of_the_site = "Arrêt"
            elif _step.ranking == HANDOVER_TO_COMMUNITY_RANKING:
                subproject.current_status_of_the_site = "Réception provisoire"
            else:
                subproject.current_status_of_the_site = _step.wording
            
            if step.ranking == APPROVED_BY_CORA_RANKING: # approved
                subproject.approval_date_cora = validated_data.get('begin')
            elif step.ranking in (FIRST_CONTRACT_RANKING, OTHERS_CONTRACT_RANKING): # contract_signed
                subproject.date_signature_contract_work_companies = validated_data.get('begin')
            # elif step.ranking == IN_PROGRESS_RANKING: # progress
            #     subproject.launch_date_of_the_construction_site_in_the_village = validated_data.get('begin')
            elif step.ranking == COMPLETED_RANKING: # completed
                subproject.work_completion_date = validated_data.get('begin')
                if validated_data.get('total_amount_spent'):
                    subproject.amount_spent_on_completing_the_infrastructure = validated_data.get('total_amount_spent')
            elif step.ranking == RECEPTION_TECHNICAL_RANKING: # technical_acceptance
                subproject.date_of_technical_acceptance_of_work_contracts = validated_data.get('begin')
            elif step.ranking == PROVISIONAL_RECEPTION_RANKING: # provisional_acceptance
                subproject.date_of_provisional_acceptance_of_work_contracts = validated_data.get('begin')
                if validated_data.get('total_amount_spent'):
                    subproject.amount_spent_on_infrastructure_up_to_provisional_acceptance = validated_data.get('total_amount_spent')
            elif step.ranking == HANDOVER_TO_COMMUNITY_RANKING: # handover_to_the_community
                subproject.official_handover_date_of_the_microproject_to_the_community = validated_data.get('begin')
            elif step.ranking == FINAL_RECEPTION_RANKING: # final_acceptance
                subproject.date_of_final_acceptance_of_the_work = validated_data.get('begin')
                if validated_data.get('total_amount_spent'):
                    subproject.exact_amount_spent = validated_data.get('total_amount_spent')

            if _step.percent:
                subproject.current_level_of_physical_realization_of_the_work = str(_step.percent)
                subproject.current_level_of_physical_realization_of_the_work_percent = _step.percent
            else:
                subproject.current_level_of_physical_realization_of_the_work = _step.wording
                subproject.current_level_of_physical_realization_of_the_work_percent = 0.0
            subproject.current_level_of_physical_realization_of_the_work_wording = subproject.get_current_subproject_step_and_level_without_percent

            subproject.save(user=request.data.get('user'))
        
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
                    Level.objects.filter(subproject_step__subproject__id=subproject_id).order_by('-begin', '-ranking', '-created_date'),
                    many=True).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
class RestGetSubprojectLevelsBySubprojectStepId(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, subproject_id, subproject_step_id, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data

        try:
            return Response(
                LevelSerializer(
                    Level.objects.filter(subproject_step_id=subproject_step_id, subproject_step__subproject__id=subproject_id).order_by('-begin', '-ranking', '-created_date'),
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
        
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        o = serializer.save()
        o.save(user=request.data.get('user'))
        subproject_step = validated_data.get('subproject_step')
        subproject = subproject_step.subproject
        percent = validated_data.get('percent')

        _step = subproject.get_current_subproject_step
        if _step and (_step.wording in STRUCTURE_IN_PROGRESS_STATUS or (_step.ranking in STRUCTURE_IN_PROGRESS_RANKING_LIST)):
            
            old_percent = convert_str_percent_to_float(subproject.current_level_of_physical_realization_of_the_work)
            new_percent = convert_str_percent_to_float(percent)
            
            if old_percent < new_percent:
                subproject.current_status_of_the_site = "En cours"
                subproject.current_level_of_physical_realization_of_the_work = str(percent if percent else "0")
                
                if percent:
                    subproject.current_level_of_physical_realization_of_the_work = str(percent)
                    subproject.current_level_of_physical_realization_of_the_work_percent = percent
                else:
                    subproject.current_level_of_physical_realization_of_the_work = "0"
                    subproject.current_level_of_physical_realization_of_the_work_percent = 0.0
                subproject.current_level_of_physical_realization_of_the_work_wording = subproject.get_current_subproject_step_and_level_without_percent

                subproject.save(user=request.data.get('user'))

        try:
            return Response(
                LevelSerializer(
                    Level.objects.filter(subproject_step_id=subproject_step.id, subproject_step__subproject__id=subproject.id).order_by('-begin', '-ranking', '-created_date'),
                    many=True).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )