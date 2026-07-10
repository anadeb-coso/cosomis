import jwt
from datetime import datetime, timedelta
from django.conf import settings # Assurez-vous que SECRET_KEY est bien défini
from usermanager.models import TOKEN_LIFETIME, UserToken
from django.db.models.signals import post_save
from django.utils import timezone

from django.contrib.auth import get_user_model
User = get_user_model()


def create_jwt_token(user_id):
    """Génère un JWT d'accès."""
    
    # 1. Définir l'expiration
    expiration_time = datetime.utcnow() + TOKEN_LIFETIME

    # 2. Définir le Payload
    payload = {
        'user_id': user_id,
        'exp': expiration_time,
        'iat': datetime.utcnow()
    }

    # 3. Encoder et signer
    # Utiliser une clé secrète forte et unique (ex: settings.SECRET_KEY)
    encoded_jwt = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm='HS256'
    )
    
    return encoded_jwt

def decode_jwt_token(token):
    """Décode et vérifie un JWT d'accès."""
    try:
        # 1. Décoder le token
        decoded_payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=['HS256']
        )
        
        return decoded_payload
    
    except jwt.ExpiredSignatureError:
        # Le token a expiré
        return None
    except jwt.InvalidTokenError:
        # Le token est invalide
        return None
    
def is_jwt_token_valid(token):
    """Vérifie si un JWT est valide et non expiré."""
    decoded_payload = decode_jwt_token(token)
    return decoded_payload is not None

def get_user_id_from_jwt(token):
    """Récupère l'ID utilisateur à partir du JWT."""
    decoded_payload = decode_jwt_token(token)
    if decoded_payload:
        return decoded_payload.get('user_id')
    return None

def refresh_jwt_token(token):
    """Rafraîchit un JWT en générant un nouveau token avec une nouvelle expiration."""
    decoded_payload = decode_jwt_token(token)
    if decoded_payload:
        user_id = decoded_payload.get('user_id')
        return create_jwt_token(user_id)
    return None

def jwt_token_remaining_time(token):
    """Retourne le temps restant avant l'expiration du JWT en secondes."""
    decoded_payload = decode_jwt_token(token)
    if decoded_payload:
        exp_timestamp = decoded_payload.get('exp')
        exp_datetime = datetime.utcfromtimestamp(exp_timestamp)
        remaining_time = exp_datetime - datetime.utcnow()
        return max(0, int(remaining_time.total_seconds()))
    return 0


def create_token_for_all_users():
    """Crée des tokens JWT pour tous les utilisateurs existants."""
    
    
    users = User.objects.all()
    tokens = {}
    
    for user in users:
        token = create_jwt_token(user.id)

        # Enregistrer ou mettre à jour le token dans UserToken
        UserToken.objects.update_or_create(
            user=user,
            defaults={'token': token, 'expires_at': timezone.now() + TOKEN_LIFETIME}
        )

        tokens[user.id] = token
    
    return tokens

# Create or update UserToken upon user creation
def create_token_for_user(user_id):
    
    token = create_jwt_token(user_id)

    UserToken.objects.update_or_create(
        user_id=user_id,
        defaults={'token': token, 'expires_at': timezone.now() + TOKEN_LIFETIME}
    )

    return token



# post_save.connect for User model to create UserToken automatically
def create_user_token(sender, instance, created, **kwargs):
    
    token = create_jwt_token(instance.id)
    
    UserToken.objects.update_or_create(
        user=instance,
        defaults={'token': token, 'expires_at': timezone.now() + TOKEN_LIFETIME}
    )

post_save.connect(create_user_token, sender=User)
