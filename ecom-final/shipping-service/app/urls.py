from django.urls import path
from .views import ShipmentDetailView
urlpatterns = [path('<int:order_id>/', ShipmentDetailView.as_view(), name='shipment-detail')]
