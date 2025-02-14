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

        user_program = UserProgram.objects.filter(user=request.user, is_paid=True).first()
        if not user_program:
            return False

        # is_paid + end_date >= today
        return user_program.is_subscription_active()


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
