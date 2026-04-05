from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta, date
import uuid


class Farm(models.Model):
    owner = models.OneToOneField(User, on_delete=models.CASCADE, related_name='farm')
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=300)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    established_date = models.DateField(null=True, blank=True)
    logo = models.ImageField(upload_to='farm_logos/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def total_cows(self):
        return self.cows.filter(is_active=True).count()

    def total_milk_today(self):
        today = date.today()
        return MilkProduction.objects.filter(
            cow__farm=self, date=today
        ).aggregate(models.Sum('morning_litres') + models.Sum('evening_litres'))['total'] or 0


class Cow(models.Model):
    BREED_CHOICES = [
        ('friesian', 'Friesian'),
        ('jersey', 'Jersey'),
        ('ayrshire', 'Ayrshire'),
        ('guernsey', 'Guernsey'),
        ('holstein', 'Holstein'),
        ('crossbreed', 'Crossbreed'),
        ('boran', 'Boran'),
        ('zebu', 'Zebu'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('lactating', 'Lactating'),
        ('dry', 'Dry'),
        ('pregnant', 'Pregnant'),
        ('heifer', 'Heifer'),
        ('bull', 'Bull'),
        ('sick', 'Sick'),
        ('sold', 'Sold'),
        ('deceased', 'Deceased'),
    ]
    COLOR_CHOICES = [
        ('black_white', 'Black & White'),
        ('brown', 'Brown'),
        ('fawn', 'Fawn'),
        ('red', 'Red'),
        ('white', 'White'),
        ('mixed', 'Mixed'),
    ]

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='cows')
    tag_number = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    breed = models.CharField(max_length=50, choices=BREED_CHOICES)
    color = models.CharField(max_length=20, choices=COLOR_CHOICES, default='black_white')
    date_of_birth = models.DateField()
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='heifer')
    mother = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='calves')
    purchase_date = models.DateField(null=True, blank=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    photo = models.ImageField(upload_to='cow_photos/', null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['tag_number']

    def __str__(self):
        return f"{self.tag_number} - {self.name}"

    def age(self):
        today = date.today()
        delta = today - self.date_of_birth
        years = delta.days // 365
        months = (delta.days % 365) // 30
        if years > 0:
            return f"{years}y {months}m"
        return f"{months} months"

    def age_days(self):
        return (date.today() - self.date_of_birth).days

    def next_insemination_date(self):
        last_insem = self.inseminations.order_by('-insemination_date').first()
        if last_insem and not last_insem.is_successful:
            return last_insem.insemination_date + timedelta(days=21)
        if not self.inseminations.exists():
            # First time — recommend when cow is 15 months old (450 days)
            return self.date_of_birth + timedelta(days=450)
        return None

    def expected_delivery_date(self):
        last_successful = self.inseminations.filter(is_successful=True).order_by('-insemination_date').first()
        if last_successful:
            return last_successful.insemination_date + timedelta(days=283)
        return None

    def days_to_next_event(self):
        next_insem = self.next_insemination_date()
        expected_delivery = self.expected_delivery_date()
        today = date.today()
        events = []
        if next_insem and next_insem >= today:
            events.append(('Insemination', (next_insem - today).days, next_insem))
        if expected_delivery and expected_delivery >= today:
            events.append(('Delivery', (expected_delivery - today).days, expected_delivery))
        return sorted(events, key=lambda x: x[1])

    def total_milk_this_month(self):
        today = date.today()
        return self.milk_productions.filter(
            date__year=today.year, date__month=today.month
        ).aggregate(
            total=models.Sum(models.F('morning_litres') + models.F('evening_litres'))
        )['total'] or 0

    def latest_health_check(self):
        return self.health_records.order_by('-date').first()


class Insemination(models.Model):
    METHOD_CHOICES = [
        ('ai', 'Artificial Insemination'),
        ('natural', 'Natural Mating'),
        ('embryo', 'Embryo Transfer'),
    ]

    cow = models.ForeignKey(Cow, on_delete=models.CASCADE, related_name='inseminations')
    insemination_date = models.DateField()
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='ai')
    bull_breed = models.CharField(max_length=100, blank=True)
    semen_batch = models.CharField(max_length=100, blank=True)
    technician = models.CharField(max_length=150, blank=True)
    cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_successful = models.BooleanField(default=False)
    confirmed_pregnancy_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def expected_delivery(self):
        return self.insemination_date + timedelta(days=283)

    @property
    def days_to_delivery(self):
        return (self.expected_delivery - date.today()).days

    def __str__(self):
        return f"{self.cow} - {self.insemination_date}"


class CalvingRecord(models.Model):
    CALVING_EASE_CHOICES = [
        ('easy', 'Easy'),
        ('assisted', 'Assisted'),
        ('difficult', 'Difficult'),
        ('caesarean', 'Caesarean'),
    ]
    CALF_GENDER = [('male', 'Male'), ('female', 'Female')]

    cow = models.ForeignKey(Cow, on_delete=models.CASCADE, related_name='calvings')
    insemination = models.ForeignKey(Insemination, on_delete=models.SET_NULL, null=True, blank=True)
    calving_date = models.DateField()
    calf_tag = models.CharField(max_length=50, blank=True)
    calf_name = models.CharField(max_length=100, blank=True)
    calf_gender = models.CharField(max_length=10, choices=CALF_GENDER)
    calf_weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    calving_ease = models.CharField(max_length=20, choices=CALVING_EASE_CHOICES, default='easy')
    calf_survived = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.cow.name} calved on {self.calving_date}"


class MilkProduction(models.Model):
    cow = models.ForeignKey(Cow, on_delete=models.CASCADE, related_name='milk_productions')
    date = models.DateField(default=date.today)
    morning_litres = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    midday_litres = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    evening_litres = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    milk_quality = models.CharField(max_length=20, choices=[
        ('good', 'Good'), ('fair', 'Fair'), ('poor', 'Poor'), ('discarded', 'Discarded')
    ], default='good')
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['cow', 'date']
        ordering = ['-date']

    @property
    def total_litres(self):
        return self.morning_litres + self.midday_litres + self.evening_litres

    def __str__(self):
        return f"{self.cow.name} - {self.date} - {self.total_litres}L"


class MilkSale(models.Model):
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='milk_sales')
    date = models.DateField(default=date.today)
    litres_sold = models.DecimalField(max_digits=8, decimal_places=2)
    price_per_litre = models.DecimalField(max_digits=6, decimal_places=2)
    buyer_name = models.CharField(max_length=200, blank=True)
    payment_received = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_amount(self):
        return self.litres_sold * self.price_per_litre

    class Meta:
        ordering = ['-date']


class HealthRecord(models.Model):
    RECORD_TYPE = [
        ('vaccination', 'Vaccination'),
        ('treatment', 'Treatment'),
        ('checkup', 'Routine Checkup'),
        ('deworming', 'Deworming'),
        ('surgery', 'Surgery'),
        ('other', 'Other'),
    ]

    cow = models.ForeignKey(Cow, on_delete=models.CASCADE, related_name='health_records')
    date = models.DateField(default=date.today)
    record_type = models.CharField(max_length=20, choices=RECORD_TYPE)
    diagnosis = models.CharField(max_length=300, blank=True)
    treatment = models.TextField(blank=True)
    medicine = models.CharField(max_length=200, blank=True)
    dosage = models.CharField(max_length=100, blank=True)
    vet_name = models.CharField(max_length=150, blank=True)
    cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    next_appointment = models.DateField(null=True, blank=True)
    is_recovered = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.cow.name} - {self.record_type} - {self.date}"


class FeedRecord(models.Model):
    FEED_TYPE = [
        ('hay', 'Hay'),
        ('silage', 'Silage'),
        ('concentrates', 'Concentrates'),
        ('mineral_lick', 'Mineral Lick'),
        ('pasture', 'Pasture'),
        ('napier', 'Napier Grass'),
        ('dairy_meal', 'Dairy Meal'),
        ('other', 'Other'),
    ]

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='feed_records')
    cow = models.ForeignKey(Cow, on_delete=models.CASCADE, related_name='feed_records', null=True, blank=True)
    date = models.DateField(default=date.today)
    feed_type = models.CharField(max_length=30, choices=FEED_TYPE)
    quantity_kg = models.DecimalField(max_digits=8, decimal_places=2)
    cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    supplier = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']


class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('feed', 'Feed & Fodder'),
        ('veterinary', 'Veterinary'),
        ('medicine', 'Medicine'),
        ('labor', 'Labor'),
        ('equipment', 'Equipment'),
        ('utilities', 'Utilities'),
        ('transport', 'Transport'),
        ('insemination', 'Insemination'),
        ('other', 'Other'),
    ]

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='expenses')
    date = models.DateField(default=date.today)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    description = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_to = models.CharField(max_length=200, blank=True)
    receipt_number = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.category} - KES {self.amount} on {self.date}"


class SMSReminder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    TYPE_CHOICES = [
        ('insemination', 'Insemination Due'),
        ('delivery', 'Expected Delivery'),
        ('vaccination', 'Vaccination Due'),
        ('health_check', 'Health Check Due'),
        ('dry_off', 'Dry Off Due'),
        ('custom', 'Custom'),
    ]

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='sms_reminders')
    cow = models.ForeignKey(Cow, on_delete=models.CASCADE, related_name='sms_reminders', null=True, blank=True)
    reminder_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    message = models.TextField()
    phone_number = models.CharField(max_length=20)
    scheduled_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scheduled_date']

    def __str__(self):
        return f"{self.reminder_type} - {self.scheduled_date} - {self.status}"


class WeightRecord(models.Model):
    cow = models.ForeignKey(Cow, on_delete=models.CASCADE, related_name='weight_records')
    date = models.DateField(default=date.today)
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2)
    body_condition_score = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True,
                                               help_text="Score 1-5")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']
expected_insemination_date = models.DateField(
    null=True, blank=True,
    help_text="Expected date for next insemination"
)
expected_delivery_date = models.DateField(
    null=True, blank=True,
    help_text="Expected calving / delivery date"
)

