from django.db import models
from django.contrib.auth.hashers import make_password


class Role(models.Model):
    """RBAC Role — Customer, Staff, Admin"""
    CUSTOMER = 'customer'
    STAFF    = 'staff'
    ADMIN    = 'admin'

    ROLE_CHOICES = [
        (CUSTOMER, 'Customer'),
        (STAFF,    'Staff'),
        (ADMIN,    'Admin'),
    ]

    name        = models.CharField(max_length=50, choices=ROLE_CHOICES, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'roles'


class User(models.Model):
    """
    User model — KHÔNG dùng AbstractUser để tránh ràng buộc với Django auth.
    Không có Foreign Key sang bất kỳ service nào khác.
    """
    username     = models.CharField(max_length=150, unique=True)
    email        = models.EmailField(unique=True)
    password     = models.CharField(max_length=255)       # bcrypt hash
    full_name    = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address      = models.TextField(blank=True, null=True)
    # Soft reference đến Role (cùng DB nên có thể dùng FK nội bộ)
    role         = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, related_name='users')
    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def __str__(self):
        return f"{self.username} ({self.email})"

    class Meta:
        db_table = 'users'
