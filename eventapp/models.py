from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
import random, string


class Profile(models.Model):
    ROLE_CHOICES = (('user', 'User'), ('admin', 'Admin'))
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')

    def __str__(self):
        return f"{self.user.username} ({self.role})"

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


class Event(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateField()
    time = models.TimeField()
    venue = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    available_seats = models.PositiveIntegerField(default=100)
    total_seats = models.PositiveIntegerField(default=100)
    rows = models.PositiveIntegerField(default=10)
    seats_per_row = models.PositiveIntegerField(default=10)
    category = models.CharField(max_length=50, blank=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'time']

    def __str__(self):
        return self.title


class Seat(models.Model):
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('booked', 'Booked'),
        ('blocked', 'Blocked'),
    )
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='seats')
    row = models.CharField(max_length=5)       # A, B, C...
    number = models.PositiveIntegerField()      # 1, 2, 3...
    seat_label = models.CharField(max_length=10)  # A1, B5...
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='available')

    class Meta:
        unique_together = ('event', 'row', 'number')

    def __str__(self):
        return f"{self.event.title} - {self.seat_label} ({self.status})"


class Booking(models.Model):
    STATUS_CHOICES = (
        ('pending_payment', 'Pending Payment'),
        ('pending_verification', 'Pending Verification'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='bookings')
    seats = models.ManyToManyField(Seat, blank=True, related_name='bookings')
    num_tickets = models.PositiveIntegerField()
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='pending_payment')
    booking_ref = models.CharField(max_length=20, unique=True, blank=True)
    ticket_number = models.CharField(max_length=20, blank=True)
    utr_number = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.booking_ref:
            self.booking_ref = 'BK' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        super().save(*args, **kwargs)

    def generate_ticket_number(self):
        if not self.ticket_number:
            self.ticket_number = 'TKT' + ''.join(random.choices(string.digits, k=8))
            self.save()
        return self.ticket_number

    @property
    def total_amount(self):
        return float(self.event.price) * self.num_tickets

    @property
    def seat_labels(self):
        return [s.seat_label for s in self.seats.all()]

    def __str__(self):
        return f"{self.user.username} - {self.event.title} [{self.status}]"


class Payment(models.Model):
    STATUS_CHOICES = (('pending','Pending'),('paid','Paid'),('failed','Failed'))
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    payment_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=255, blank=True)
    upi_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='wishlisted_by')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'event')