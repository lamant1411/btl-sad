from django.urls import path
from .views import CartCreateView, CartDetailView, CartItemView

urlpatterns = [
    path('',                                  CartCreateView.as_view(),  name='cart-create'),
    path('<int:customer_id>/',                CartDetailView.as_view(),  name='cart-detail'),
    path('<int:customer_id>/items/',          CartItemView.as_view(),    name='cart-item-add'),
    path('<int:customer_id>/items/<int:product_id>/', CartItemView.as_view(), name='cart-item-delete'),
]
