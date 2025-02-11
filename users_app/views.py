
from django.contrib.auth import authenticate, login, get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from users_app.models import (User, Notification, Program, UserProgram, MealCompletion, Session,
                              SessionCompletion, ExerciseCompletion, Program, UserProgram, Session,
                              MealCompletion, SessionCompletion, UserProgram, Session, MealCompletion,
                              SessionCompletion, ExerciseCompletion)

from .models import Notification
from django.core.exceptions import ValidationError as DjangoValidationError
from users_app.serializers import (
    InitialRegisterSerializer, VerifyCodeSerializer, LoginSerializer,
    ForgotPasswordSerializer, ResetPasswordSerializer,
    ProgramSerializer, LanguageUpdateSerializer,
    UserPaymentSerializer, UserProfileSerializer, CompleteProfileSerializer, UserProfileUpdateSerializer
	)
from django.core.validators import EmailValidator
import random
import logging
import re
from datetime import datetime, timedelta, timezone	


from django.core.mail import send_mail
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import FormParser, MultiPartParser

from drf_yasg import openapi
from .eskiz_api import EskizAPI
from .serializers import (
    InitialRegisterSerializer,
    VerifyCodeSerializer,
    CompleteProfileSerializer
)
from rest_framework import views
from rest_framework import response
from payme import Payme
from register import settings
from drf_yasg.utils import swagger_auto_schema
from django.conf import settings
from .tasks import send_scheduled_notification




logger = logging.getLogger(__name__)
User = get_user_model()




eskiz_api = EskizAPI(email=settings.ESKIZ_EMAIL, password=settings.ESKIZ_PASSWORD)



try:
    goal_choices = [program.program_goal for program in Program.objects.all()]
except Exception as e:
    logger.warning(f"Failed to fetch Program model data: {e}")
    goal_choices = []



import smtplib
from email.message import EmailMessage
from django.conf import settings







def send_verification_email(subject, body, to_email):
    smtp_server = "smtp.gmail.com"
    port = 587
    sender_email = settings.EMAIL_HOST_USER
    sender_password = settings.EMAIL_HOST_PASSWORD

    try:
        # Ensure subject and body are plain strings
        subject = str(subject)
        body = str(body)

        # Create an EmailMessage object
        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = to_email

        # Set timeout for SMTP connection
        timeout = 10  # 10 seconds timeout

        # Send the email
        with smtplib.SMTP(smtp_server, port, timeout=timeout) as server:
            server.ehlo()
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)

        logger.info(f"Email successfully sent to {to_email}")

    except (smtplib.SMTPException, socket.timeout) as e:
        logger.error(f"Email sending failed: {e}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise



# Initial Register View
class InitialRegisterView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [FormParser, MultiPartParser]

    @swagger_auto_schema(
        operation_description="Register with basic information",
        consumes=['multipart/form-data'],
        manual_parameters=[
            openapi.Parameter('first_name', openapi.IN_FORM, description="First Name", type=openapi.TYPE_STRING,
                              required=True),
            openapi.Parameter('last_name', openapi.IN_FORM, description="Last Name", type=openapi.TYPE_STRING,
                              required=True),
            openapi.Parameter('email_or_phone', openapi.IN_FORM, description="Email or Phone (+ format)",
                              type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('password', openapi.IN_FORM, description="Password", type=openapi.TYPE_STRING,
                              required=True),
        ],
        responses={
            201: openapi.Response(
                description="User registered",
                examples={
                    "application/json": {
                        "user_id": 1,
                        "first_name": "John",
                        "last_name": "Doe",
                        "email_or_phone": "+1234567890",
                        "message": "User registered. Please verify your account."
                    }
                }
            )
        }
    )
    def post(self, request):
        serializer = InitialRegisterSerializer(data=request.data)
        if serializer.is_valid():
            identifier = serializer.validated_data["email_or_phone"]
            existing_user = User.objects.filter(email_or_phone=identifier).first()

            if existing_user:
                # User exists
                if existing_user.is_active:
                    return Response(
                        {"error": _("This email or phone number is already registered.")},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                else:
                    # Resend verification code
                    verification_code = random.randint(1000, 9999)
                    logger.info(f"Verification code: {verification_code}")
                    phone_pattern = re.compile(r"^\+\d+$")
                    is_phone = bool(phone_pattern.match(identifier))

                    try:
                        if is_phone:
                            eskiz_api.send_sms(
                                identifier,
                                message=_(
                                    f"Workout ilovasiga ro'yxatdan o'tish uchun tasdiqlash kodi: {verification_code}"
                                ).format(code=verification_code),
                            )
                        else:
                            send_verification_email(
                                subject=_("Your Verification Code"),
                                body=_("Your verification code is: {code}").format(
                                    code=verification_code
                                ),
                                to_email=identifier,
                            )

                        cache.set(
                            f"verification_code_{existing_user.id}",
                            {"code": verification_code, "timestamp": datetime.now().timestamp()},
                            timeout=7300,
                        )
                        return Response(
                            {"user_id": existing_user.id, "message": _("Verification code resent.")},
                            status=status.HTTP_200_OK,
                        )
                    except Exception as e:
                        logger.error(f"Failed to send verification code: {e}")
                        return Response(
                            {"error": _("Failed to send verification code. Please try again.")},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )

            else:
                # Create a new user
                user = serializer.save()
                verification_code = random.randint(1000, 9999)
                logger.info(f"Verification code: {verification_code}")
                phone_pattern = re.compile(r"^\+\d+$")
                is_phone = bool(phone_pattern.match(identifier))

                try:
                    if is_phone:
                        eskiz_api.send_sms(
                            identifier,
                            message=_(
                                f"Workout ilovasiga ro'yxatdan o'tish uchun tasdiqlash kodi: {verification_code}"
                            ).format(code=verification_code),
                        )
                    else:
                        send_verification_email(
                            subject=_("Your Verification Code"),
                            body=_("Your verification code is: {code}").format(
                                code=verification_code
                            ),
                            to_email=identifier,
                        )
                except Exception as e:
                    logger.error(f"Failed to send verification code: {e}")
                    user.delete()
                    return Response(
                        {"error": _("Failed to send verification code. Please try again.")},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

                cache.set(
                    f"verification_code_{user.id}",
                    {"code": verification_code, "timestamp": datetime.now().timestamp()},
                    timeout=7300,
                )
                return Response(
                    {"user_id": user.id, "message": _("User registered. Please verify your account.")},
                    status=status.HTTP_201_CREATED,
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)







class VerifyCodeView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    """
    Verify the user's code and activate the user account.
    """

    @swagger_auto_schema(
        operation_description="Verify a user's code to activate the account.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'user_id': openapi.Schema(
                    type=openapi.TYPE_INTEGER, 
                    description="The ID of the user."
                ),
                'code': openapi.Schema(
                    type=openapi.TYPE_STRING, 
                    description="The verification code sent to the user."
                ),
            },
            required=['user_id', 'code'],
        ),
        responses={
            200: openapi.Response(
                description="Verification successful.",
                examples={
                    "application/json": {
                        "message": "Verification successful. You can now complete your profile."
                    }
                }
            ),
            400: openapi.Response(
                description="Invalid verification code or expired.",
                examples={
                    "application/json": {
                        "error": "Verification code expired or invalid."
                    }
                }
            ),
            404: openapi.Response(
                description="User not found.",
                examples={
                    "application/json": {
                        "error": "User not found."
                    }
                }
            ),
        },
    )
    def post(self, request):
        user_id = request.data.get('user_id')
        code = request.data.get('code')

        # Fetch the user
        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response(
                {"error": _("User not found.")},
                status=status.HTTP_404_NOT_FOUND
            )

        # Fetch the verification code from cache
        cached_data = cache.get(f'verification_code_{user.id}')
        print(f"This is cashed data if it is exists {cached_data}")
        if not cached_data:
            return Response(
                {"error": _("Verification code expired or invalid.")},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Compare the codes
        if str(cached_data['code']) != str(code):
            return Response(
                {"error": _("Invalid verification code.")},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if the code has expired
        code_timestamp = datetime.fromtimestamp(cached_data['timestamp'])
        if datetime.now() - code_timestamp > timedelta(minutes=10):  # Adjust expiration time if needed
            return Response(
                {"error": _("Verification code expired.")},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Activate the user
        user.is_active = True
        user.save()

        # Clear the code from cache
        cache.delete(f'verification_code_{user.id}')

        return Response(
            {"message": _("Verification successful. You can now complete your profile.")},
            status=status.HTTP_200_OK
        )






def get_goal_choices():
    return list(Program.objects.values_list('program_goal', flat=True))

class CompleteProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [FormParser, MultiPartParser]  # Enable form data parsing

    @swagger_auto_schema(
        operation_description="Complete the user profile with additional details",
        consumes=['multipart/form-data'],
        manual_parameters=[
            openapi.Parameter(
                'gender',
                openapi.IN_FORM,
                description="Gender",
                type=openapi.TYPE_STRING,
                enum=["Male", "Female"],
                required=True
            ),
            openapi.Parameter(
                'country',
                openapi.IN_FORM,
                description="Country",
                type=openapi.TYPE_STRING,
                enum=["Uzbekistan", "Russia", "Kazakhstan", "Other"],
                required=True
            ),
            openapi.Parameter(
                'age',
                openapi.IN_FORM,
                description="Age",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
            openapi.Parameter(
                'height',
                openapi.IN_FORM,
                description="Height (in cm)",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
            openapi.Parameter(
                'weight',
                openapi.IN_FORM,
                description="Weight (in kg)",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
            openapi.Parameter(
                'level',
                openapi.IN_FORM,
                description="Level",
                type=openapi.TYPE_STRING,
                enum=["Beginner", "Intermediate", "Advanced"],
                required=True
            ),
            openapi.Parameter(
                'goal',
                openapi.IN_FORM,
                description="Goal",
                type=openapi.TYPE_STRING,
                enum=lambda: get_goal_choices(),
                required=True
            ),
        ],
        responses={200: "Profile completed successfully."}
    )
    def patch(self, request):
        serializer = CompleteProfileSerializer(instance=request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            user = request.user


            if user.goal:
                program = Program.objects.filter(program_goal=user.goal).first()
                if program:
                    start_date = datetime.now().date()
                    total_sessions = program.sessions.count()
                    end_date = start_date + timedelta(days=total_sessions)

                    user_program = UserProgram.objects.create(
                        user=user,
                        program=program,
                        start_date=start_date,
                        end_date=end_date
                    )

                    sessions = program.sessions.order_by('session_number')
                    for index, session in enumerate(sessions, start=1):
                        session_date = start_date + timedelta(days=index - 1)

                        # Create MealCompletion
                        for meal in session.meals.all():
                            MealCompletion.objects.create(
                                user=user,
                                meal=meal,
                                session=session,
                                is_completed=False,
                                meal_date=session_date,
                                completion_date=None,
                            )

                        # Create SessionCompletion
                        SessionCompletion.objects.create(
                            user=user,
                            session=session,
                            is_completed=False,
                            session_number_private=session.session_number,
                            session_date=session_date
                        )

                        # Create ExerciseCompletion
                        for exercise in session.exercises.all():
                            ExerciseCompletion.objects.create(
                                user=user,
                                exercise=exercise,
                                session=session,
                                is_completed=False,
                                exercise_date=session_date
                            )

            return Response({"message": _("Profile completed successfully.")}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [FormParser, MultiPartParser]

    @swagger_auto_schema(
        operation_description="Update user's profile details",
        request_body=UserProfileUpdateSerializer,
        responses={200: "Profile updated successfully."}
    )
    def patch(self, request):
        serializer = UserProfileUpdateSerializer(instance=request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": _("Profile updated successfully.")}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=LoginSerializer)
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            email_or_phone = serializer.validated_data['email_or_phone']
            password = serializer.validated_data['password']
            print(email_or_phone,password)

            user = User.objects.filter(email_or_phone=email_or_phone).first()
            print(user)

            if user:
                if not user.is_active:
                    user.is_active = True
                    user.save(update_fields=['is_active'])

                user = authenticate(request, email_or_phone=email_or_phone, password=password)
                print(user)  # Agar foydalanuvchi topilsa, user obyektini qaytaradi
                if user:
                    login(request, user)
                    refresh = RefreshToken.for_user(user)
                    return Response({
                        "message": _("Login successful"),
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                    }, status=status.HTTP_200_OK)

            return Response({"error": _("Invalid credentials")}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=ForgotPasswordSerializer)
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email_or_phone = serializer.validated_data['email_or_phone']
            user = User.objects.filter(email_or_phone=email_or_phone).first()

            if user:
                verification_code = random.randint(1000, 9999)
                cache.set(f'verification_code_{user.id}', verification_code, timeout=300)
                try:
                    if re.match(r'^\+998\d{9}$', email_or_phone):
                        eskiz_api.send_sms(
                            email_or_phone,
                            _("Your password reset verification code is {code}").format(code=verification_code)
                        )
                    else:
                        send_mail(
                            subject=_("Your Password Reset Verification Code"),
                            message=_("Your password reset verification code is {code}.").format(code=verification_code),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[user.email_or_phone]
                        )
                    return Response({"message": _("Verification code sent")}, status=status.HTTP_200_OK)
                except Exception as e:
                    logger.error(f"Failed to send password reset verification: {e}")
                    return Response({"error": _("Failed to send verification code")},
                                    status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response({"error": _("User not found")}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=ResetPasswordSerializer)
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email_or_phone = serializer.validated_data['email_or_phone']
            verification_code = serializer.validated_data['verification_code']
            new_password = serializer.validated_data['new_password']
            user = User.objects.filter(email_or_phone=email_or_phone).first()

            if user and str(cache.get(f'verification_code_{user.id}')) == str(verification_code):
                user.set_password(new_password)
                user.save()
                cache.delete(f'verification_code_{user.id}')
                return Response({"message": _("Password reset successful")}, status=status.HTTP_200_OK)

            return Response({"error": _("Invalid or expired verification code")}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        user.is_active = False
        user.save()

        if hasattr(request.auth, 'delete'):
            request.auth.delete()

        return Response({"message": _("Foydalanuvchi tizimdan muvaffaqiyatli chiqarildi.")}, status=200)


payme = Payme(payme_id=settings.PAYME_ID)


class OrderCreate(views.APIView):
    serializer_class = UserPaymentSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        result = {
            "order": serializer.data
        }

        if serializer.data["payment_method"] == "payme":
            payment_link = payme.initializer.generate_pay_link(
                id=serializer.data["id"],
                amount=serializer.data["amount"],
                return_url="https://uzum.uz"
            )
            result["payment_link"] = payment_link

        return response.Response(result)


class ProgramLanguageView22(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        language = user.language

        user_programs = UserProgram.objects.filter(user=user, is_active=True, is_paid=True)  # Only show paid
        programs = [user_program.program for user_program in user_programs]

        serializer = ProgramSerializer(programs, many=True, context={'request': request})
        return Response({
            "message": _("Programs retrieved successfully"),
            "language": language,
            "programs": serializer.data,
        }, status=status.HTTP_200_OK)


class UpdateLanguageView22(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LanguageUpdateSerializer

    @swagger_auto_schema(request_body=LanguageUpdateSerializer)
    def post(self, request):
        serializer = LanguageUpdateSerializer(data=request.data)
        if serializer.is_valid():
            new_language = serializer.validated_data['language']
            user = request.user
            user.language = new_language
            user.save()
            return Response({"message": _("Language updated successfully")}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=200)





class SetReminderTimeView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "reminder_time": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Time in 'HH:MM' format",
                    example="14:30"
                ),
            },
            required=["reminder_time"]
        )
    )
    def post(self, request):
        reminder_time = request.data.get("reminder_time")
        if not reminder_time:
            return Response({"error": "No time provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            formatted_time = datetime.strptime(reminder_time, "%H:MM").time()
            request.user.reminder_time = formatted_time
            request.user.save()

            reminder_time_5min_early = datetime.combine(now().date(), formatted_time) - timedelta(minutes=5)

            message = {
                "uz": "Sizning mashqingizga 5 daqiqa qoldi!",
                "ru": "До вашей тренировки осталось 5 минут!",
                "en": "5 minutes left until your workout!"
            }
            final_message = message.get(request.user.language, message["en"])

            notification = Notification.objects.create(
                user=request.user,
                message=final_message,
                notification_type="reminder",
                scheduled_time=reminder_time_5min_early
            )

            send_scheduled_notification.apply_async(
                (notification.id,), eta=reminder_time_5min_early
            )

            return Response({
                "message": "Reminder time set successfully.",
                "reminder_time": str(formatted_time),
                "notification_scheduled_at": str(reminder_time_5min_early.time())
            }, status=status.HTTP_200_OK)

        except ValueError:
            return Response({"error": "Invalid time format. Use 'HH:MM' format."}, status=status.HTTP_400_BAD_REQUEST)
