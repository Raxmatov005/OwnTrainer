from rest_framework import viewsets, status
from users_app.models import Program, Session, SessionCompletion, ExerciseBlock
from exercise.serializers import ProgramSerializer, SessionNestedSerializer, EmptyQuerySerializer
from django.utils.translation import gettext_lazy as _
from drf_yasg.utils import swagger_auto_schema
from exercise.permissions import IsAdminOrReadOnly
from users_app.models import translate_text
from rest_framework.views import APIView
from datetime import timedelta
from threading import Timer
from drf_yasg import openapi
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils.timezone import now
from django.utils.dateparse import parse_date
from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser, JSONParser, FormParser
from .subscribtion_check import IsSubscriptionActive
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone


# ----- Define a manual schema for Session creation -----
session_create_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "program": openapi.Schema(
            type=openapi.TYPE_INTEGER,
            description="ID of the Program"
        ),
        "meals": openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(type=openapi.TYPE_INTEGER),
            description="List of Meal IDs (optional)"
        ),
        "block": openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "block_name": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Name of the exercise block"
                ),
                "block_image": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="URL for the block image"
                ),
                "block_kkal": openapi.Schema(
                    type=openapi.TYPE_NUMBER,
                    description="Calories associated with the block"
                ),
                "block_water_amount": openapi.Schema(
                    type=openapi.TYPE_NUMBER,
                    description="Water amount for the block"
                ),
                "description": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Description of the block"
                ),
                "video_url": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Video URL for the block"
                ),
                "block_time": openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="Duration of the block (in seconds)"
                ),
                "calories_burned": openapi.Schema(
                    type=openapi.TYPE_NUMBER,
                    description="Calories burned during the block"
                ),
                "exercises": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "name": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Name of the exercise"
                            ),
                            "sequence_number": openapi.Schema(
                                type=openapi.TYPE_INTEGER,
                                description="Sequence number of the exercise"
                            ),
                            "exercise_time": openapi.Schema(
                                type=openapi.TYPE_INTEGER,
                                description="Duration of the exercise in seconds"
                            ),
                            "description": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Description of the exercise"
                            ),
                            "image": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                description="Image URL for the exercise"
                            ),
                        },
                        required=["name", "sequence_number", "exercise_time"],
                        description="An exercise within the block"
                    ),
                    description="List of nested exercises"
                ),
            },
            required=["block_name", "exercises"],
            description="Data for the nested exercise block"
        ),
    },
    required=["program", "block"],
    description="Payload for creating a new session with a nested exercise block."
)

class ProgramViewSet(viewsets.ModelViewSet):
    queryset = Program.objects.all()
    serializer_class = ProgramSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        language = self.request.query_params.get('lang', 'en')
        context['language'] = language
        return context

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Program.objects.all()
        user_goal = getattr(self.request.user, 'goal', None)
        return Program.objects.filter(is_active=True, program_goal=user_goal)

    @swagger_auto_schema(tags=['Programs'], operation_description=_("List all active programs"))
    def list(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({"programs": serializer.data})

    @swagger_auto_schema(tags=['Programs'], operation_description=_("Retrieve program by ID"))
    def retrieve(self, request, pk=None):
        program = self.get_object()
        serializer = self.get_serializer(program)
        return Response({"program": serializer.data})

    @swagger_auto_schema(tags=['Programs'], operation_description=_("Create a new program"))
    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        language = request.user.language
        if serializer.is_valid():
            serializer.save()
            message = translate_text("Program created successfully", language)
            return Response({"message": message, "program": serializer.data})
        return Response(serializer.errors, status=400)

    @swagger_auto_schema(tags=['Programs'], operation_description=_("Update a program by ID"))
    def update(self, request, pk=None):
        program = self.get_object()
        serializer = self.get_serializer(program, data=request.data)
        language = request.user.language
        if serializer.is_valid():
            serializer.save()
            message = translate_text("Program updated successfully", language)
            return Response({"message": message, "program": serializer.data})
        return Response(serializer.errors, status=400)

    @swagger_auto_schema(tags=['Programs'], operation_description=_("Partially update a program by ID"))
    def partial_update(self, request, pk=None):
        program = self.get_object()
        serializer = self.get_serializer(program, data=request.data, partial=True)
        language = request.user.language
        if serializer.is_valid():
            serializer.save()
            message = translate_text("Program partially updated successfully", language)
            return Response({"message": message, "program": serializer.data})
        return Response(serializer.errors, status=400)

    @swagger_auto_schema(tags=['Programs'], operation_description=_("Delete a program"))
    def destroy(self, request, pk=None):
        if not request.user.is_superuser:
            message = translate_text("You do not have permission to delete a program.", request.user.language)
            return Response({"error": message}, status=403)
        program = self.get_object()
        program.delete()
        message = translate_text("Program deleted successfully", request.user.language)
        return Response({"message": message})


class SessionViewSet(viewsets.ModelViewSet):
    """
    Updated Session view.
    """
    queryset = Session.objects.all()
    serializer_class = SessionNestedSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        language = self.request.query_params.get('lang', 'en')
        context['language'] = language
        return context

    def get_serializer(self, *args, **kwargs):
        if self.action == 'reset_today_session':
            return None
        return super().get_serializer(*args, **kwargs)

    @swagger_auto_schema(
        tags=['Sessions'],
        operation_description=_("Create a new session for a program (with nested exercise block)."),
        request_body=session_create_schema
    )
    def create(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return Response({"error": _("You do not have permission to create a session.")},
                            status=status.HTTP_403_FORBIDDEN)
        program_id = request.data.get('program')
        if not program_id:
            return Response({"error": _("Program ID is required to create a session.")},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            program = Program.objects.get(id=program_id)
        except Program.DoesNotExist:
            return Response({"error": _("Specified program does not exist.")},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": _("Session created successfully"),
                "session": serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['Sessions'],
        operation_description=_("Retrieve session by ID")
    )
    def retrieve(self, request, pk=None):
        session = self.get_object()
        serializer = self.get_serializer(session)
        return Response({"session": serializer.data})

    @swagger_auto_schema(
        tags=['Sessions'],
        operation_description=_("Update a session by ID")
    )
    def update(self, request, pk=None):
        session = self.get_object()
        if not request.user.is_superuser:
            return Response({"error": _("You do not have permission to update this session.")}, status=403)
        serializer = self.get_serializer(session, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": _("Session updated successfully"), "session": serializer.data})
        return Response(serializer.errors, status=400)

    @swagger_auto_schema(
        tags=['Sessions'],
        operation_description=_("Partially update a session by ID")
    )
    def partial_update(self, request, pk=None):
        session = self.get_object()
        if not request.user.is_superuser:
            return Response({"error": _("You do not have permission to partially update this session.")}, status=403)
        serializer = self.get_serializer(session, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": _("Session partially updated successfully"), "session": serializer.data})
        return Response(serializer.errors, status=400)

    @swagger_auto_schema(
        tags=['Sessions'],
        operation_description=_("Delete a session")
    )
    def destroy(self, request, pk=None):
        if not request.user.is_superuser:
            return Response({"error": _("You do not have permission to delete this session.")}, status=403)
        session = self.get_object()
        session.delete()
        return Response({"message": _("Session deleted successfully")})

    @swagger_auto_schema(
        tags=['Sessions'],
        operation_description=_("List sessions for the user. Staff sees all sessions."),
        query_serializer=EmptyQuerySerializer()
    )
    def list(self, request):
        from users_app.models import UserSubscription, UserProgram
        user_subscription = UserSubscription.objects.filter(user=request.user, is_active=True).first()
        if not user_subscription or not user_subscription.is_subscription_active():
            return Response({"error": _("Your subscription has ended. Please renew.")}, status=403)
        user_program = UserProgram.objects.filter(user=request.user, is_active=True).first()
        if not user_program:
            return Response({"error": _("No active program found for the user.")}, status=404)
        incomplete_sc = SessionCompletion.objects.filter(
            user=request.user,
            session__program=user_program.program,
            is_completed=False
        ).select_related('session').order_by('session__session_number')
        if not incomplete_sc.exists():
            return Response({"message": _("You have completed all sessions!")}, status=200)
        next_sc = incomplete_sc.first()
        next_session_number = next_sc.session.session_number
        session_ids = [sc.session_id for sc in incomplete_sc]
        sessions = Session.objects.filter(id__in=session_ids).order_by('session_number')
        data = []
        for s in sessions:
            ser = self.get_serializer(s).data
            ser["locked"] = (s.session_number > next_session_number)
            data.append(ser)
        return Response({"sessions": data}, status=200)

    @swagger_auto_schema(
        tags=['Sessions'],
        operation_description=_("Get a session by session_number for the user's active program"),
        manual_parameters=[
            openapi.Parameter(
                'session_number',
                openapi.IN_QUERY,
                description="Session number to retrieve the session details.",
                type=openapi.TYPE_INTEGER,
                required=True
            )
        ],
        responses={
            200: SessionNestedSerializer(),
            400: "session_number is required.",
            404: "Session not found or no active program."
        },
        query_serializer=EmptyQuerySerializer()
    )
    @action(detail=False, methods=['get'], url_path='by-session-number')
    def get_by_session_number(self, request):
        from users_app.models import UserProgram
        user_program = UserProgram.objects.filter(user=request.user, is_active=True).first()
        if not user_program:
            return Response({"error": _("No active program found for the logged-in user.")},
                            status=404)
        session_number = request.query_params.get('session_number')
        if not session_number:
            return Response({"error": "session_number is required."}, status=400)
        try:
            session = Session.objects.get(program=user_program.program, session_number=session_number)
        except Session.DoesNotExist:
            return Response({"error": "Session not found for the given session_number in the user's program."},
                            status=404)
        serializer = self.get_serializer(session)
        return Response(serializer.data, status=200)

    @swagger_auto_schema(
        operation_description=_("Reset today's session for the logged-in user"),
        responses={
            200: "Today's session has been reset successfully.",
            404: "No session found for today."
        },
        request_body=None
    )
    @action(detail=False, methods=['post'], url_path='reset-today-session', permission_classes=[IsAuthenticated])
    def reset_today_session(self, request):
        from users_app.models import SessionCompletion
        today_sc = SessionCompletion.objects.filter(
            user=request.user,
            session_date=now().date()
        ).first()
        if not today_sc:
            return Response({"error": _("No session found for today.")}, status=404)
        today_sc.is_completed = False
        today_sc.completion_date = None
        today_sc.save()
        return Response({"message": _("Today's session has been reset successfully.")}, status=200)


class CompleteBlockView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=['Sessions'],
        operation_description=_("Complete the entire exercise block for a session."),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'block_id': openapi.Schema(type=openapi.TYPE_INTEGER, description="ID of the ExerciseBlock")
            },
            required=['block_id']
        ),
        responses={200: "Block completed successfully. Session completed."}
    )
    def post(self, request):
        block_id = request.data.get("block_id")
        if not block_id:
            return Response({"error": _("block_id is required.")}, status=400)
        block = get_object_or_404(ExerciseBlock, id=block_id)
        from users_app.models import UserProgram
        user_program = UserProgram.objects.filter(user=request.user, is_active=True).first()
        if not request.user.is_staff:
            if not user_program or not user_program.is_subscription_active():
                return Response({"error": _("Your subscription has ended. Please renew.")}, status=403)
        bc, created = block.completions.get_or_create(user=request.user)
        if bc.is_completed:
            return Response({"message": _("Block already completed.")}, status=200)
        bc.is_completed = True
        bc.save()
        return Response({"message": _("Block completed successfully.")}, status=200)


class ExerciseViewSet(viewsets.ModelViewSet):
    queryset = Exercise.objects.all()
    serializer_class = NestedExerciseSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    def get_user_language(self):
        return getattr(self.request.user, 'language', 'en')

    @swagger_auto_schema(
        tags=['Exercises'],
        operation_description=_("List exercises for a specific session"),
        query_serializer=EmptyQuerySerializer()
    )
    def list(self, request):
        if not request.user.is_authenticated:
            return Response({"error": "Authentication credentials were not provided."}, status=403)
        session_id = request.query_params.get('session_id')
        queryset = self.get_queryset().filter(sessions__id=session_id) if session_id else self.get_queryset()
        if not request.user.is_superuser:
            queryset = queryset.filter(sessions__program__is_active=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response({"exercises": serializer.data})

    @swagger_auto_schema(
        tags=['Exercises'],
        operation_description=_("Retrieve exercises by category ID"),
        manual_parameters=[
            openapi.Parameter(
                'category_id',
                openapi.IN_QUERY,
                description="ID of the category to filter exercises by",
                type=openapi.TYPE_INTEGER,
                required=True
            )
        ],
        responses={
            200: openapi.Response(
                description="A list of exercises in the specified category",
                schema=NestedExerciseSerializer(many=True)
            ),
            400: "Category ID is required",
            404: "No exercises found for the given category"
        },
        query_serializer=EmptyQuerySerializer()
    )
    @action(detail=False, methods=['get'], url_path='by-category')
    def by_category(self, request):
        language = self.get_user_language()
        category_id = request.query_params.get('category_id')
        if not category_id:
            message = translate_text("Category ID is required.", language)
            return Response({"error": message}, status=400)
        queryset = self.get_queryset().filter(category_id=category_id)
        if not queryset.exists():
            message = translate_text("No exercises found for the given category.", language)
            return Response({"message": message}, status=404)
        serializer = self.get_serializer(queryset, many=True)
        return Response({"exercises": serializer.data})

    @swagger_auto_schema(tags=['Exercises'], operation_description=_("Retrieve exercise by ID"))
    def retrieve(self, request, pk=None):
        exercise = self.get_object()
        serializer = self.get_serializer(exercise)
        return Response({"exercise": serializer.data})

    @swagger_auto_schema(tags=['Exercises'], operation_description=_("Create a new exercise"))
    def create(self, request):
        language = self.get_user_language()
        if not request.user.is_superuser:
            message = translate_text("You do not have permission to create an exercise.", language)
            return Response({"error": message}, status=403)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            message = translate_text("Exercise created successfully", language)
            return Response({"message": message, "exercise": serializer.data})
        return Response(serializer.errors, status=400)

    @swagger_auto_schema(tags=['Exercises'], operation_description=_("Update an exercise by ID"))
    def update(self, request, pk=None):
        language = self.get_user_language()
        exercise = self.get_object()
        if not request.user.is_superuser:
            message = translate_text("You do not have permission to update this exercise.", language)
            return Response({"error": message}, status=403)
        serializer = self.get_serializer(exercise, data=request.data)
        if serializer.is_valid():
            serializer.save()
            message = translate_text("Exercise updated successfully", language)
            return Response({"message": message, "exercise": serializer.data})
        return Response(serializer.errors, status=400)

    @swagger_auto_schema(tags=['Exercises'], operation_description=_("Partially update an exercise by ID"))
    def partial_update(self, request, pk=None):
        language = self.get_user_language()
        exercise = self.get_object()
        if not request.user.is_superuser:
            message = translate_text("You do not have permission to partially update this exercise.", language)
            return Response({"error": message}, status=403)
        serializer = self.get_serializer(exercise, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            message = translate_text("Exercise partially updated successfully", language)
            return Response({"message": message, "exercise": serializer.data})
        return Response(serializer.errors, status=400)

    @swagger_auto_schema(tags=['Exercises'], operation_description=_("Delete an exercise"))
    def destroy(self, request, pk=None):
        language = self.get_user_language()
        if not request.user.is_superuser:
            message = translate_text("You do not have permission to delete this exercise.", language)
            return Response({"error": message}, status=403)
        exercise = self.get_object()
        exercise.delete()
        message = translate_text("Exercise deleted successfully", language)
        return Response({"message": message})


class UserProgramViewSet(viewsets.ModelViewSet):
    queryset = UserProgram.objects.all()
    serializer_class = UserProgramSerializer
    permission_classes = [IsAuthenticated]

    def get_user_language(self):
        return getattr(self.request.user, 'language', 'en')

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return UserProgram.objects.none()
        return UserProgram.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        tags=['User Programs'],
        operation_description=_("List all user programs for the authenticated user")
    )
    def list(self, request):
        queryset = self.get_queryset().filter(user=request.user)
        serializer = self.get_serializer(queryset, many=True)
        return Response({"user_programs": serializer.data})

    @swagger_auto_schema(
        tags=['User Programs'],
        operation_description=_("Retrieve user program by ID")
    )
    def retrieve(self, request, pk=None):
        user_program = self.get_object()
        serializer = self.get_serializer(user_program)
        return Response({"user_program": serializer.data})

    @swagger_auto_schema(
        tags=['User Programs'],
        operation_description=_("Create a new user program"),
        request_body=UserProgramCreateSerializer,
        responses={201: openapi.Response(description="User program created", schema=UserProgramSerializer)}
    )
    def create(self, request):
        language = self.get_user_language()
        program_id = request.data.get("program")
        if not program_id:
            return Response({"error": "program_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            program = Program.objects.get(id=program_id, is_active=True)
        except Program.DoesNotExist:
            return Response({"error": "Invalid or inactive program_id."}, status=status.HTTP_404_NOT_FOUND)
        create_serializer = UserProgramCreateSerializer(data=request.data)
        if create_serializer.is_valid():
            user_program = create_serializer.save(user=request.user, program=program)
            message = "Program selected. Complete payment to access sessions."
            return Response({"message": message, "user_program": create_serializer.data},
                            status=status.HTTP_201_CREATED)
        return Response(create_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['User Programs'],
        operation_description=_("Update a user program by ID")
    )
    def update(self, request, pk=None):
        language = self.get_user_language()
        user_program = self.get_object()
        if user_program.user != request.user:
            message = translate_text("You do not have permission to update this user program.", language)
            return Response({"error": message}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(user_program, data=request.data, partial=True)
        if serializer.is_valid():
            was_unpaid = not user_program.is_paid
            is_now_paid = serializer.validated_data.get("is_paid", user_program.is_paid)
            new_end_date = serializer.validated_data.get("end_date")
            if new_end_date and new_end_date > user_program.end_date:
                user_program.end_date = new_end_date
            serializer.save()
            if was_unpaid and is_now_paid:
                message = translate_text("Subscription renewed successfully.", language)
            else:
                message = translate_text("User program updated successfully", language)
            return Response({"message": message, "user_program": serializer.data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['User Programs'],
        operation_description=_("Partially update a user program by ID")
    )
    def partial_update(self, request, pk=None):
        language = self.get_user_language()
        user_program = self.get_object()
        if user_program.user != request.user:
            message = translate_text("You do not have permission to partially update this user program.", language)
            return Response({"error": message}, status=403)
        serializer = self.get_serializer(user_program, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            message = translate_text("User program partially updated successfully", language)
            return Response({"message": message, "user_program": serializer.data})
        return Response(serializer.errors, status=400)

    @swagger_auto_schema(
        tags=['User Programs'],
        operation_description=_("Delete a user program")
    )
    def destroy(self, request, pk=None):
        language = self.get_user_language()
        user_program = self.get_object()
        if user_program.user != request.user:
            message = translate_text("You do not have permission to delete this user program.", language)
            return Response({"error": message}, status=403)
        user_program.delete()
        message = translate_text("User program deleted successfully", language)
        return Response({"message": message})


class UserFullProgramDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user_program = UserProgram.objects.filter(user=request.user, is_active=True).first()
            if not user_program:
                return Response({"error": "Foydalanuvchining faol dasturi topilmadi."},
                                status=status.HTTP_404_NOT_FOUND)
            if not user_program.is_subscription_active():
                return Response({"error": "Your subscription has ended. Please renew."}, status=403)
            sessions = Session.objects.filter(program=user_program.program).prefetch_related(
                'exercises', 'meals__preparations'
            )
            response_data = {
                "program": {
                    "id": user_program.program.id,
                    "goal": user_program.program.program_goal,
                    "progress": user_program.progress,
                    "total_sessions": user_program.program.total_sessions,
                    "is_active": user_program.is_active,
                    "start_date": user_program.start_date,
                    "end_date": user_program.end_date,
                },
                "sessions": [
                    {
                        "id": session.id,
                        "session_number": session.session_number,
                        "calories_burned": session.calories_burned,
                        "is_completed": self._is_session_completed(request.user, session),
                        "exercises": [
                            {
                                "id": exercise.id,
                                "name": exercise.name,
                                "description": exercise.description,
                                "difficulty_level": exercise.difficulty_level,
                                "target_muscle": exercise.target_muscle,
                                "video_url": exercise.video_url,
                            }
                            for exercise in session.exercises.all()
                        ],
                        "meals": [
                            {
                                "id": meal.id,
                                "type": meal.meal_type,
                                "food_name": meal.food_name,
                                "calories": meal.calories,
                                "water_content": meal.water_content,
                                "preparation_time": meal.preparation_time,
                                "is_completed": self._is_meal_completed(request.user, session, meal),
                                "preparations": [
                                    {
                                        "id": preparation.id,
                                        "name": preparation.name,
                                        "description": preparation.description,
                                        "preparation_time": preparation.preparation_time,
                                    }
                                    for preparation in meal.preparations.all()
                                ],
                            }
                            for meal in session.meals.all()
                        ],
                    }
                    for session in sessions
                ],
            }
            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Xato yuz berdi: {str(e)}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _is_session_completed(self, user, session):
        completion = SessionCompletion.objects.filter(user=user, session=session).first()
        return completion.is_completed if completion else False

    def _is_meal_completed(self, user, session, meal):
        meal_completion = MealCompletion.objects.filter(user=user, session=session, meal=meal).first()
        return meal_completion.is_completed if meal_completion else False


class ProgressView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "type": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["daily", "weekly", "monthly"],
                    description="Progress type (daily or weekly, or monthly)"
                ),
                "date": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="date",
                    description="Date for the progress query (format: YYYY-MM-DD)"
                ),
            },
            required=["type", "date"],
        ),
        responses={
            200: openapi.Response(
                description="Progress response",
                examples={
                    "application/json": {
                        "date": "2024-11-23",
                        "completed_sessions_count": 2,
                        "missed_sessions_count": 1,
                        "total_calories_burned": 350.5,
                        "completed_meals_count": 3,
                        "missed_meals_count": 0,
                        "calories_gained": 1200.0,
                        "sessions": [
                            {"id": 1, "calories_burned": 200.5, "status": "completed"},
                            {"id": 2, "calories_burned": 150.0, "status": "completed"},
                            {"id": 3, "calories_burned": 0.0, "status": "missed"}
                        ],
                        "meals": [
                            {"id": 1, "calories": 500.0, "status": "completed"},
                            {"id": 2, "calories": 700.0, "status": "completed"},
                            {"id": 3, "calories": 0.0, "status": "missed"}
                        ]
                    }
                },
            ),
            400: "Invalid request",
            404: "No active program",
        },
    )
    def post(self, request):
        query_type = request.data.get("type")
        date_str = request.data.get("date")
        if query_type not in ["daily", "weekly", "monthly"]:
            return Response({"error": "Invalid type. Expected 'daily' or 'weekly' or 'monthly'."},
                            status=400)
        try:
            date = parse_date(date_str)
            if not date:
                raise ValueError
        except ValueError:
            return Response({"error": "Invalid date format. Expected 'YYYY-MM-DD'."},
                            status=400)
        if query_type == "daily":
            progress = self.calculate_daily_progress(request.user, date)
        elif query_type == "weekly":
            progress = self.calculate_weekly_progress(request.user, date)
        elif query_type == "monthly":
            progress = self.calculate_monthly_progress(request.user, date)
        return Response(progress, status=200)

    def calculate_daily_progress(self, user, date):
        completed_sessions = SessionCompletion.objects.filter(user=user, session_date=date)
        sessions = [{
            "id": session.session.id,
            "calories_burned": float(session.session.block.calories_burned) if session.is_completed and hasattr(session.session, 'block') else 0.0,
            "status": "completed" if session.is_completed else "missed"
        } for session in completed_sessions]
        completed_meals = MealCompletion.objects.filter(user=user, meal_date=date)
        meals = [{
            "id": meal.meal.id,
            "calories": float(meal.meal.calories) if meal.is_completed else 0.0,
            "status": "completed" if meal.is_completed else "missed"
        } for meal in completed_meals]
        total_calories_burned = sum(s["calories_burned"] for s in sessions)
        total_calories_gained = sum(m["calories"] for m in meals)
        return {
            "date": str(date),
            "completed_sessions_count": sum(1 for s in sessions if s["status"] == "completed"),
            "missed_sessions_count": sum(1 for s in sessions if s["status"] == "missed"),
            "total_calories_burned": total_calories_burned,
            "completed_meals_count": sum(1 for m in meals if m["status"] == "completed"),
            "missed_meals_count": sum(1 for m in meals if m["status"] == "missed"),
            "calories_gained": total_calories_gained,
            "sessions": sessions,
            "meals": meals,
        }

    def calculate_weekly_progress(self, user, date):
        week_start = date - timedelta(days=date.weekday())
        week_end = week_start + timedelta(days=6)
        completed_sessions = SessionCompletion.objects.filter(user=user, session_date__range=(week_start, week_end))
        sessions = [{
            "id": session.session.id,
            "calories_burned": float(session.session.block.calories_burned) if session.is_completed and hasattr(session.session, 'block') else 0.0,
            "status": "completed" if session.is_completed else "missed"
        } for session in completed_sessions]
        completed_meals = MealCompletion.objects.filter(user=user, meal_date__range=(week_start, week_end))
        meals = [{
            "id": meal.meal.id,
            "calories": float(meal.meal.calories) if meal.is_completed else 0.0,
            "status": "completed" if meal.is_completed else "missed"
        } for meal in completed_meals]
        total_calories_burned = sum(s["calories_burned"] for s in sessions)
        total_calories_gained = sum(m["calories"] for m in meals)
        return {
            "week_start_date": str(week_start),
            "week_end_date": str(week_end),
            "completed_sessions_count": sum(1 for s in sessions if s["status"] == "completed"),
            "missed_sessions_count": sum(1 for s in sessions if s["status"] == "missed"),
            "total_calories_burned": total_calories_burned,
            "completed_meals_count": sum(1 for m in meals if m["status"] == "completed"),
            "missed_meals_count": sum(1 for m in meals if m["status"] == "missed"),
            "calories_gained": total_calories_gained,
            "sessions": sessions,
            "meals": meals,
        }

    def calculate_monthly_progress(self, user, date):
        month_start = date.replace(day=1)
        next_month = month_start.replace(day=28) + timedelta(days=4)
        month_end = next_month - timedelta(days=next_month.day)
        completed_sessions = SessionCompletion.objects.filter(user=user, session_date__range=(month_start, month_end))
        sessions = [{
            "id": session.session.id,
            "calories_burned": float(session.session.block.calories_burned) if session.is_completed and hasattr(session.session, 'block') else 0.0,
            "status": "completed" if session.is_completed else "missed"
        } for session in completed_sessions]
        completed_meals = MealCompletion.objects.filter(user=user, meal_date__range=(month_start, month_end))
        meals = [{
            "id": meal.meal.id,
            "calories": float(meal.meal.calories) if meal.is_completed else 0.0,
            "status": "completed" if meal.is_completed else "missed"
        } for meal in completed_meals]
        total_calories_burned = sum(s["calories_burned"] for s in sessions)
        total_calories_gained = sum(m["calories"] for m in meals)
        return {
            "month_start_date": str(month_start),
            "month_end_date": str(month_end),
            "completed_sessions_count": sum(1 for s in sessions if s["status"] == "completed"),
            "missed_sessions_count": sum(1 for s in sessions if s["status"] == "missed"),
            "total_calories_burned": total_calories_burned,
            "completed_meals_count": sum(1 for m in meals if m["status"] == "completed"),
            "missed_meals_count": sum(1 for m in meals if m["status"] == "missed"),
            "calories_gained": total_calories_gained,
            "sessions": sessions,
            "meals": meals,
        }
