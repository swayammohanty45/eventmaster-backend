from django.contrib import admin
from .models import Profile, Event, Booking, Payment, Wishlist
admin.site.register(Profile)
admin.site.register(Event)
admin.site.register(Booking)
admin.site.register(Payment)
admin.site.register(Wishlist)
