from rest_framework import status
from rest_framework.response import Response
from rest_framework import permissions
from rest_framework.views import APIView

from administrativelevels.models import AdministrativeLevel
from administrativelevels.serializers import AdministrativeLevelSerializer


class GetAdministrativeLevelByTypeView(APIView):

    permission_classes = (permissions.IsAuthenticated,)
    def get(self, request, *args, **kwargs):
        _type = request.GET.get('type', None)

        return Response(AdministrativeLevelSerializer(AdministrativeLevel.objects.get_objects_by_general_filtre(self.request, None).filter(type=_type), many=True).data, status.HTTP_200_OK)