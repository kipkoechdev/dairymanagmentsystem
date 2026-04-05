from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.db.models import Sum, F, Q
from django.http import JsonResponse
from datetime import date, timedelta
from decimal import Decimal
import json

from .models import *
from .forms import *
from .sms_utils import send_sms_reminder


def get_farm_or_redirect(request):
    """Auto-creates a default farm if none exists. NEVER redirects — always returns (farm, None)."""
    try:
        return request.user.farm, None
    except Farm.DoesNotExist:
        farm = Farm.objects.create(
            owner=request.user,
            name=f"{request.user.username.title()}'s Farm",
            phone='',
        )
        return farm, None


def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'home.html')


def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            # Auto-create farm immediately on registration
            Farm.objects.get_or_create(
                owner=user,
                defaults={'name': f"{user.username.title()}'s Farm", 'phone': ''}
            )
            messages.success(request, 'Welcome! Your account is ready. Start by adding your cows.')
            return redirect('dashboard')
    else:
        form = UserRegistrationForm()
    return render(request, 'registration/register.html', {'form': form})


@login_required
def farm_setup(request):
    """Optional farm settings page — update name, phone, etc. Never a gate."""
    farm, _ = get_farm_or_redirect(request)
    if request.method == 'POST':
        form = FarmSetupForm(request.POST, request.FILES, instance=farm)
        if form.is_valid():
            form.save()
            messages.success(request, f'Farm details updated for {farm.name}.')
            return redirect('dashboard')
    else:
        form = FarmSetupForm(instance=farm)
    return render(request, 'cows/farm_setup.html', {'form': form, 'farm': farm})


@login_required
def dashboard(request):
    farm, _ = get_farm_or_redirect(request)
    today = date.today()
    cows = Cow.objects.filter(farm=farm, is_active=True)
    total_cows = cows.count()
    lactating = cows.filter(status='lactating').count()
    pregnant = cows.filter(status='pregnant').count()
    sick = cows.filter(status='sick').count()
    month_start = today.replace(day=1)
    milk_this_month = MilkProduction.objects.filter(
        cow__farm=farm, date__gte=month_start
    ).aggregate(total=Sum(F('morning_litres') + F('midday_litres') + F('evening_litres')))['total'] or Decimal('0')
    milk_today = MilkProduction.objects.filter(
        cow__farm=farm, date=today
    ).aggregate(total=Sum(F('morning_litres') + F('midday_litres') + F('evening_litres')))['total'] or Decimal('0')
    revenue_this_month = MilkSale.objects.filter(
        farm=farm, date__gte=month_start
    ).aggregate(total=Sum(F('litres_sold') * F('price_per_litre')))['total'] or Decimal('0')
    expenses_this_month = Expense.objects.filter(
        farm=farm, date__gte=month_start
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    profit = revenue_this_month - expenses_this_month
    upcoming_events = []
    for cow in cows:
        for event_type, days, event_date in cow.days_to_next_event():
            if 0 <= days <= 30:
                upcoming_events.append({'cow': cow, 'event_type': event_type, 'days': days, 'date': event_date, 'urgent': days <= 3})
    upcoming_events.sort(key=lambda x: x['days'])
    health_alerts = HealthRecord.objects.filter(
        cow__farm=farm, next_appointment__gte=today, next_appointment__lte=today + timedelta(days=7)
    ).select_related('cow')
    recent_milk = MilkProduction.objects.filter(cow__farm=farm).select_related('cow').order_by('-date', '-created_at')[:10]
    chart_labels, chart_data = [], []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        chart_labels.append(day.strftime('%a %d'))
        daily = MilkProduction.objects.filter(cow__farm=farm, date=day).aggregate(
            total=Sum(F('morning_litres') + F('midday_litres') + F('evening_litres')))['total'] or 0
        chart_data.append(float(daily))
    context = {
        'farm': farm, 'total_cows': total_cows, 'lactating': lactating, 'pregnant': pregnant, 'sick': sick,
        'milk_today': milk_today, 'milk_this_month': milk_this_month, 'revenue_this_month': revenue_this_month,
        'expenses_this_month': expenses_this_month, 'profit': profit, 'upcoming_events': upcoming_events[:10],
        'health_alerts': health_alerts, 'recent_milk': recent_milk,
        'chart_labels': json.dumps(chart_labels), 'chart_data': json.dumps(chart_data),
    }
    return render(request, 'cows/dashboard.html', context)


@login_required
def cow_list(request):
    farm, _ = get_farm_or_redirect(request)
    status_filter = request.GET.get('status', '')
    breed_filter = request.GET.get('breed', '')
    search = request.GET.get('search', '')
    cows = Cow.objects.filter(farm=farm, is_active=True)
    if status_filter:
        cows = cows.filter(status=status_filter)
    if breed_filter:
        cows = cows.filter(breed=breed_filter)
    if search:
        cows = cows.filter(Q(name__icontains=search) | Q(tag_number__icontains=search))
    context = {
        'farm': farm, 'cows': cows, 'status_filter': status_filter,
        'breed_filter': breed_filter, 'search': search,
        'status_choices': Cow.STATUS_CHOICES, 'breed_choices': Cow.BREED_CHOICES,
    }
    return render(request, 'cows/cow_list.html', context)


@login_required
def cow_add(request):
    farm, _ = get_farm_or_redirect(request)
    if request.method == 'POST':
        form = CowForm(request.POST, request.FILES, farm=farm)
        if form.is_valid():
            cow = form.save(commit=False)
            cow.farm = farm
            cow.save()
            _auto_create_reminder(farm, cow, 'insemination')
            messages.success(request, f'Cow {cow.name} ({cow.tag_number}) added successfully!')
            return redirect('cow_detail', pk=cow.pk)
    else:
        form = CowForm(farm=farm)
    return render(request, 'cows/cow_form.html', {'form': form, 'farm': farm, 'title': 'Add New Cow'})


@login_required
def cow_edit(request, pk):
    farm, _ = get_farm_or_redirect(request)
    cow = get_object_or_404(Cow, pk=pk, farm=farm)
    if request.method == 'POST':
        form = CowForm(request.POST, request.FILES, instance=cow, farm=farm)
        if form.is_valid():
            form.save()
            messages.success(request, f'Cow {cow.name} updated!')
            return redirect('cow_detail', pk=cow.pk)
    else:
        form = CowForm(instance=cow, farm=farm)
    return render(request, 'cows/cow_form.html', {'form': form, 'farm': farm, 'cow': cow, 'title': f'Edit {cow.name}'})


@login_required
def cow_detail(request, pk):
    farm, _ = get_farm_or_redirect(request)
    cow = get_object_or_404(Cow, pk=pk, farm=farm)
    last_30 = date.today() - timedelta(days=30)
    milk_records = cow.milk_productions.filter(date__gte=last_30).order_by('-date')
    chart_labels, chart_data = [], []
    for i in range(29, -1, -1):
        day = date.today() - timedelta(days=i)
        record = cow.milk_productions.filter(date=day).first()
        chart_labels.append(day.strftime('%d %b'))
        chart_data.append(float(record.total_litres) if record else 0)
    context = {
        'farm': farm, 'cow': cow, 'milk_records': milk_records,
        'inseminations': cow.inseminations.order_by('-insemination_date'),
        'health_records': cow.health_records.order_by('-date'),
        'calvings': cow.calvings.order_by('-calving_date'),
        'weight_records': cow.weight_records.order_by('-date')[:10],
        'chart_labels': json.dumps(chart_labels), 'chart_data': json.dumps(chart_data),
        'upcoming_events': cow.days_to_next_event(),
    }
    return render(request, 'cows/cow_detail.html', context)


@login_required
def cow_retire(request, pk):
    farm, _ = get_farm_or_redirect(request)
    cow = get_object_or_404(Cow, pk=pk, farm=farm)
    if request.method == 'POST':
        action = request.POST.get('action', 'sold')
        cow.status = action
        cow.is_active = False
        cow.save()
        messages.success(request, f'{cow.name} has been marked as {action}.')
        return redirect('cow_list')
    return render(request, 'cows/cow_retire.html', {'cow': cow, 'farm': farm})


@login_required
def milk_entry(request):
    farm, _ = get_farm_or_redirect(request)
    today = date.today()
    if request.method == 'POST':
        form = MilkProductionForm(request.POST, farm=farm)
        if form.is_valid():
            record = form.save(commit=False)
            record.recorded_by = request.user
            record.save()
            messages.success(request, f'Milk recorded: {record.total_litres}L for {record.cow.name}')
            return redirect('milk_entry')
    else:
        form = MilkProductionForm(farm=farm, initial={'date': today})
    todays_milk = MilkProduction.objects.filter(cow__farm=farm, date=today).select_related('cow')
    total_today = todays_milk.aggregate(
        total=Sum(F('morning_litres') + F('midday_litres') + F('evening_litres')))['total'] or 0
    return render(request, 'cows/milk_entry.html', {'farm': farm, 'form': form, 'todays_milk': todays_milk, 'total_today': total_today})


@login_required
def milk_bulk_entry(request):
    farm, _ = get_farm_or_redirect(request)
    today = date.today()
    cows = Cow.objects.filter(farm=farm, is_active=True, status__in=['lactating', 'pregnant'])
    if request.method == 'POST':
        entry_date = request.POST.get('date', str(today))
        saved = 0
        for cow in cows:
            morning = request.POST.get(f'morning_{cow.id}', '0') or '0'
            midday = request.POST.get(f'midday_{cow.id}', '0') or '0'
            evening = request.POST.get(f'evening_{cow.id}', '0') or '0'
            if float(morning) + float(midday) + float(evening) > 0:
                MilkProduction.objects.update_or_create(
                    cow=cow, date=entry_date,
                    defaults={'morning_litres': morning, 'midday_litres': midday,
                              'evening_litres': evening, 'recorded_by': request.user}
                )
                saved += 1
        messages.success(request, f'Bulk milk entry saved for {saved} cows.')
        return redirect('milk_production_report')
    existing = {m.cow_id: m for m in MilkProduction.objects.filter(cow__farm=farm, date=today)}
    return render(request, 'cows/milk_bulk_entry.html', {'farm': farm, 'cows': cows, 'today': today, 'existing': existing})


@login_required
def milk_production_report(request):
    farm, _ = get_farm_or_redirect(request)
    today = date.today()
    month_start = today.replace(day=1)
    cow_summary = Cow.objects.filter(farm=farm, is_active=True).annotate(
        month_total=Sum(
            F('milk_productions__morning_litres') + F('milk_productions__midday_litres') + F('milk_productions__evening_litres'),
            filter=models.Q(milk_productions__date__gte=month_start)
        )
    ).filter(month_total__isnull=False).order_by('-month_total')
    sales = MilkSale.objects.filter(farm=farm, date__gte=month_start)
    total_sold = sales.aggregate(total=Sum('litres_sold'))['total'] or 0
    total_revenue = sales.aggregate(total=Sum(F('litres_sold') * F('price_per_litre')))['total'] or 0
    return render(request, 'cows/milk_report.html', {
        'farm': farm, 'cow_summary': cow_summary, 'sales': sales,
        'total_sold': total_sold, 'total_revenue': total_revenue, 'month_start': month_start,
    })


@login_required
def insemination_add(request, cow_pk):
    farm, _ = get_farm_or_redirect(request)
    cow = get_object_or_404(Cow, pk=cow_pk, farm=farm)
    if request.method == 'POST':
        form = InseminationForm(request.POST)
        if form.is_valid():
            insem = form.save(commit=False)
            insem.cow = cow
            insem.save()
            if insem.is_successful:
                cow.status = 'pregnant'
                cow.save()
                delivery_date = insem.expected_delivery
                SMSReminder.objects.create(
                    farm=farm, cow=cow, reminder_type='delivery',
                    message=f"🐄 REMINDER: {cow.name} ({cow.tag_number}) is expected to calve around {delivery_date.strftime('%d %b %Y')}.",
                    phone_number=farm.phone, scheduled_date=delivery_date - timedelta(days=7)
                )
            messages.success(request, 'Insemination record added.')
            return redirect('cow_detail', pk=cow.pk)
    else:
        form = InseminationForm(initial={'insemination_date': date.today()})
    return render(request, 'cows/insemination_form.html', {'form': form, 'cow': cow, 'farm': farm})


@login_required
def health_add(request, cow_pk):
    farm, _ = get_farm_or_redirect(request)
    cow = get_object_or_404(Cow, pk=cow_pk, farm=farm)
    if request.method == 'POST':
        form = HealthRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.cow = cow
            record.save()
            if not record.is_recovered:
                cow.status = 'sick'
                cow.save()
            if record.next_appointment:
                SMSReminder.objects.create(
                    farm=farm, cow=cow, reminder_type='health_check',
                    message=f"🏥 REMINDER: {cow.name}'s vet appointment is on {record.next_appointment.strftime('%d %b %Y')}.",
                    phone_number=farm.phone, scheduled_date=record.next_appointment - timedelta(days=1)
                )
            messages.success(request, 'Health record added.')
            return redirect('cow_detail', pk=cow.pk)
    else:
        form = HealthRecordForm(initial={'date': date.today()})
    return render(request, 'cows/health_form.html', {'form': form, 'cow': cow, 'farm': farm})


@login_required
def expense_list(request):
    farm, _ = get_farm_or_redirect(request)
    expenses = Expense.objects.filter(farm=farm).order_by('-date')
    category = request.GET.get('category', '')
    if category:
        expenses = expenses.filter(category=category)
    today = date.today()
    month_start = today.replace(day=1)
    category_totals = Expense.objects.filter(farm=farm, date__gte=month_start).values('category').annotate(total=Sum('amount')).order_by('-total')
    total_expenses = Expense.objects.filter(farm=farm, date__gte=month_start).aggregate(Sum('amount'))['amount__sum'] or 0
    return render(request, 'cows/expense_list.html', {
        'farm': farm, 'expenses': expenses[:50], 'category_totals': category_totals,
        'total_expenses': total_expenses, 'category_choices': Expense.CATEGORY_CHOICES, 'category_filter': category,
    })


@login_required
def expense_add(request):
    farm, _ = get_farm_or_redirect(request)
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.farm = farm
            expense.save()
            messages.success(request, f'Expense of KES {expense.amount} recorded.')
            return redirect('expense_list')
    else:
        form = ExpenseForm(initial={'date': date.today()})
    return render(request, 'cows/expense_form.html', {'form': form, 'farm': farm})


@login_required
def reminders_list(request):
    farm, _ = get_farm_or_redirect(request)
    reminders = SMSReminder.objects.filter(farm=farm).select_related('cow')
    today = date.today()
    for cow in Cow.objects.filter(farm=farm, is_active=True):
        for event_type, days, event_date in cow.days_to_next_event():
            if 0 <= days <= 14:
                if not SMSReminder.objects.filter(farm=farm, cow=cow, reminder_type=event_type.lower(), scheduled_date=event_date - timedelta(days=2)).exists():
                    SMSReminder.objects.create(
                        farm=farm, cow=cow, reminder_type=event_type.lower(),
                        message=_build_reminder_message(cow, event_type, event_date),
                        phone_number=farm.phone, scheduled_date=event_date - timedelta(days=2)
                    )
    return render(request, 'cows/reminders.html', {'farm': farm, 'reminders': reminders, 'pending': reminders.filter(status='pending').count()})


@login_required
def send_reminder(request, pk):
    farm, _ = get_farm_or_redirect(request)
    reminder = get_object_or_404(SMSReminder, pk=pk, farm=farm)
    success, msg = send_sms_reminder(reminder)
    if success:
        messages.success(request, f'SMS sent to {reminder.phone_number}')
    else:
        messages.error(request, f'SMS failed: {msg}')
    return redirect('reminders_list')


@login_required
def reminder_add(request):
    farm, _ = get_farm_or_redirect(request)
    if request.method == 'POST':
        form = SMSReminderForm(request.POST, farm=farm)
        if form.is_valid():
            reminder = form.save(commit=False)
            reminder.farm = farm
            reminder.save()
            messages.success(request, 'Reminder created.')
            return redirect('reminders_list')
    else:
        form = SMSReminderForm(farm=farm)
    return render(request, 'cows/reminder_form.html', {'form': form, 'farm': farm})


@login_required
def financial_report(request):
    farm, _ = get_farm_or_redirect(request)
    today = date.today()
    monthly_data = []
    for i in range(5, -1, -1):
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        month_start = date(year, month, 1)
        month_end = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year + 1, 1, 1) - timedelta(days=1)
        revenue = MilkSale.objects.filter(farm=farm, date__range=[month_start, month_end]).aggregate(total=Sum(F('litres_sold') * F('price_per_litre')))['total'] or 0
        expenses = Expense.objects.filter(farm=farm, date__range=[month_start, month_end]).aggregate(total=Sum('amount'))['total'] or 0
        monthly_data.append({'month': month_start.strftime('%b %Y'), 'revenue': float(revenue), 'expenses': float(expenses), 'profit': float(revenue - expenses)})
    return render(request, 'cows/financial_report.html', {
        'farm': farm, 'monthly_data': monthly_data,
        'months_json': json.dumps([d['month'] for d in monthly_data]),
        'revenue_json': json.dumps([d['revenue'] for d in monthly_data]),
        'expenses_json': json.dumps([d['expenses'] for d in monthly_data]),
        'profit_json': json.dumps([d['profit'] for d in monthly_data]),
    })


@login_required
def calving_add(request, cow_pk):
    farm, _ = get_farm_or_redirect(request)
    cow = get_object_or_404(Cow, pk=cow_pk, farm=farm)
    if request.method == 'POST':
        form = CalvingRecordForm(request.POST)
        if form.is_valid():
            calving = form.save(commit=False)
            calving.cow = cow
            calving.save()
            cow.status = 'lactating'
            cow.save()
            messages.success(request, 'Calving record added!')
            return redirect('cow_detail', pk=cow.pk)
    else:
        form = CalvingRecordForm(initial={'calving_date': date.today()})
    return render(request, 'cows/calving_form.html', {'form': form, 'cow': cow, 'farm': farm})


@login_required
def weight_add(request, cow_pk):
    farm, _ = get_farm_or_redirect(request)
    cow = get_object_or_404(Cow, pk=cow_pk, farm=farm)
    if request.method == 'POST':
        form = WeightRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.cow = cow
            record.save()
            cow.weight_kg = record.weight_kg
            cow.save()
            messages.success(request, 'Weight recorded.')
            return redirect('cow_detail', pk=cow.pk)
    else:
        form = WeightRecordForm(initial={'date': date.today()})
    return render(request, 'cows/weight_form.html', {'form': form, 'cow': cow, 'farm': farm})


@login_required
def milk_sale_add(request):
    farm, _ = get_farm_or_redirect(request)
    if request.method == 'POST':
        form = MilkSaleForm(request.POST)
        if form.is_valid():
            sale = form.save(commit=False)
            sale.farm = farm
            sale.save()
            messages.success(request, f'Milk sale recorded: KES {sale.total_amount}')
            return redirect('milk_production_report')
    else:
        form = MilkSaleForm(initial={'date': date.today()})
    return render(request, 'cows/milk_sale_form.html', {'form': form, 'farm': farm})


@login_required
def api_stats(request):
    farm, _ = get_farm_or_redirect(request)
    today = date.today()
    milk_today = MilkProduction.objects.filter(cow__farm=farm, date=today).aggregate(
        total=Sum(F('morning_litres') + F('midday_litres') + F('evening_litres')))['total'] or 0
    return JsonResponse({'milk_today': float(milk_today)})


def _build_reminder_message(cow, event_type, event_date):
    if event_type in ('Insemination', 'insemination'):
        return f"🐄 DAIRY ALERT: {cow.name} ({cow.tag_number}) is due for insemination on {event_date.strftime('%d %b %Y')}."
    elif event_type in ('Delivery', 'delivery'):
        return f"🍼 DAIRY ALERT: {cow.name} ({cow.tag_number}) is expected to calve on {event_date.strftime('%d %b %Y')}."
    elif event_type in ('health_check',):
        return f"🏥 DAIRY ALERT: {cow.name} ({cow.tag_number}) has a vet appointment on {event_date.strftime('%d %b %Y')}."
    return f"📅 DAIRY REMINDER: Check {cow.name} ({cow.tag_number}) on {event_date.strftime('%d %b %Y')}."


def _auto_create_reminder(farm, cow, reminder_type):
    next_date = cow.next_insemination_date()
    if next_date:
        SMSReminder.objects.get_or_create(
            farm=farm, cow=cow, reminder_type=reminder_type, scheduled_date=next_date,
            defaults={'message': _build_reminder_message(cow, 'Insemination', next_date), 'phone_number': farm.phone}
        )


def _schedule_reminders_for_date(farm, cow, reminder_type, event_date, lead_days_list=(7, 3, 1)):
    today = date.today()
    scheduled_dates = [event_date - timedelta(days=d) for d in lead_days_list] + [event_date]
    for scheduled in scheduled_dates:
        if scheduled >= today:
            SMSReminder.objects.get_or_create(
                farm=farm,
                cow=cow,
                reminder_type=reminder_type,
                scheduled_date=scheduled,
                defaults={
                    'message': _build_reminder_message(cow, reminder_type, event_date),
                    'phone_number': farm.phone,
                    'status': 'pending',
                }
            )


# ─────────────────────────────────────────────
#  EXPECTED DATES VIEWS
# ─────────────────────────────────────────────

@login_required
def expected_dates_list(request):
    farm, _ = get_farm_or_redirect(request)
    today = date.today()
    cows = Cow.objects.filter(farm=farm, is_active=True).order_by('name')
    cow_data = []
    for cow in cows:
        cow_data.append({
            'cow': cow,
            'expected_insemination': cow.expected_insemination_date,
            'expected_delivery': cow.expected_delivery_date,
            'insemination_days': (cow.expected_insemination_date - today).days if cow.expected_insemination_date else None,
            'delivery_days': (cow.expected_delivery_date - today).days if cow.expected_delivery_date else None,
        })
    overdue_inseminations = [d for d in cow_data if d['insemination_days'] is not None and d['insemination_days'] <= 0]
    overdue_deliveries = [d for d in cow_data if d['delivery_days'] is not None and d['delivery_days'] <= 0]
    return render(request, 'cows/expected_dates_list.html', {
        'farm': farm, 'cow_data': cow_data, 'today': today,
        'overdue_inseminations': overdue_inseminations,
        'overdue_deliveries': overdue_deliveries,
    })


@login_required
def set_expected_dates(request, cow_pk):
    farm, _ = get_farm_or_redirect(request)
    cow = get_object_or_404(Cow, pk=cow_pk, farm=farm)
    if request.method == 'POST':
        form = ExpectedDatesForm(request.POST, instance=cow)
        if form.is_valid():
            form.save()
            insem_date = cow.expected_insemination_date
            deliv_date = cow.expected_delivery_date
            if insem_date:
                _schedule_reminders_for_date(farm, cow, 'insemination', insem_date, lead_days_list=(7, 3, 1))
            if deliv_date:
                cow.status = 'pregnant'
                cow.save(update_fields=['status'])
                _schedule_reminders_for_date(farm, cow, 'delivery', deliv_date, lead_days_list=(14, 7, 3, 1))
            messages.success(request, f'Expected dates updated for {cow.name}. SMS reminders have been scheduled.')
            return redirect('expected_dates_list')
    else:
        form = ExpectedDatesForm(instance=cow)
    return render(request, 'cows/set_expected_dates.html', {'farm': farm, 'cow': cow, 'form': form})
