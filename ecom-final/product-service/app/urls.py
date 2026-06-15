from django.urls import path
from .views import (
    CategoryListView, ProductListCreateView,
    ProductDetailView, StockUpdateView
)

urlpatterns = [
    path('',                    ProductListCreateView.as_view(), name='product-list-create'),
    path('<int:pk>/',           ProductDetailView.as_view(),     name='product-detail'),
    path('<int:pk>/stock/',     StockUpdateView.as_view(),       name='product-stock-update'),
    path('categories/',         CategoryListView.as_view(),      name='category-list'),
]
