from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from unittest.mock import patch
from users_app.models import User, UserSubscription
from click_app.views import SUBSCRIPTION_COSTS
import logging

# Set up logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClickPaymentTests(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            email_or_phone="test@example.com",
            password="testpassword",
            first_name="Test",
            last_name="User"
        )
        # Create a subscription
        self.subscription = UserSubscription.objects.create(
            user=self.user,
            subscription_type="month",
            amount_in_soum=SUBSCRIPTION_COSTS["month"],  # 1000 so'm
            start_date=timezone.now().date(),
            is_active=False
        )
        self.client = APIClient()

    def test_user_subscription_amount_calculation(self):
        """Test that the amount property returns the correct value in tiyins."""
        self.assertEqual(self.subscription.amount_in_soum, 1000)  # 1000 so'm
        self.assertEqual(self.subscription.amount, 100000)  # 1000 * 100 = 100,000 tiyins

    @patch("click_app.views.PyClick.generate_url")
    def test_create_click_order(self, mock_generate_url):
        """Test the CreateClickOrderView to ensure it generates the correct payment URL."""
        mock_generate_url.return_value = "https://click.uz/test-payment-url"
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("create_click_order"),
            {"subscription_type": "month"},
            format="json"
        )

        self.assertEqual(response.status_code, 302)  # Redirect to payment URL
        self.assertEqual(response.url, "https://click.uz/test-payment-url")
        mock_generate_url.assert_called_once_with(
            order_id=self.subscription.id,
            amount=str(self.subscription.amount),  # 100,000 tiyins
            return_url="https://owntrainer.uz/"
        )

    def test_click_prepare_api(self):
        """Test the ClickPrepareAPIView to ensure it validates the amount correctly."""
        response = self.client.post(
            reverse("click_prepare"),
            {
                "order_id": self.subscription.id,
                "amount": self.subscription.amount,  # 100,000 tiyins
                "merchant_id": "31383",
                "service_id": "test_service"
            },
            format="multipart"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"error": 0})

    def test_click_prepare_api_amount_mismatch(self):
        """Test the ClickPrepareAPIView with an incorrect amount."""
        response = self.client.post(
            reverse("click_prepare"),
            {
                "order_id": self.subscription.id,
                "amount": 1,  # Incorrect amount (should be 100,000 tiyins)
                "merchant_id": "31383",
                "service_id": "test_service"
            },
            format="multipart"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": -1})

    def test_click_complete_api(self):
        response = self.client.post(
            reverse("click_complete"),
            {
                "order_id": self.subscription.id,
                "amount": self.subscription.amount,
                "state": "1"
            },
            format="multipart"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"result": {"code": 0}})
        self.subscription.refresh_from_db()
        self.assertTrue(self.subscription.is_active)
        self.assertEqual(self.subscription.end_date, self.subscription.start_date + timezone.timedelta(days=30))


    def test_click_complete_api_failed_payment(self):
        """Test the ClickCompleteAPIView with a failed payment."""
        response = self.client.post(
            reverse("click_complete"),
            {
                "order_id": self.subscription.id,
                "amount": self.subscription.amount,  # 100,000 tiyins
                "state": "0"  # Payment failed
            },
            format="multipart"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"result": {"code": 0}})

        # Refresh subscription from database
        self.subscription.refresh_from_db()
        self.assertFalse(self.subscription.is_active)