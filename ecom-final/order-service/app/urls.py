from django.urls import path
from .views import OrderListView, OrderCreateView, OrderDetailView

urlpatterns = [
    path('',          OrderListView.as_view(),   name='order-list'),
    path('create/',   OrderCreateView.as_view(), name='order-create'),
    path('<int:pk>/', OrderDetailView.as_view(),  name='order-detail'),
]
