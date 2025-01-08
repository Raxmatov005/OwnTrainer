from rest_framework import viewsets,status
from users_app.models import *
from exercise.serializers import *
from django.utils.translation import gettext_lazy as _
from drf_yasg.utils import swagger_auto_schema
from exercise.permissions import IsAdminOrReadOnly
from rest_framework.permissions import IsAuthenticated
from users_app.models import translate_text
from rest_framework.views import APIView
from datetime import timedelta
from threading import Timer
from drf_yasg import openapi
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils.timezone import now
from django.utils.translation import gettext as _
from .serializers import SessionSerializer
from django.utils.dateparse import parse_date
from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser, JSONParser, FormParser

class ProgramViewSet(viewsets.ModelViewSet):
    queryset = Program.objects.all()
    serializer_class = ProgramSerializer
    permission_classes = [IsAuthenticated,IsAdminOrReadOnly]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        language = self.request.query_params.get('lang', 'en')
        context['language'] = language
        return context

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Program.objects.all()
        # Filter programs by 'is_active' and match the user's goal
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
            program = serializer.save()
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
    queryset = Session.objects.all()
    serializer_class = SessionSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]


    def get_user_language(self,request):
        return getattr(request.user, 'language', 'en')



    def get_serializer(self, *args, **kwargs):
        # Override to avoid using any serializer for the `reset_today_session` action
        if self.action == 'reset_today_session':
            return None  # No serializer required for this action
        return super().get_serializer(*args, **kwargs)



    @action(detail=False, methods=['get'], url_path='by-session-number')
    @swagger_auto_schema(
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
            200: SessionSerializer(),
            400: "session_number is required.",
            404: "Session not found or no active program."
        }
    )
    def get_by_session_number(self, request):
        user_program = UserProgram.objects.filter(user=request.user, is_active=True).first()

        if not user_program:
            return Response(
                {"error": "No active program found for the logged-in user."},
                status=status.HTTP_404_NOT_FOUND,
            )

        session_number = request.query_params.get('session_number')
        if not session_number:
            return Response(
                {"error": "session_number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            session = Session.objects.get(program=user_program.program, session_number=session_number)
        except Session.DoesNotExist:
            return Response(
                {"error": "Session not found for the given session_number in the user's program."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.get_serializer(session)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(tags=['Sessions'],
                         operation_description=_("List completed sessions and the next upcoming session for the user"))
    def list(self, request):
        print(f"Request User: {request.user}")
        print(f"Is Authenticated: {request.user.is_authenticated}")
        print(f"Is Superuser: {request.user.is_superuser}")
        print(request.user.is_staff)
        print(request.user.is_superuser)
        if request.user.is_staff:  # Admin user
            # Fetch all sessions for admin
            sessions = Session.objects.all().order_by('session_number')
            serializer = self.get_serializer(sessions, many=True)
            return Response({"sessions": serializer.data}, status=status.HTTP_200_OK)
        else:  # Regular user
            # Check if the user has an active program
            user_program = UserProgram.objects.filter(user=request.user, is_active=True).first()
            if not user_program:
                return Response(
                    {"error": _("No active program found for the user.")},
                    status=status.HTTP_404_NOT_FOUND
                )



            # Fetch the next upcoming session
            next_upcoming_session = SessionCompletion.objects.filter(
                user=request.user,
                is_completed=False,
                session_date__gte=now().date()
            ).order_by('session_date').first()

            # Collect session IDs to display
            session_ids = []
            if next_upcoming_session:

            # if next_upcoming_session:
                session_ids.append(next_upcoming_session.session_id)

            # Filter sessions based on the collected session IDs
            sessions = Session.objects.filter(id__in=session_ids).order_by('session_number')

            # Serialize and return the filtered sessions
            serializer = self.get_serializer(sessions, many=True)
            return Response({"sessions": serializer.data}, status=status.HTTP_200_OK)


    @swagger_auto_schema(tags=['Sessions'], operation_description=_("Retrieve session by ID"))
    def retrieve(self, request, pk=None):
        session = self.get_object()
        serializer = self.get_serializer(session)
        return Response({"session": serializer.data})






    @swagger_auto_schema(tags=['Sessions'], operation_description=_("Update a session by ID"))
    def update(self, request, pk=None):
        language = self.get_user_language()
        session = self.get_object()
        if not request.user.is_superuser:
            message = _("You do not have permission to update this session.")
            return Response({"error": message}, status=403)
        serializer = self.get_serializer(session, data=request.data)
        if serializer.is_valid():
            serializer.save()
            message = _("Session updated successfully")
            return Response({"message": message, "session": serializer.data})
        return Response(serializer.errors, status=400)

    @swagger_auto_schema(tags=['Sessions'], operation_description=_("Partially update a session by ID"))
    def partial_update(self, request, pk=None):
        language = self.get_user_language()
        session = self.get_object()
        if not request.user.is_superuser:
            message = _("You do not have permission to partially update this session.")
            return Response({"error": message}, status=403)
        serializer = self.get_serializer(session, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            message = _("Session partially updated successfully")
            return Response({"message": message, "session": serializer.data})
        return Response(serializer.errors, status=400)
 
    @swagger_auto_schema(tags=['Sessions'], operation_description=_("Create a new session for a program"))
    def create(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return Response({"error": _("You do not have permission to create a session.")}, status=status.HTTP_403_FORBIDDEN)

        program_id = request.data.get('program')
        if not program_id:
            return Response({"error": _("Program ID is required to create a session.")}, status=status.HTTP_400_BAD_REQUEST)

        try:
            program = Program.objects.get(id=program_id)
        except Program.DoesNotExist:
            return Response({"error": _("Specified program does not exist.")}, status=status.HTTP_404_NOT_FOUND)

        # Convert exercises and meals to lists of integers
        exercises = request.data.get('exercises', [])
        meals = request.data.get('meals', [])

        if isinstance(exercises, str):
            exercises = exercises.split(',')
        if isinstance(meals, str):
            meals = meals.split(',')

        request.data._mutable = True  # Allow modification of QueryDict (for testing purposes)
        request.data.setlist('exercises', exercises)
        request.data.setlist('meals', meals)

        # Add cover image if present
        cover_image = request.FILES.get('cover_image')
        if cover_image:
            request.data['cover_image'] = cover_image

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": _("Session created successfully"), "session": serializer.data},
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST) 
    @swagger_auto_schema(tags=['Sessions'], operation_description=_("Delete a session"))
    def destroy(self, request, pk=None):
        language = self.get_user_language()
        if not request.user.is_superuser:
            message = _("You do not have permission to delete this session.")
            return Response({"error": message}, status=403)
        session = self.get_object()
        session.delete()
        message = _("Session deleted successfully")
        return Response({"message": message})



    @action(detail=False, methods=['post'], url_path='reset-today-session', permission_classes=[IsAuthenticated])
    @swagger_auto_schema(
        operation_description=_("Reset today's session for the logged-in user"),
        responses={
            200: "Today's session has been reset successfully.",
            404: "No session found for today."
        },
        request_body=None
         )
    def reset_today_session(self, request):
        """
        Custom endpoint to reset today's session for the logged-in user.
        """
        # Fetch today's session for the user
        today_session = SessionCompletion.objects.filter(
            user=request.user,
            session_date=now().date()
        ).first()

        if not today_session:
            return Response(
                {"error": _("No session found for today.")},
                status=status.HTTP_404_NOT_FOUND
            )

        # Reset session completion status
        today_session.is_completed = False
        today_session.completion_date = None
        today_session.save()

        return Response(
            {"message": _("Today's session has been reset successfully.")},
            status=status.HTTP_200_OK
        )


class ExerciseViewSet(viewsets.ModelViewSet):
    queryset = Exercise.objects.all()
    serializer_class = ExerciseSerializer
    permission_classes = [IsAuthenticated,IsAdminOrReadOnly]

    def get_user_language(self):
        return getattr(self.request.user, 'language', 'en')

    @swagger_auto_schema(tags=['Exercises'], operation_description=_("List exercises for a specific session"))
    def list(self, request):
        if not request.user.is_authenticated:
            return Response({"error": "Authentication credentials were not provided."}, status=403)
        session_id = request.query_params.get('session_id')  # `session_id` parametrini oladi
        queryset = self.get_queryset().filter(sessions__id=session_id) if session_id else self.get_queryset()
        if not request.user.is_superuser:
            queryset = queryset.filter(
                sessions__program__is_active=True)  # Foydalanuvchi uchun faqat aktiv dasturlarni ko'rsatish
        serializer = self.get_serializer(queryset, many=True)
        return Response({"exercises": serializer.data})


    @swagger_auto_schema(
        tags=['Exercises'],
        operation_description=_("Retrieve exercises by category ID"),
        manual_parameters=[
            openapi.Parameter(
                'category_id', openapi.IN_QUERY, 
                description="ID of the category to filter exercises by",
                type=openapi.TYPE_INTEGER,
                required=True
            )
        ],
        responses={
            200: openapi.Response(
                description="A list of exercises in the specified category",
                schema=ExerciseSerializer(many=True)
            ),
            400: "Category ID is required",
            404: "No exercises found for the given category"
        }
    )
    @action(detail=False, methods=['get'], url_path='by-category')
    def by_category(self, request):
        """
        Custom endpoint to get exercises filtered by category ID.
        """
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


class WorkoutCategoryViewSet(viewsets.ModelViewSet):
    queryset = WorkoutCategory.objects.all()
    serializer_class = WorkoutCategorySerializer
    permission_classes = [IsAuthenticated,IsAdminOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]


    def get_user_language(self):
        # Assuming the user's preferred language is stored in the User model
        return self.request.user.language if hasattr(self.request.user, 'language') else 'en'

    @swagger_auto_schema(tags=['Workout Categories'], operation_description=_("List all workout categories"))
    def list(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({"workout_categories": serializer.data})

    @swagger_auto_schema(tags=['Workout Categories'], operation_description=_("Retrieve workout category by ID"))
    def retrieve(self, request, pk=None):
        workout_category = self.get_object()
        serializer = self.get_serializer(workout_category)
        return Response({"workout_category": serializer.data})

    @swagger_auto_schema(tags=['Workout Categories'], operation_description=_("Create a new workout category"))
    def create(self, request, *args, **kwargs):
        language = self.get_user_language()
        if not request.user.is_superuser:
            message = translate_text("You do not have permission to create a workout category.", language)
            return Response({"error": message}, status=403)
        
        # Parse the request for form data and files
        data = request.data.copy()
        workout_image = request.FILES.get('workout_image')
        if workout_image:
            data['workout_image'] = workout_image

        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            serializer.save()
            message = translate_text("Workout category created successfully", language)
            return Response({"message": message, "workout_category": serializer.data}, status=201)
        return Response(serializer.errors, status=400)
    @swagger_auto_schema(tags=['Workout Categories'], operation_description=_("Update a workout category by ID"))
    def update(self, request, pk=None):
        language = self.get_user_language()
        workout_category = self.get_object()
        if not request.user.is_superuser:
            message = translate_text("You do not have permission to update this workout category.", language)
            return Response({"error": message}, status=403)
        serializer = self.get_serializer(workout_category, data=request.data)
        if serializer.is_valid():
            serializer.save()
            message = translate_text("Workout category updated successfully", language)
            return Response({"message": message, "workout_category": serializer.data})
        return Response(serializer.errors, status=400)

    @swagger_auto_schema(tags=['Workout Categories'], operation_description=_("Partially update a workout category by ID"))
    def partial_update(self, request, pk=None):
        language = self.get_user_language()
        workout_category = self.get_object()
        if not request.user.is_superuser:
            message = translate_text("You do not have permission to partially update this workout category.", language)
            return Response({"error": message}, status=403)
        serializer = self.get_serializer(workout_category, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            message = translate_text("Workout category updated successfully", language)
            return Response({"message": message, "workout_category": serializer.data})
        return Response(serializer.errors, status=400)

    @swagger_auto_schema(tags=['Workout Categories'], operation_description=_("Delete a workout category"))
    def destroy(self, request, pk=None):
        language = self.get_user_language()
        if not request.user.is_superuser:
            message = translate_text("You do not have permission to delete this workout category.", language)
            return Response({"error": message}, status=403)
        workout_category = self.get_object()
        workout_category.delete()
        message = translate_text("Workout category deleted successfully", language)
        return Response({"message": message})


class UserProgramViewSet(viewsets.ModelViewSet):
    queryset = UserProgram.objects.all()
    serializer_class = UserProgramSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    def get_user_language(self):
        return getattr(self.request.user, 'language', 'en')

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return UserProgram.objects.none()
        return UserProgram.objects.filter(user=self.request.user)

    @swagger_auto_schema(tags=['User Programs'], operation_description=_("List all user programs for the authenticated user"))
    def list(self, request):
        queryset = self.get_queryset().filter(user=request.user)
        serializer = self.get_serializer(queryset, many=True)
        return Response({"user_programs": serializer.data})

    @swagger_auto_schema(tags=['User Programs'], operation_description=_("Retrieve user program by ID"))
    def retrieve(self, request, pk=None):
        user_program = self.get_object()
        serializer = self.get_serializer(user_program)
        return Response({"user_program": serializer.data})

    @swagger_auto_schema(tags=['User Programs'], operation_description=_("Create a new user program"))
    def create(self, request):
        language = self.get_user_language()
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            message = translate_text("User program created successfully", language)
            return Response({"message": message, "user_program": serializer.data})
        return Response(serializer.errors, status=400)

    @swagger_auto_schema(tags=['User Programs'], operation_description=_("Update a user program by ID"))
    def update(self, request, pk=None):
        language = self.get_user_language()
        user_program = self.get_object()
        if user_program.user != request.user:
            message = translate_text("You do not have permission to update this user program.", language)
            return Response({"error": message}, status=403)
        serializer = self.get_serializer(user_program, data=request.data)
        if serializer.is_valid():
            serializer.save()
            message = translate_text("User program updated successfully", language)
            return Response({"message": message, "user_program": serializer.data})
        return Response(serializer.errors, status=400)

    @swagger_auto_schema(tags=['User Programs'], operation_description=_("Partially update a user program by ID"))
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

    @swagger_auto_schema(tags=['User Programs'], operation_description=_("Delete a user program"))
    def destroy(self, request, pk=None):
        language = self.get_user_language()
        user_program = self.get_object()
        if user_program.user != request.user:
            message = translate_text("You do not have permission to delete this user program.", language)
            return Response({"error": message}, status=403)
        user_program.delete()
        message = translate_text("User program deleted successfully", language)
        return Response({"message": message})


class UserProgramAllViewSet(APIView):
    queryset = UserProgram.objects.all()
    serializer_class = UserProgramSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    def get_user_language(self):
        return getattr(self.request.user, 'language', 'en')

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return UserProgram.objects.none()
        return UserProgram.objects.all()

    @swagger_auto_schema(tags=['User Programs All'], operation_description=_("List all user programs for the authenticated user"))
    def list(self, request):
        queryset = self.get_queryset().filter(user=request.user)
        serializer = self.get_serializer(queryset, many=True)
        return Response({"user_programs": serializer.data})


class UserFullProgramDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Fetch the user's active program
            user_program = UserProgram.objects.filter(user=request.user, is_active=True).first()
            if not user_program:
                return Response(
                    {"error": "Foydalanuvchining faol dasturi topilmadi."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Fetch all sessions for the program
            sessions = Session.objects.filter(program=user_program.program).prefetch_related(
                'exercises', 'meals__preparations'
            )

            # Prepare response data
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
            return Response(
                {"error": f"Xato yuz berdi: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _is_session_completed(self, user, session):
        """Helper method to check if a session is completed."""
        completion = SessionCompletion.objects.filter(user=user, session=session).first()
        return completion.is_completed if completion else False

    def _is_meal_completed(self, user, session, meal):
        """Helper method to check if a meal is completed."""
        meal_completion = MealCompletion.objects.filter(
            user=user, session=session, meal=meal
        ).first()
        return meal_completion.is_completed if meal_completion else False


class StartSessionView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=['Sessions'],
        operation_description="Start a session with a 10-second preparation period.",
        request_body=SessionStartSerializer,
        responses={
            200: openapi.Response(
                description="Session start information",
                examples={
                    "application/json": {
                        "message": "Session will start after a 10-second preparation period.",
                        "preparation_ends_at": "2024-12-13T16:30:10Z",
                        "estimated_end_time": "2024-12-13T17:00:10Z"
                    }
                }
            ),
            400: "Bad Request - Missing or invalid session_id.",
            404: "Not Found - Session not found or not assigned to user."
        }
    )
    def post(self, request):
        serializer = SessionStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session_id = serializer.validated_data['session_id']
        session_completion = SessionCompletion.objects.filter(user=request.user, session_id=session_id).first()

        if not session_completion:
            return Response({"error": _("Session not found or not assigned to user.")}, status=404)

        if session_completion.is_completed:
            return Response({"error": _("Session already completed.")}, status=400)

        # Add 10-second preparation time
        preparation_period = timedelta(seconds=10)

        session = session_completion.session
        exercise_duration = timedelta(
            hours=session.session_time.hour if session.session_time else 0,
            minutes=session.session_time.minute if session.session_time else 0,
            seconds=session.session_time.second if session.session_time else 0
        )

        session_start_time = now() + preparation_period
        session_end_time = session_start_time + exercise_duration

        def mark_session_complete():
            session_completion.is_completed = True
            session_completion.completion_date = now()
            session_completion.save()

        # Schedule the completion after prep time + exercise duration
        Timer((preparation_period + exercise_duration).total_seconds(), mark_session_complete).start()

        return Response({
            "message": _("Session will start after a 10-second preparation period."),
            "preparation_ends_at": session_start_time,
            "estimated_end_time": session_end_time
        }, status=200)


class ProgressView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "type": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["daily", "weekly"],
                    description="Progress type (daily or weekly)"
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

        # Validate query_type
        if query_type not in ["daily", "weekly"]:
            return Response(
                {"error": "Invalid type. Expected 'daily' or 'weekly'."},
                status=400,
            )

        # Validate and parse date
        try:
            date = parse_date(date_str)
            if not date:
                raise ValueError
        except ValueError:
            return Response(
                {"error": "Invalid date format. Expected 'YYYY-MM-DD'."},
                status=400,
            )

        # Calculate progress based on query_type
        if query_type == "daily":
            progress = self.calculate_daily_progress(request.user, date)
        elif query_type == "weekly":
            progress = self.calculate_weekly_progress(request.user, date)

        return Response(progress, status=200)

    def calculate_daily_progress(self, user, date):
        completed_sessions = SessionCompletion.objects.filter(
            user=user,
            session_date=date,
        )
        sessions = [
            {
                "id": session.session.id,
                "calories_burned": float(session.session.calories_burned) if session.is_completed else 0.0,
                "status": "completed" if session.is_completed else "missed"
            }
            for session in completed_sessions
        ]

        completed_meals = MealCompletion.objects.filter(
            user=user,
            meal_date=date,
        )
        meals = [
            {
                "id": meal.meal.id,
                "calories": float(meal.meal.calories) if meal.is_completed else 0.0,
                "status": "completed" if meal.is_completed else "missed"
            }
            for meal in completed_meals
        ]

        total_calories_burned = sum(session["calories_burned"] for session in sessions)
        total_calories_gained = sum(meal["calories"] for meal in meals)

        return {
            "date": str(date),
            "completed_sessions_count": sum(1 for session in sessions if session["status"] == "completed"),
            "missed_sessions_count": sum(1 for session in sessions if session["status"] == "missed"),
            "total_calories_burned": total_calories_burned,
            "completed_meals_count": sum(1 for meal in meals if meal["status"] == "completed"),
            "missed_meals_count": sum(1 for meal in meals if meal["status"] == "missed"),
            "calories_gained": total_calories_gained,
            "sessions": sessions,
            "meals": meals,
        }

    def calculate_weekly_progress(self, user, date):
        week_start = date - timedelta(days=date.weekday())
        week_end = week_start + timedelta(days=6)

        completed_sessions = SessionCompletion.objects.filter(
            user=user,
            session_date__range=(week_start, week_end),
        )
        sessions = [
            {
                "id": session.session.id,
                "calories_burned": float(session.session.calories_burned) if session.is_completed else 0.0,
                "status": "completed" if session.is_completed else "missed"
            }
            for session in completed_sessions
        ]

        completed_meals = MealCompletion.objects.filter(
            user=user,
            meal_date__range=(week_start, week_end),
        )
        meals = [
            {
                "id": meal.meal.id,
                "calories": float(meal.meal.calories) if meal.is_completed else 0.0,
                "status": "completed" if meal.is_completed else "missed"
            }
            for meal in completed_meals
        ]

        total_calories_burned = sum(session["calories_burned"] for session in sessions)
        total_calories_gained = sum(meal["calories"] for meal in meals)

        return {
            "week_start_date": str(week_start),
            "week_end_date": str(week_end),
            "completed_sessions_count": sum(1 for session in sessions if session["status"] == "completed"),
            "missed_sessions_count": sum(1 for session in sessions if session["status"] == "missed"),
            "total_calories_burned": total_calories_burned,
            "completed_meals_count": sum(1 for meal in meals if meal["status"] == "completed"),
            "missed_meals_count": sum(1 for meal in meals if meal["status"] == "missed"),
            "calories_gained": total_calories_gained,
            "sessions": sessions,
            "meals": meals,
        }


class ExerciseStartView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=['Exercises'],
        operation_description="Start an exercise for the given session and exercise ID.",
        request_body=ExerciseStartSerializer,
        responses={
            200: openapi.Response(
                description="Exercise started successfully.",
                examples={
                    "application/json": {
                        "session_id": 1,
                        "exercise_id": 2,
                        "start_time": "2024-06-13T10:00:10Z",
                        "end_time": "2024-06-13T10:30:10Z",
                        "message": "Exercise started successfully. Countdown begins."
                    }
                }
            ),
            400: "Bad Request - Validation Error",
            404: "Exercise not found for this session."
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = ExerciseStartSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            data = serializer.save()
            return Response(data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DailySessionCompletionView(APIView):
    """
    Retrieve session completion details, including meals, by session ID for a user.
    """
    def get(self, request, session_id):
        # Foydalanuvchi uchun SessionCompletion-ni tekshirish
        session_completion = get_object_or_404(
            SessionCompletion, session__id=session_id, user=request.user
        )

        # Serializatsiya qilish
        serializer = DailySessionCompletionSerializer(session_completion, context={'request': request})

        # Ma'lumotlarni qaytarish
        return Response(serializer.data, status=status.HTTP_200_OK)
