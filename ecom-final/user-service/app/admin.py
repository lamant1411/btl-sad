from django.contrib import admin
from .models import User, Role

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'description']

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display  = ['id', 'username', 'email', 'full_name', 'role', 'is_active', 'created_at']
    list_filter   = ['role', 'is_active']
    search_fields = ['username', 'email', 'full_name']
    readonly_fields = ['created_at', 'updated_at']
