import logging
import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, Role
from .serializers import RegisterSerializer, LoginSerializer, UserSerializer

logger = logging.getLogger(__name__)


def _get_tokens_for_user(user):
    """Tạo JWT token pair từ user object (không dùng Django auth backend)."""
    # Dùng simplejwt với custom payload
    from rest_framework_simplejwt.tokens import RefreshToken as RT
    # Tạo token với user_id trong payload
    refresh = RT()
    refresh['user_id']   = user.id
    refresh['username']  = user.username
    refresh['role']      = user.role.name if user.role else 'customer'

    return {
        'refresh': str(refresh),
        'access':  str(refresh.access_token),
    }


def _create_cart_for_user(user_id: int):
    """
    Gọi Cart Service để khởi tạo giỏ hàng rỗng sau khi đăng ký.
    Áp dụng Resilience Pattern: timeout=3.0 + try-except.
    """
    cart_url = getattr(settings, 'CART_SERVICE_URL', 'http://cart-service:8002')
    try:
        resp = requests.post(
            f"{cart_url}/api/carts/",
            json={"customer_id": user_id},
            timeout=3.0
        )
        if resp.status_code not in (200, 201):
            logger.warning(f"Cart Service returned {resp.status_code} for user {user_id}")
    except requests.exceptions.Timeout:
        logger.warning(f"Cart Service timeout — giỏ hàng sẽ được tạo sau (user_id={user_id})")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Cart Service unavailable: {e} — Eventual Consistency sẽ xử lý sau")


class RegisterView(APIView):
    """POST /api/users/auth/register — Đăng ký tài khoản mới."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Gán role Customer mặc định
        customer_role, _ = Role.objects.get_or_create(
            name=Role.CUSTOMER,
            defaults={'description': 'Khách hàng mua sắm'}
        )
        user = serializer.save()
        user.role = customer_role
        user.save(update_fields=['role'])

        # Gọi ngầm Cart Service (Resilience: không crash nếu Cart Service chưa sẵn sàng)
        _create_cart_for_user(user.id)

        tokens = _get_tokens_for_user(user)
        return Response({
            "message": "Đăng ký thành công.",
            "user": UserSerializer(user).data,
            **tokens
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """POST /api/users/auth/login — Đăng nhập, trả về JWT."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user   = serializer.validated_data['user']
        tokens = _get_tokens_for_user(user)

        return Response({
            "message": "Đăng nhập thành công.",
            "user": UserSerializer(user).data,
            **tokens
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """POST /api/users/auth/logout — Blacklist refresh token."""
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Đăng xuất thành công."}, status=status.HTTP_200_OK)
        except Exception:
            return Response({"error": "Token không hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    """GET /api/users/me — Lấy thông tin cá nhân (yêu cầu JWT)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Lấy user_id từ JWT payload (vì ta không dùng Django auth)
        user_id = request.auth.payload.get('user_id')
        try:
            user = User.objects.select_related('role').get(pk=user_id)
            return Response(UserSerializer(user).data)
        except User.DoesNotExist:
            return Response({"error": "Người dùng không tồn tại."}, status=status.HTTP_404_NOT_FOUND)

    def patch(self, request):
        """PATCH /api/users/me — Cập nhật thông tin cá nhân."""
        user_id = request.auth.payload.get('user_id')
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"error": "Người dùng không tồn tại."}, status=status.HTTP_404_NOT_FOUND)

        allowed_fields = ['full_name', 'phone_number', 'address']
        for field in allowed_fields:
            if field in request.data:
                setattr(user, field, request.data[field])
        user.save()
        return Response(UserSerializer(user).data)


class UserDetailView(APIView):
    """GET /api/users/<user_id>/ — Internal endpoint cho các service khác."""
    permission_classes = [AllowAny]  # Chỉ accessible từ internal network

    def get(self, request, user_id):
        try:
            user = User.objects.select_related('role').get(pk=user_id, is_active=True)
            return Response({
                "id":       user.id,
                "username": user.username,
                "email":    user.email,
                "role":     user.role.name if user.role else 'customer',
            })
        except User.DoesNotExist:
            return Response({"error": "Người dùng không tồn tại."}, status=status.HTTP_404_NOT_FOUND)
