from django.contrib import admin
from .models import *


@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'location', 'phone', 'created_at']


@admin.register(Cow)
class CowAdmin(admin.ModelAdmin):
    list_display = ['tag_number', 'name', 'breed', 'status', 'farm', 'is_active']
    list_filter = ['breed', 'status', 'farm', 'is_active']
    search_fields = ['tag_number', 'name']


@admin.register(MilkProduction)
class MilkProductionAdmin(admin.ModelAdmin):
    list_display = ['cow', 'date', 'morning_litres', 'evening_litres']
    list_filter = ['date']


@admin.register(Insemination)
class InseminationAdmin(admin.ModelAdmin):
    list_display = ['cow', 'insemination_date', 'method', 'is_successful']


@admin.register(HealthRecord)
class HealthRecordAdmin(admin.ModelAdmin):
    list_display = ['cow', 'date', 'record_type', 'medicine', 'cost']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['farm', 'date', 'category', 'description', 'amount']
    list_filter = ['category']


@admin.register(SMSReminder)
class SMSReminderAdmin(admin.ModelAdmin):
    list_display = ['farm', 'cow', 'reminder_type', 'scheduled_date', 'status']
    list_filter = ['status', 'reminder_type']


admin.site.register(CalvingRecord)
admin.site.register(MilkSale)
admin.site.register(FeedRecord)
admin.site.register(WeightRecord)
