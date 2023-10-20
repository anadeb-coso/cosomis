from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.response import Response
from rest_framework import generics

from usermanager.serializers import UserSerializer


class RestGetAUsers(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    