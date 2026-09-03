from rest_framework import serializers
from django.contrib.auth.models import User
from django.db.models import Q
from django.contrib.auth.hashers import check_password
from django.utils.translation import gettext_lazy as _
from django.conf import settings

from authentication.models import Facilitator
from usermanager.tokens.jwt import get_user_id_from_jwt
from cosomis.functions_base import model_has_field
from usermanager.models import UserToken

#Login User Serialization
class CheckUserSerializer(serializers.Serializer):
	username = serializers.CharField(required=False)
	password = serializers.CharField(required=False)
	token = serializers.CharField(required=False)

	def validate(self, data):
		username = data.get('username')
		password = data.get('password')
		token = data.get('token')

		if not username and not token:
			raise serializers.ValidationError(_("Username or token is required"))
		if not password and not token:
			raise serializers.ValidationError(_("Password is required"))
				
		# Try to find user by token first
		if token:
			print(token)
			if token in settings.TOKEN_ALLOWED_TO_ACCESS_API:
				return User(id=None, username="TokenUser", is_active=True)
			
			user_id_from_jwt_token = get_user_id_from_jwt(token)
			if user_id_from_jwt_token:
				user = User.objects.filter(id=user_id_from_jwt_token).first()
				
				if model_has_field(Facilitator, 'user'):
					user = Facilitator.objects.using('cdd').filter(user_id=user_id_from_jwt_token).first() if not user else user
				
				if user:
					if not user.is_active:
						raise serializers.ValidationError(_("Your account is inactive"))

					user_token = None
					if model_has_field(Facilitator, 'user'):
						user_token = UserToken.objects.filter(token=token, user=user.user_id)
					else:
						user_token = UserToken.objects.filter(token=token, user=user)
					
					if not user_token.exists():
						raise serializers.ValidationError(_("Invalid token"))
					
					return user
				
			if not username:
				raise serializers.ValidationError(_("Invalid token"))
	
		# Fusion PostgreSQL : __iexact préserve la connexion insensible à la
		# casse (comportement MySQL utf8mb4_general_ci historique).
		user = User.objects.filter(Q(email__iexact=username) | Q(username__iexact=username)).first()
		user = Facilitator.objects.using('cdd').filter(Q(email__iexact=username) | Q(username__iexact=username)).first() if not user else user

		if user and check_password(password, user.password):
			if not user.is_active:
				return serializers.ValidationError(_("Your account is inactive"))
			return user
    			
		raise serializers.ValidationError(_("Incorrect credentials. If you have recently changed your password on one of our platforms, we recommend that you log out and log back in to that application. Thanks!"))