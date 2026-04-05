from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import *


from .models import Cow   


class ExpectedDatesForm(forms.ModelForm):
    expected_insemination_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Expected Insemination Date',
        help_text='Leave blank if not yet known.'
    )
    expected_delivery_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Expected Delivery / Calving Date',
        help_text='Leave blank if not yet known.'
    )

    class Meta:
        model = Cow
        fields = ['expected_insemination_date', 'expected_delivery_date']

    def clean(self):
        cleaned_data = super().clean()
        insem = cleaned_data.get('expected_insemination_date')
        deliv = cleaned_data.get('expected_delivery_date')
        today = forms.fields.datetime.date.today() if False else __import__('datetime').date.today()

        if insem and insem < today:
            self.add_error('expected_insemination_date', 'Insemination date cannot be in the past.')
        if deliv and deliv < today:
            self.add_error('expected_delivery_date', 'Delivery date cannot be in the past.')
        if insem and deliv and deliv <= insem:
            self.add_error('expected_delivery_date', 'Delivery date must be after the insemination date.')
        return cleaned_data



class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=100, required=True)
    last_name = forms.CharField(max_length=100, required=True)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']


class FarmSetupForm(forms.ModelForm):
    class Meta:
        model = Farm
        fields = ['name', 'location', 'phone', 'email', 'established_date', 'logo']
        widgets = {
            'established_date': forms.DateInput(attrs={'type': 'date'}),
        }


class CowForm(forms.ModelForm):
    class Meta:
        model = Cow
        fields = ['tag_number', 'name', 'breed', 'color', 'date_of_birth', 'weight_kg',
                  'status', 'mother', 'purchase_date', 'purchase_price', 'photo', 'notes']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, farm=None, **kwargs):
        super().__init__(*args, **kwargs)
        if farm:
            self.fields['mother'].queryset = Cow.objects.filter(farm=farm, is_active=True)


class InseminationForm(forms.ModelForm):
    class Meta:
        model = Insemination
        fields = ['insemination_date', 'method', 'bull_breed', 'semen_batch',
                  'technician', 'cost', 'is_successful', 'confirmed_pregnancy_date', 'notes']
        widgets = {
            'insemination_date': forms.DateInput(attrs={'type': 'date'}),
            'confirmed_pregnancy_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class CalvingRecordForm(forms.ModelForm):
    class Meta:
        model = CalvingRecord
        fields = ['calving_date', 'calf_tag', 'calf_name', 'calf_gender',
                  'calf_weight_kg', 'calving_ease', 'calf_survived', 'notes']
        widgets = {
            'calving_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class MilkProductionForm(forms.ModelForm):
    class Meta:
        model = MilkProduction
        fields = ['cow', 'date', 'morning_litres', 'midday_litres', 'evening_litres', 'milk_quality', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, farm=None, **kwargs):
        super().__init__(*args, **kwargs)
        if farm:
            self.fields['cow'].queryset = Cow.objects.filter(
                farm=farm, is_active=True, status__in=['lactating', 'pregnant']
            )


class MilkSaleForm(forms.ModelForm):
    class Meta:
        model = MilkSale
        fields = ['date', 'litres_sold', 'price_per_litre', 'buyer_name', 'payment_received', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class HealthRecordForm(forms.ModelForm):
    class Meta:
        model = HealthRecord
        fields = ['date', 'record_type', 'diagnosis', 'treatment', 'medicine',
                  'dosage', 'vet_name', 'cost', 'next_appointment', 'is_recovered', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'next_appointment': forms.DateInput(attrs={'type': 'date'}),
            'treatment': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['date', 'category', 'description', 'amount', 'paid_to', 'receipt_number']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }


class FeedRecordForm(forms.ModelForm):
    class Meta:
        model = FeedRecord
        fields = ['cow', 'date', 'feed_type', 'quantity_kg', 'cost', 'supplier', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, farm=None, **kwargs):
        super().__init__(*args, **kwargs)
        if farm:
            self.fields['cow'].queryset = Cow.objects.filter(farm=farm, is_active=True)
            self.fields['cow'].required = False


class SMSReminderForm(forms.ModelForm):
    class Meta:
        model = SMSReminder
        fields = ['cow', 'reminder_type', 'message', 'phone_number', 'scheduled_date']
        widgets = {
            'scheduled_date': forms.DateInput(attrs={'type': 'date'}),
            'message': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, farm=None, **kwargs):
        super().__init__(*args, **kwargs)
        if farm:
            self.fields['cow'].queryset = Cow.objects.filter(farm=farm, is_active=True)
            self.fields['cow'].required = False


class WeightRecordForm(forms.ModelForm):
    class Meta:
        model = WeightRecord
        fields = ['date', 'weight_kg', 'body_condition_score', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class BulkMilkEntryForm(forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
