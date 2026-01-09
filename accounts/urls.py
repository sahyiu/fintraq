# accounts/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from expenses import views as expense_views

app_name = 'accounts'

urlpatterns = [
    # Login - uses Django's built-in LoginView
    path('login/', auth_views.LoginView.as_view(
        template_name='accounts/login.html',
        redirect_authenticated_user=True
    ), name='login'),
    
    # Logout - properly logs out the user then redirects to login
    path('logout/', auth_views.LogoutView.as_view(next_page='accounts:login'), name='logout'),
    
    # Register - uses your custom registration view
    path('register/', expense_views.register, name='register'),

    path('password-change/', auth_views.PasswordChangeView.as_view(template_name='accounts/password_change.html'), name='password_change'),
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='accounts/password_change_done.html'), name='password_change_done'),
]