from django.contrib.auth import views as auth_views
from django.urls import path

from usermanager.forms import EmailAuthenticationForm
from usermanager.tokens import jwt_views

app_name = 'usermanager'
urlpatterns = [
    path('', auth_views.LoginView.as_view(
        authentication_form=EmailAuthenticationForm,
        template_name='login.html',
        redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('user/manager/token/', auth_views.TemplateView.as_view(template_name='token.html'), name='token'),
    
    path('user/manager/generate-token/', jwt_views.generate_token_view, name='generate_token'),
    # path('user/manager/token/', jwt_views.token_view, name='token'),
]
