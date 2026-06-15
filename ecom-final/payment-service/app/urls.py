from django.urls import path
from .views import PaymentProcessView, PaymentDetailView

urlpatterns = [
    path('',                      PaymentProcessView.as_view(), name='payment-process'),
    path('<int:order_id>/',       PaymentDetailView.as_view(),  name='payment-detail'),
]
