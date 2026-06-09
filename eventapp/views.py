from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from django.template.loader import render_to_string

from .models import Event, Seat, Booking, Payment, Wishlist
from .serializers import (EventSerializer, SeatSerializer, BookingSerializer,
                           PaymentSerializer, UserSerializer, RegisterSerializer, WishlistSerializer)

UPI_ID = 'BHARATPE2C0T0Z1G2A51103@unitype'

def is_admin(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'admin'

def create_seats_for_event(event):
    Seat.objects.filter(event=event).delete()
    rows = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    seats_created = 0
    total = event.total_seats
    for r_idx in range(event.rows):
        row_letter = rows[r_idx] if r_idx < 26 else f"R{r_idx+1}"
        for seat_num in range(1, event.seats_per_row + 1):
            if seats_created >= total:
                break
            Seat.objects.create(
                event=event,
                row=row_letter,
                number=seat_num,
                seat_label=f"{row_letter}{seat_num}",
                status='available'
            )
            seats_created += 1
        if seats_created >= total:
            break

# ── AUTH ──────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    s = RegisterSerializer(data=request.data)
    if s.is_valid():
        user = s.save()
        refresh = RefreshToken.for_user(user)
        return Response({'user': UserSerializer(user).data,
                         'access': str(refresh.access_token),
                         'refresh': str(refresh)}, status=201)
    return Response(s.errors, status=400)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    user = authenticate(username=request.data.get('username'), password=request.data.get('password'))
    if user:
        refresh = RefreshToken.for_user(user)
        return Response({'user': UserSerializer(user).data,
                         'access': str(refresh.access_token),
                         'refresh': str(refresh)})
    return Response({'error': 'Invalid credentials'}, status=401)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile(request):
    return Response(UserSerializer(request.user).data)


# ── EVENTS ────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def event_list(request):
    qs = Event.objects.all()
    search = request.GET.get('search')
    category = request.GET.get('category')
    if search:
        qs = qs.filter(Q(title__icontains=search)|Q(venue__icontains=search)|Q(description__icontains=search))
    if category:
        qs = qs.filter(category__icontains=category)
    return Response(EventSerializer(qs, many=True, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def event_detail(request, pk):
    event = get_object_or_404(Event, pk=pk)
    return Response(EventSerializer(event, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def event_seats(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if not event.seats.exists():
        create_seats_for_event(event)
    seats = event.seats.all().order_by('row', 'number')
    return Response(SeatSerializer(seats, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def event_create(request):
    if not is_admin(request.user):
        return Response({'error': 'Admin only'}, status=403)
    s = EventSerializer(data=request.data, context={'request': request})
    if s.is_valid():
        event = s.save()
# Auto-calculate rows and seats_per_row from total_seats
        import math
        total = event.total_seats
        cols = min(10, total)
        rows = math.ceil(total / cols)
        event.rows = rows
        event.seats_per_row = cols
        event.save()
        create_seats_for_event(event)
        return Response(s.data, status=201)
    return Response(s.errors, status=400)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def event_update(request, pk):
    if not is_admin(request.user):
        return Response({'error': 'Admin only'}, status=403)
    event = get_object_or_404(Event, pk=pk)
    s = EventSerializer(event, data=request.data, partial=True, context={'request': request})
    if s.is_valid():
        s.save()
        return Response(s.data)
    return Response(s.errors, status=400)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def event_delete(request, pk):
    if not is_admin(request.user):
        return Response({'error': 'Admin only'}, status=403)
    get_object_or_404(Event, pk=pk).delete()
    return Response({'message': 'Deleted'})


# ── BOOKINGS ──────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def book_event(request, pk):
    event = get_object_or_404(Event, pk=pk)
    seat_labels = request.data.get('seat_labels', [])
    num = len(seat_labels) if seat_labels else int(request.data.get('num_tickets', 1))

    if num < 1:
        return Response({'error': 'Select at least 1 seat'}, status=400)
    if num > event.available_seats:
        return Response({'error': 'Not enough seats available'}, status=400)

    booking = Booking.objects.create(
        user=request.user,
        event=event,
        num_tickets=num,
        status='pending_payment'
    )

    if seat_labels:
        booking.utr_number = f"SEATS:{','.join(seat_labels)}"
        booking.save()

    event.available_seats -= num
    event.save()

    return Response({
        **BookingSerializer(booking).data,
        'upi_id': UPI_ID,
        'amount': booking.total_amount,
        'seat_labels': seat_labels,
    }, status=201)
     


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_utr(request, pk):
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    utr = request.data.get('utr_number', '').strip()
    if not utr:
        return Response({'error': 'Please enter UTR / Transaction ID'}, status=400)
    if booking.status != 'pending_payment':
        return Response({'error': 'Booking already processed'}, status=400)
    booking.utr_number = utr
    booking.status = 'pending_verification'
    booking.save()
    Payment.objects.get_or_create(
        booking=booking,
        defaults={'amount': booking.total_amount, 'payment_status': 'pending',
                  'transaction_id': utr, 'upi_id': UPI_ID}
    )
    return Response({'message': 'Submitted. Waiting for admin verification.',
                     'booking': BookingSerializer(booking).data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_bookings(request):
    bookings = Booking.objects.filter(user=request.user).select_related('event').order_by('-created_at')
    return Response(BookingSerializer(bookings, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def all_bookings(request):
    if not is_admin(request.user):
        return Response({'error': 'Admin only'}, status=403)
    bookings = Booking.objects.select_related('user', 'event').order_by('-created_at')
    return Response(BookingSerializer(bookings, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_verifications(request):
    if not is_admin(request.user):
        return Response({'error': 'Admin only'}, status=403)
    bookings = Booking.objects.filter(status='pending_verification').select_related('user', 'event').order_by('-created_at')
    return Response(BookingSerializer(bookings, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_ticket_email(booking):
    """Send ticket confirmation email to user"""
    try:
        seat_info = ', '.join(booking.seat_labels) if booking.seat_labels else f"{booking.num_tickets} ticket(s)"
        
        subject = f"🎟️ Your Ticket Confirmed - {booking.event.title}"
        
        message = f"""
Dear {booking.username},

Your booking has been confirmed! Here are your ticket details:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ EVENTMASTER - OFFICIAL TICKET
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎟️ TICKET NUMBER: {booking.ticket_number}
📋 BOOKING REF:   {booking.booking_ref}

🎪 EVENT:    {booking.event.title}
📅 DATE:     {booking.event.date}
⏰ TIME:     {booking.event.time}
📍 VENUE:    {booking.event.venue}
💺 SEATS:    {seat_info}
🎫 TICKETS:  {booking.num_tickets}
💰 AMOUNT:   ₹{booking.total_amount:.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Please show this ticket number at the entry gate.

Thank you for booking with EventMaster!
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=None,  # uses DEFAULT_FROM_EMAIL
            recipient_list=[booking.user.email],
            fail_silently=True,  # won't crash if email fails
        )
    except Exception as e:
        print(f"Email sending failed: {e}")


def confirm_payment(request, pk):
    if not is_admin(request.user):
        return Response({'error': 'Admin only'}, status=403)
    booking = get_object_or_404(Booking, pk=pk)
    if booking.status != 'pending_verification':
        return Response({'error': 'Not pending verification'}, status=400)
    booking.status = 'confirmed'
    booking.generate_ticket_number()
    send_ticket_email(booking)  # new for email
    try:
        booking.payment.payment_status = 'paid'
        booking.payment.save()
    except:
        Payment.objects.create(booking=booking, amount=booking.total_amount,
                                payment_status='paid', transaction_id=booking.utr_number)
    return Response({'message': 'Confirmed! Ticket issued.',
                     'booking': BookingSerializer(booking).data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_payment(request, pk):
    if not is_admin(request.user):
        return Response({'error': 'Admin only'}, status=403)
    booking = get_object_or_404(Booking, pk=pk)
    if booking.status != 'pending_verification':
        return Response({'error': 'Not pending verification'}, status=400)
    booking.status = 'rejected'
    booking.save()
    booking.seats.update(status='available')
    booking.event.available_seats += booking.num_tickets
    booking.event.save()
    try:
        booking.payment.payment_status = 'failed'
        booking.payment.save()
    except:
        pass
    return Response({'message': 'Rejected. Seats restored.',
                     'booking': BookingSerializer(booking).data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    if booking.status in ['confirmed', 'rejected', 'cancelled']:
        return Response({'error': 'Cannot cancel this booking'}, status=400)
    booking.status = 'cancelled'
    booking.save()
    booking.seats.update(status='available')
    booking.event.available_seats += booking.num_tickets
    booking.event.save()
    return Response(BookingSerializer(booking).data)


# ── WISHLIST ──────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_wishlist(request):
    items = Wishlist.objects.filter(user=request.user).select_related('event')
    return Response(WishlistSerializer(items, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def wishlist_add(request, pk):
    event = get_object_or_404(Event, pk=pk)
    _, created = Wishlist.objects.get_or_create(user=request.user, event=event)
    return Response({'status': 'added' if created else 'already_exists'})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def wishlist_remove(request, pk):
    Wishlist.objects.filter(user=request.user, event_id=pk).delete()
    return Response({'status': 'removed'})


# ── ADMIN DASHBOARD ───────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_dashboard(request):
    if not is_admin(request.user):
        return Response({'error': 'Admin only'}, status=403)
    recent = Booking.objects.select_related('user', 'event').order_by('-created_at')[:5]
    revenue = Payment.objects.filter(payment_status='paid').aggregate(t=Sum('amount'))['t'] or 0
    return Response({
        'total_events': Event.objects.count(),
        'total_users': User.objects.count(),
        'total_bookings': Booking.objects.count(),
        'confirmed_bookings': Booking.objects.filter(status='confirmed').count(),
        'pending_verifications': Booking.objects.filter(status='pending_verification').count(),
        'total_revenue': float(revenue),
        'upcoming_events': Event.objects.filter(date__gte=__import__('datetime').date.today()).count(),
        'recent_bookings': BookingSerializer(recent, many=True).data,
        'category_stats': list(Event.objects.values('category').annotate(count=Count('id')).order_by('-count')[:6]),
    })