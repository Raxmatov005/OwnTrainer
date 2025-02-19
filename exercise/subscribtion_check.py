# Example in any view that requires an active subscription
from django.utils import timezone
from rest_framework.permissions import BasePermission

class IsSubscriptionActive(BasePermission):
    """
    Custom permission that only allows access if user has an active subscription.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        return UserSubscription.objects.filter(user=request.user,
                                               is_active=True,
                                               end_date__gte=timezone.now().date()).exists()





class StaffOrSubscriptionActive(BasePermission):
    """
    Allows access if the user is staff (admin/superuser)
    OR passes the IsSubscriptionActive check (meaning they have
    an active subscription).
    """

    def has_permission(self, request, view):
        # If user is an admin or superuser, skip subscription check
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Otherwise, require an active subscription
        return IsSubscriptionActive().has_permission(request, view)
