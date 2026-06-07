from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path('auth/register/', views.register),
    path('auth/login/', views.login),
    path('auth/refresh/', TokenRefreshView.as_view()),
    path('auth/profile/', views.profile),
    path('events/', views.event_list),
    path('events/create/', views.event_create),
    path('events/<int:pk>/', views.event_detail),
    path('events/<int:pk>/seats/', views.event_seats),
    path('events/<int:pk>/update/', views.event_update),
    path('events/<int:pk>/delete/', views.event_delete),
    path('events/<int:pk>/book/', views.book_event),
    path('events/<int:pk>/wishlist/add/', views.wishlist_add),
    path('events/<int:pk>/wishlist/remove/', views.wishlist_remove),
    path('bookings/mine/', views.my_bookings),
    path('bookings/all/', views.all_bookings),
    path('bookings/pending-verifications/', views.pending_verifications),
    path('bookings/<int:pk>/cancel/', views.cancel_booking),
    path('bookings/<int:pk>/submit-utr/', views.submit_utr),
    path('bookings/<int:pk>/confirm-payment/', views.confirm_payment),
    path('bookings/<int:pk>/reject-payment/', views.reject_payment),
    path('wishlist/', views.my_wishlist),
    path('admin/dashboard/', views.admin_dashboard),
]