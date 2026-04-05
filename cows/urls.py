from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('farm/setup/', views.farm_setup, name='farm_setup'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # Cows
    path('cows/', views.cow_list, name='cow_list'),
    path('cows/add/', views.cow_add, name='cow_add'),
    path('cows/<int:pk>/', views.cow_detail, name='cow_detail'),
    path('cows/<int:pk>/edit/', views.cow_edit, name='cow_edit'),
    path('cows/<int:pk>/retire/', views.cow_retire, name='cow_retire'),

    # Insemination
    path('cows/<int:cow_pk>/inseminate/', views.insemination_add, name='insemination_add'),

    # Calving
    path('cows/<int:cow_pk>/calving/', views.calving_add, name='calving_add'),

    # Health
    path('cows/<int:cow_pk>/health/', views.health_add, name='health_add'),

    # Weight
    path('cows/<int:cow_pk>/weight/', views.weight_add, name='weight_add'),

    # Milk
    path('milk/', views.milk_entry, name='milk_entry'),
    path('milk/bulk/', views.milk_bulk_entry, name='milk_bulk_entry'),
    path('milk/report/', views.milk_production_report, name='milk_production_report'),
    path('milk/sale/', views.milk_sale_add, name='milk_sale_add'),

    # Expenses
    path('expenses/', views.expense_list, name='expense_list'),
    path('expenses/add/', views.expense_add, name='expense_add'),

    # Reminders
    path('reminders/', views.reminders_list, name='reminders_list'),
    path('reminders/add/', views.reminder_add, name='reminder_add'),
    path('reminders/<int:pk>/send/', views.send_reminder, name='send_reminder'),

    # Reports
    path('reports/financial/', views.financial_report, name='financial_report'),

    # API
    path('api/stats/', views.api_stats, name='api_stats'),
    path('cows/expected-dates/', views.expected_dates_list, name='expected_dates_list'),
    path('cows/<int:cow_pk>/set-expected-dates/', views.set_expected_dates, name='set_expected_dates'),
]
