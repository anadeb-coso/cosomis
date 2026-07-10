import secrets
from django.db import models
from django.conf import settings
from datetime import datetime, timedelta
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


from cosomis.models_base import BaseModel

# Default token lifetime: 3 years
TOKEN_LIFETIME = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'] if settings.SIMPLE_JWT and 'ACCESS_TOKEN_LIFETIME' in settings.SIMPLE_JWT else timedelta(days=365*3)

class UserToken(BaseModel):
    """
    Stocke les jetons d'accès pour un service API tiers, liés à un utilisateur.
    """
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_token', verbose_name=_('User'))
    
    token = models.TextField()
    
    refresh_token = models.TextField(
        null=True, blank=True,
        default=timezone.now() + TOKEN_LIFETIME,
        verbose_name="Jeton de Rafraîchissement",
        help_text="Permet d'obtenir un nouveau jeton d'accès sans reconnexion."
    )
    
    service_name = models.CharField(max_length=100,default='External_API',verbose_name="Nom du Service Tiers")
    
    expires_at = models.DateTimeField(default=timezone.now() + TOKEN_LIFETIME)


    def __str__(self):
        return f"Jeton pour {self.user.username} - {self.service_name}"

    def is_valid(self):
        return self.expires_at > (timezone.now() + timedelta(minutes=5))
    



