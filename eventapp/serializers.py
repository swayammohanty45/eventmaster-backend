from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Profile, Event, Seat, Booking, Payment, Wishlist


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['role']


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    password2 = serializers.CharField(write_only=True)
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password', 'password2']

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError("Passwords do not match.")
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        return User.objects.create_user(**validated_data)


class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = ['id', 'row', 'number', 'seat_label', 'status']


class EventSerializer(serializers.ModelSerializer):
    seats_booked = serializers.SerializerMethodField()
    is_wishlisted = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = ['id', 'title', 'description', 'date', 'time', 'venue',
                  'price', 'available_seats', 'total_seats', 'rows',
                  'seats_per_row', 'category', 'is_featured',
                  'seats_booked', 'is_wishlisted', 'created_at']

    def get_seats_booked(self, obj):
        return obj.total_seats - obj.available_seats

    def get_is_wishlisted(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.wishlisted_by.filter(user=request.user).exists()
        return False


class BookingSerializer(serializers.ModelSerializer):
    event = EventSerializer(read_only=True)
    event_id = serializers.PrimaryKeyRelatedField(queryset=Event.objects.all(), write_only=True, source='event')
    total_amount = serializers.FloatField(read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    payment_status = serializers.SerializerMethodField()
    seat_labels = serializers.ListField(read_only=True)

    class Meta:
        model = Booking
        fields = ['id', 'username', 'user_email', 'event', 'event_id',
                  'num_tickets', 'status', 'booking_ref', 'ticket_number',
                  'utr_number', 'total_amount', 'payment_status',
                  'seat_labels', 'created_at', 'updated_at']
        read_only_fields = ['id', 'booking_ref', 'ticket_number', 'created_at', 'updated_at']

    def get_payment_status(self, obj):
        try:
            return obj.payment.payment_status
        except:
            return 'unpaid'


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'booking', 'amount', 'payment_status', 'transaction_id', 'upi_id', 'created_at']


class WishlistSerializer(serializers.ModelSerializer):
    event = EventSerializer(read_only=True)
    class Meta:
        model = Wishlist
        fields = ['id', 'event', 'added_at']