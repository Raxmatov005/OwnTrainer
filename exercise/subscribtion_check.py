from django.utils import timezone
from rest_framework.permissions import BasePermission
from django.utils.translation import gettext_lazy as _
from users_app.models import UserSubscription  # Ensure this import is correct


class IsSubscriptionActive(BasePermission):
    """
    ✅ Allows access if the user has an active subscription.
    ✅ Admins and staff can bypass this check.
    """

    def has_permission(self, request, view):
        # ✅ Allow superusers and staff without checking subscription
        if request.user.is_staff or request.user.is_superuser:
            return True

        # ✅ Check if regular users have an active subscription
        has_subscription = UserSubscription.objects.filter(
            user=request.user, is_active=True, end_date__gte=timezone.now().date()
        ).exists()

        if not has_subscription:
            self.message = {
                "error": _("Please upgrade your subscription to access exercise blocks."),
                "subscription_options_url": request.build_absolute_uri("/api/subscriptions/options/")
            }
            return False

        return True


class StaffOrSubscriptionActive(BasePermission):
    """
    ✅ Allows access if:
      - The user is an admin/superuser/staff **OR**
      - The user has an active subscription.
    """

    def has_permission(self, request, view):
        # ✅ Allow admins and staff without checking subscription
        if request.user.is_staff or request.user.is_superuser:
            return True

        # ✅ Require an active subscription for regular users
        return IsSubscriptionActive().has_permission(request, view)