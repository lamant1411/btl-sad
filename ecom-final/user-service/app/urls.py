from django.urls import path
from .views import RegisterView, LoginView, LogoutView, UserProfileView, UserDetailView

urlpatterns = [
    # Auth endpoints
    path('auth/register/', RegisterView.as_view(),  name='user-register'),
    path('auth/login/',    LoginView.as_view(),     name='user-login'),
    path('auth/logout/',   LogoutView.as_view(),    name='user-logout'),

    # User profile
    path('me/',            UserProfileView.as_view(), name='user-profile'),

    # Internal — cho các service khác gọi
    path('<int:user_id>/', UserDetailView.as_view(),  name='user-detail'),
]
