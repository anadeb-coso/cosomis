from rest_framework import serializers

from django.contrib.auth.models import User, Group, Permission

		
class GroupSerializer(serializers.ModelSerializer):
	class Meta:
		"""docstring for Meta"""
		model = Group
		fields = '__all__'
		
class PermissionSerializer(serializers.ModelSerializer):
	class Meta:
		"""docstring for Meta"""
		model = Permission
		fields = '__all__'
		
class UserSerializer(serializers.ModelSerializer):
	groups = GroupSerializer(many=True) 
	user_permissions = PermissionSerializer(many=True) 
	class Meta:
		"""docstring for Meta"""
		model = User
		fields = ['id', 'is_superuser', 'last_name', 'first_name', 'email', 'groups', 'user_permissions']