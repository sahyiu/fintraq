from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal

class Category(models.Model):
    """Expense categories"""
    CATEGORY_TYPES = [
        ('food', 'Food & Dining'),
        ('transport', 'Transportation'),
        ('utilities', 'Utilities'),
        ('entertainment', 'Entertainment'),
        ('healthcare', 'Healthcare'),
        ('shopping', 'Shopping'),
        ('education', 'Education'),
        ('housing', 'Housing'),
        ('other', 'Other'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPES, default='other')
    description = models.TextField(blank=True, null=True)
    color = models.CharField(max_length=7, default='#6366f1')  # Hex color code
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']
        unique_together = ['user', 'name']
    
    def __str__(self):
        return self.name


class Expense(models.Model):
    """Individual expense records"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='expenses')
    budget = models.ForeignKey('Budget', on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    description = models.CharField(max_length=255)
    notes = models.TextField(blank=True, null=True)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['user', 'category']),
        ]
    
    def __str__(self):
        return f"{self.description} - ₱{self.amount}"


class Budget(models.Model):
    """Budget limits for categories"""
    PERIOD_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='budgets', null=True, blank=True)
    name = models.CharField(max_length=100)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES, default='monthly')
    start_date = models.DateField()
    end_date = models.DateField()
    alert_threshold = models.IntegerField(default=80, help_text="Alert when % of budget is reached")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - ₱{self.amount}"
    
    def get_spent_amount(self):
        """Calculate total spent for this budget"""
        expenses = Expense.objects.filter(
            user=self.user,
            date__gte=self.start_date,
            date__lte=self.end_date
        )
        if self.category:
            expenses = expenses.filter(category=self.category)
        return expenses.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    
    def get_remaining_amount(self):
        """Calculate remaining budget"""
        return self.amount - self.get_spent_amount()
    
    def get_percentage_used(self):
        """Calculate percentage of budget used"""
        spent = self.get_spent_amount()
        if self.amount > 0:
            return (spent / self.amount) * 100
        return 0
    
    def is_over_budget(self):
        """Check if budget is exceeded"""
        return self.get_spent_amount() > self.amount
    
    def is_alert_threshold_reached(self):
        """Check if alert threshold is reached"""
        return self.get_percentage_used() >= self.alert_threshold


class Alert(models.Model):
    """Budget alerts and notifications"""
    ALERT_TYPES = [
        ('threshold', 'Threshold Reached'),
        ('exceeded', 'Budget Exceeded'),
        ('reminder', 'Budget Reminder'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='alerts')
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='alerts', null=True, blank=True)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        budget = models.ForeignKey('Budget', on_delete=models.SET_NULL, null=True, blank=True)
        return f"{self.get_alert_type_display()} - {self.user.username}"