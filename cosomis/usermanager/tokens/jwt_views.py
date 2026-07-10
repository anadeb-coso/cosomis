from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from usermanager.tokens.jwt import create_token_for_user
from usermanager.models import UserToken
from django.contrib.auth import get_user_model
User = get_user_model()


@login_required
def generate_token_view(request):
    user = request.user
    
    token = create_token_for_user(user.id)

    return redirect('usermanager:token')

@login_required
def token_view(request):
    user = request.user
    try:
        user_token = UserToken.objects.get(user=user)
    except UserToken.DoesNotExist:
        user_token = None
        
    return render(request, 'token.html', {'user': user, 'user_token': user_token})

