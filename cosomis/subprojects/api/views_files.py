from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from django.db.models import Q, Case, When, Value, IntegerField

from usermanager.api.auth.login import CheckUserSerializer
from subprojects.serializers import FileCommentsSerializer
from subprojects.models import SubprojectFile




class RestGetFileComments(APIView):
    throttle_classes = ()
    permission_classes = ()
    serializer_class = CheckUserSerializer
    
    def post(self, request, pk, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data

        try:
            subproject_file = SubprojectFile.objects.get(id=pk)
            
            return Response(
                FileCommentsSerializer(
                    subproject_file.comments.order_by("-updated_date"), 
                    many=True
                ).data, 
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {'error': exc.__str__()}, 
                status=status.HTTP_404_NOT_FOUND
            )