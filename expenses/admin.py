from django.contrib import admin
from .models import Category, Expense, Budget, Alert

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category_type', 'user', 'created_at']
    list_filter = ['category_type', 'created_at']
    search_fields = ['name', 'user__username']
    ordering = ['user', 'name']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['description', 'amount', 'category', 'user', 'date', 'created_at']
    list_filter = ['category', 'date', 'created_at']
    search_fields = ['description', 'notes', 'user__username']
    date_hierarchy = 'date'
    ordering = ['-date', '-created_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'category')


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['name', 'amount', 'period', 'user', 'start_date', 'end_date', 'is_active']
    list_filter = ['period', 'is_active', 'created_at']
    search_fields = ['name', 'user__username']
    date_hierarchy = 'start_date'
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'category')


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['user', 'alert_type', 'budget', 'is_read', 'created_at']
    list_filter = ['alert_type', 'is_read', 'created_at']
    search_fields = ['user__username', 'message']
    ordering = ['-created_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'budget')