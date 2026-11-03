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

        levels = AdministrativeLevel.objects.get_objects_by_general_filtre(self.request, None).filter(type=_type).select_related('parent')
        data = AdministrativeLevelSerializer(levels, many=True).data
        # nom du parent : distingue deux niveaux de même nom (ex. LOKO d'OTI 2 et LOKO de TANDJOUARE 1)
        parent_names = {level.id: level.parent.name if level.parent_id else None for level in levels}
        for item in data:
            item['parent_name'] = parent_names.get(item.get('id'))
        return Response(data, status.HTTP_200_OK)