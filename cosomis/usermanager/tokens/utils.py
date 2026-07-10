import secrets
import string

def generate_secure_token(length=64):
    """Génère un jeton hexadécimal de longueur spécifiée."""
    # secrets.token_hex(n) génère une chaîne hexadécimale de longueur 2*n
    return secrets.token_hex(length // 2)

def generate_alphanumeric_token(length=32):
    """Génère un jeton alphanumérique aléatoire."""
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

