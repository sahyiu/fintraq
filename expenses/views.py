from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from .models import Expense, Category, Budget, Alert
from .forms import ExpenseForm, CategoryForm, BudgetForm, ExpenseFilterForm, UserRegistrationForm
from django.contrib.auth import get_user_model


def register(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('expenses:dashboard')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create default categories for new user
            default_categories = [
                ('Food & Dining', 'food', '#ef4444'),
                ('Transportation', 'transport', '#3b82f6'),
                ('Utilities', 'utilities', '#f59e0b'),
                ('Entertainment', 'entertainment', '#8b5cf6'),
                ('Healthcare', 'healthcare', '#10b981'),
                ('Shopping', 'shopping', '#ec4899'),
                ('Education', 'education', '#6366f1'),
                ('Housing', 'housing', '#14b8a6'),
                ('Other', 'other', '#6b7280'),
            ]
            for name, cat_type, color in default_categories:
                Category.objects.create(
                    user=user,
                    name=name,
                    category_type=cat_type,
                    color=color
                )
            login(request, user)
            messages.success(request, 'Registration successful! Welcome to Expense Tracker.')
            return redirect('expenses:dashboard')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def dashboard(request):
    auto_deactivate_budgets(request.user)
    """Main dashboard view"""
    user = request.user
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    
    # Get current month expenses
    month_expenses = Expense.objects.filter(
        user=user,
        date__gte=start_of_month,
        date__lte=today
    )
    
    # Calculate statistics
    total_expenses = month_expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    expense_count = month_expenses.count()
    
    # Get expenses by category
    expenses_by_category = month_expenses.values(
        'category__name', 'category__color'
    ).annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    # Get recent expenses
    recent_expenses = Expense.objects.filter(user=user).order_by('-date', '-created_at')[:5]
    
    # Get active budgets
    active_budgets = Budget.objects.filter(
        user=user,
        is_active=True,
        start_date__lte=today,
        end_date__gte=today
    )
    
    # Calculate budget status
    budget_data = []
    for budget in active_budgets:
        spent = budget.get_spent_amount()
        percentage = budget.get_percentage_used()
        remaining = budget.get_remaining_amount()
        
        budget_data.append({
            'budget': budget,
            'spent': spent,
            'percentage': percentage,
            'remaining': remaining,
            'is_over': budget.is_over_budget(),
            'is_alert': budget.is_alert_threshold_reached()
        })
    
    # Get unread alerts
    unread_alerts = Alert.objects.filter(user=user, is_read=False).order_by('-created_at')[:5]
    
    # Get daily expenses for the last 7 days
    week_ago = today - timedelta(days=6)
    daily_expenses = []
    for i in range(7):
        day = week_ago + timedelta(days=i)
        day_total = Expense.objects.filter(
            user=user,
            date=day
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        daily_expenses.append({
            'date': day,
            'total': float(day_total)
        })
    
    context = {
        'total_expenses': total_expenses,
        'expense_count': expense_count,
        'expenses_by_category': expenses_by_category,
        'recent_expenses': recent_expenses,
        'budget_data': budget_data,
        'unread_alerts': unread_alerts,
        'daily_expenses': daily_expenses,
    }
    
    return render(request, 'expenses/dashboard.html', context)


@login_required
def expense_list(request):
    """List all expenses with filtering"""
    user = request.user
    expenses = Expense.objects.filter(user=user)
    
    # Apply filters
    filter_form = ExpenseFilterForm(user=user, data=request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('category'):
            expenses = expenses.filter(category=filter_form.cleaned_data['category'])
        if filter_form.cleaned_data.get('start_date'):
            expenses = expenses.filter(date__gte=filter_form.cleaned_data['start_date'])
        if filter_form.cleaned_data.get('end_date'):
            expenses = expenses.filter(date__lte=filter_form.cleaned_data['end_date'])
        if filter_form.cleaned_data.get('min_amount'):
            expenses = expenses.filter(amount__gte=filter_form.cleaned_data['min_amount'])
        if filter_form.cleaned_data.get('max_amount'):
            expenses = expenses.filter(amount__lte=filter_form.cleaned_data['max_amount'])
    
    total = expenses.aggregate(total=Sum('amount'))['total' or Decimal('0.00')]
    
    context = {
        'expenses': expenses,
        'filter_form': filter_form,
        'total': total,
    }
    
    return render(request, 'expenses/expense_list.html', context)
 

@login_required
def expense_create(request):
    """Create a new expense"""
    if request.method == 'POST':
        form = ExpenseForm(user=request.user, data=request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            expense.save()
            messages.success(request, 'Expense added successfully!')
            
            # Check budgets and create alerts if needed
            check_budget_alerts(request.user, expense)
            
            return redirect('expenses:expense_list')
    else:
        form = ExpenseForm(user=request.user)
    
    return render(request, 'expenses/expense_form.html', {'form': form})

@login_required
def expense_update(request, pk):
    """Update an existing expense"""
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = ExpenseForm(user=request.user, data=request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense updated successfully!')
            return redirect('expenses:expense_list')
    else:
        form = ExpenseForm(user=request.user, instance=expense)
    
    return render(request, 'expenses/expense_form.html', {'form': form, 'action': 'Update'})


@login_required
def expense_delete(request, pk):
    """Delete an expense"""
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    
    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense deleted successfully!')
        return redirect('expenses:expense_list')
    
    return render(request, 'expenses/expense_confirm_delete.html', {'expense': expense})


# Category Views
@login_required
def category_list(request):
    """List all categories"""
    ensure_other_category(request.user)
    categories = Category.objects.filter(user=request.user)
    return render(request, 'expenses/category_list.html', {'categories': categories})

@login_required
def category_create(request):
    """Create a new category"""
    ensure_other_category(request.user)
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            messages.success(request, 'Category created successfully!')
            return redirect('expenses:category_list')
    else:
        form = CategoryForm()
    return render(request, 'expenses/category_form.html', {'form': form, 'action': 'Create'})


# Budget Views
@login_required
def budget_list(request):
    auto_deactivate_budgets(request.user)
    """List all budgets"""
    budgets = Budget.objects.filter(user=request.user)
    
    budget_data = []
    for budget in budgets:
        budget_data.append({
            'budget': budget,
            'spent': budget.get_spent_amount(),
            'percentage': budget.get_percentage_used(),
            'remaining': budget.get_remaining_amount(),
            'is_over': budget.is_over_budget(),
        })
    
    return render(request, 'expenses/budget_list.html', {'budget_data': budget_data})


@login_required
def budget_create(request):
    """Create a new budget"""
    if request.method == 'POST':
        form = BudgetForm(user=request.user, data=request.POST)
        if form.is_valid():
            budget = form.save(commit=False)
            budget.user = request.user
            budget.save()
            messages.success(request, 'Budget created successfully!')
            return redirect('expenses:budget_list')
    else:
        form = BudgetForm(user=request.user)
    
    return render(request, 'expenses/budget_form.html', {'form': form, 'action': 'Create'})


@login_required
def budget_update(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == 'POST':
        form = BudgetForm(user=request.user, data=request.POST, instance=budget)
        if form.is_valid():
            form.save()
            messages.success(request, 'Budget updated successfully!')
            return redirect('expenses:budget_list')
    else:
        form = BudgetForm(user=request.user, instance=budget)
    return render(request, 'expenses/budget_form.html', {'form': form, 'action': 'Update'})


@login_required
def budget_delete(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == 'POST':
        budget.delete()
        messages.success(request, 'Budget deleted successfully!')
        return redirect('expenses:budget_list')
    return render(request, 'expenses/budget_confirm_delete.html', {'budget': budget})


# Helper function
def check_budget_alerts(user, expense):
    """Check if any budgets need alerts after adding an expense"""
    today = timezone.now().date()
    relevant_budgets = Budget.objects.filter(
        user=user,
        is_active=True,
        start_date__lte=expense.date,
        end_date__gte=expense.date
    )
    
    if expense.category:
        relevant_budgets = relevant_budgets.filter(
            Q(category=expense.category) | Q(category__isnull=True)
        )
    
    for budget in relevant_budgets:
        if budget.is_over_budget():
            Alert.objects.create(
                user=user,
                budget=budget,
                alert_type='exceeded',
                message=f'Budget "{budget.name}" has been exceeded! You have spent ₱{budget.get_spent_amount()} of ₱{budget.amount}.'
            )
        elif budget.is_alert_threshold_reached():
            # Only create alert if not already alerted
            existing_alert = Alert.objects.filter(
                user=user,
                budget=budget,
                alert_type='threshold'
            ).exists()
            if not existing_alert:
                Alert.objects.create(
                    user=user,
                    budget=budget,
                    alert_type='threshold',
                    message=f'Budget "{budget.name}" has reached {budget.alert_threshold}% threshold!'
                )

def ensure_other_category(user):
    """Ensure the 'Other' category exists for the user."""
    if not Category.objects.filter(user=user, name__iexact="Other").exists():
        Category.objects.create(
            user=user,
            name="Other",
            category_type="other",
            color="#6b7280"
        )

# Create default categories for all existing users
default_categories = [
    ('Food & Dining', 'food', '#ef4444'),
    ('Transportation', 'transport', '#3b82f6'),
    ('Utilities', 'utilities', '#f59e0b'),
    ('Entertainment', 'entertainment', '#8b5cf6'),
    ('Healthcare', 'healthcare', '#10b981'),
    ('Shopping', 'shopping', '#ec4899'),
    ('Education', 'education', '#6366f1'),
    ('Housing', 'housing', '#14b8a6'),
    ('Other', 'other', '#6b7280'),
]

User = get_user_model()
for user in User.objects.all():
    for name, cat_type, color in default_categories:
        if not Category.objects.filter(user=user, name=name).exists():
            Category.objects.create(
                user=user,
                name=name,
                category_type=cat_type,
                color=color
            )

from django.utils import timezone

def auto_deactivate_budgets(user):
    """Deactivate budgets whose end_date has passed."""
    today = timezone.now().date()
    Budget.objects.filter(user=user, is_active=True, end_date__lt=today).update(is_active=False)