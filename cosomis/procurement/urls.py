from django.urls import path

from procurement import views

app_name = 'procurement'

urlpatterns = [
    path('', views.overview, name='overview'),
    path('commandes/ajouter/', views.OrderCreateView.as_view(), name='order_create'),
    path('commandes/<int:pk>/', views.order_detail, name='order_detail'),
    path('commandes/<int:pk>/modifier/', views.OrderUpdateView.as_view(), name='order_update'),
    path('commandes/<int:pk>/supprimer/', views.order_delete, name='order_delete'),
    path('commandes/<int:order_pk>/articles/ajouter/', views.line_create, name='line_create'),
    path('articles/<int:pk>/modifier/', views.LineUpdateView.as_view(), name='line_update'),
    path('articles/<int:pk>/supprimer/', views.line_delete, name='line_delete'),
    path('commandes/<int:order_pk>/livraisons/ajouter/', views.delivery_edit, name='delivery_create'),
    path('commandes/<int:order_pk>/livraisons/<int:pk>/modifier/', views.delivery_edit, name='delivery_update'),
    path('livraisons/<int:pk>/supprimer/', views.delivery_delete, name='delivery_delete'),
]
