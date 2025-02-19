from django.urls import path
from .views import (
    InitialRegisterView,
    VerifyCodeView,
    CompleteProfileView,
    UserProfileUpdateView,
    LoginView,
    ForgotPasswordView,
    ResetPasswordView,
    LogoutAPIView,
    ProgramLanguageView22,
    UpdateLanguageView22,
    SetReminderTimeView,
    UserProfileView,
    OrderCreate,
    SubscriptionOptionsAPIView
)

urlpatterns = [
    path("register/initial/", InitialRegisterView.as_view(), name="initial_register"),
    path("verify-code/", VerifyCodeView.as_view(), name="verify_code"),
    path("profile/complete/", CompleteProfileView.as_view(), name="complete_profile"),
    path("profile/update/", UserProfileUpdateView.as_view(), name="update_profile"),
    path("login/", LoginView.as_view(), name="login"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot_password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset_password"),
    path("set-reminder-time/", SetReminderTimeView.as_view(), name='set_reminder_time'),
    path("logout/", LogoutAPIView.as_view(), name="logout"),
    path("create/", OrderCreate.as_view(), name="create_order"),
    path("profile/", UserProfileView.as_view(), name="user_profile"),
    path("api/programs/language2", ProgramLanguageView22.as_view(), name="programs"),
    path("api/user/language2", UpdateLanguageView22.as_view(), name="update_language"),
    path("options/", SubscriptionOptionsAPIView.as_view(), name="subscription-options"),
]
