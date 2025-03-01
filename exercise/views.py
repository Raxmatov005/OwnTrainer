from rest_framework import viewsets, status
from users_app.models import *
from exercise.serializers import *
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
from .subscribtion_check import IsSubscriptionActive

# ProgramViewSet
class ProgramViewSet(viewsets.ModelViewSet):
    queryset = Program.objects.all()
    serializer_class = ProgramSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    parser_classes = [JSONParser]

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

    @swagger_auto_schema(
        tags=['Programs'],
        operation_description=_("List all active programs"),
        responses={200: ProgramSerializer(many=True)}
    )
    def list(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({"programs": serializer.data}, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=['Programs'],
        operation_description=_("Retrieve a program by ID"),
        responses={200: ProgramSerializer()}
    )
    def retrieve(self, request, pk=None):
        program = self.get_object()
        serializer = self.get_serializer(program)
        return Response({"program": serializer.data}, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        tags=['Programs'],
        operation_description=_("Create a new program"),
        request_body=ProgramSerializer,
        responses={201: ProgramSerializer()}
    )
    def create(self, request):
        """ Remove `total_sessions` from input data since it's now auto-calculated. """
        request_data = request.data.copy()  # Make a copy to modify safely
        request_data.pop('total_sessions', None)  # Ensure it's not included

        serializer = self.get_serializer(data=request_data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": _("Program created successfully"), "program": serializer.data},
                            status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['Programs'],
        operation_description=_("Update a program by ID"),
        request_body=ProgramSerializer,
        responses={200: ProgramSerializer()}
    )
    def update(self, request, pk=None):
        """ Ensure `total_sessions` is not passed in update requests. """
        request_data = request.data.copy()
        request_data.pop('total_sessions', None)

        program = self.get_object()
        serializer = self.get_serializer(program, data=request_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": _("Program updated successfully"), "program": serializer.data},
                            status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    @swagger_auto_schema(
        tags=['Programs'],
        operation_description=_("Partially update a program by ID"),
        request_body=ProgramSerializer,
        responses={200: ProgramSerializer()}
    )
    def partial_update(self, request, pk=None):
        program = self.get_object()
        serializer = self.get_serializer(program, data=request.data, partial=True)
        language = getattr(request.user, 'language', 'en')
        if serializer.is_valid():
            serializer.save()
            message = translate_text("Program partially updated successfully", language)
            return Response({"message": message, "program": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['Programs'],
        operation_description=_("Delete a program"),
        responses={204: "No Content"}
    )
    def destroy(self, request, pk=None):
        if not request.user.is_superuser:
            language = getattr(request.user, 'language', 'en')
            message = translate_text("You do not have permission to delete a program.", language)
            return Response({"error": message}, status=status.HTTP_403_FORBIDDEN)
        program = self.get_object()
        program.delete()
        language = getattr(request.user, 'language', 'en')
        message = translate_text("Program deleted successfully", language)
        return Response({"message": message}, status=status.HTTP_204_NO_CONTENT)

# SessionViewSet with nested ExerciseBlock
class SessionViewSet(viewsets.ModelViewSet):
    queryset = Session.objects.all()
    serializer_class = SessionPKSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        language = self.request.query_params.get('lang', 'en')
        context['language'] = language
        return context

    @swagger_auto_schema(
        tags=['Sessions'],
        operation_description=_("Create a new session by linking an existing exercise block and meals using their IDs."),
        request_body=SessionPKSerializer,
        responses={201: SessionPKSerializer()}
    )
    def create(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return Response({"error": _("You do not have permission to create a session.")},
                            status=status.HTTP_403_FORBIDDEN)
        program_id = request.data.get('program')
        if not program_id:
            return Response({"error": _("Program ID is required.")}, status=status.HTTP_400_BAD_REQUEST)
        try:
            Program.objects.get(id=program_id)
        except Program.DoesNotExist:
            return Response({"error": _("Specified program does not exist.")}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": _("Session created successfully"),
                "session": serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    @swagger_auto_schema(tags=['Sessions'], operation_description=_("Retrieve session by ID"))
    def retrieve(self, request, pk=None):
        session = self.get_object()
        serializer = self.get_serializer(session)
        return Response({"session": serializer.data}, status=status.HTTP_200_OK)

    @swagger_auto_schema(tags=['Sessions'], operation_description=_("Update a session by ID"))
    def update(self, request, pk=None):
        session = self.get_object()
        if not request.user.is_superuser:
            return Response({"error": _("You do not have permission to update this session.")}, status=403)
        serializer = self.get_serializer(session, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": _("Session updated successfully"), "session": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=['Sessions'], operation_description=_("Partially update a session by ID"))
    def partial_update(self, request, pk=None):
        session = self.get_object()
        if not request.user.is_superuser:
            return Response({"error": _("You do not have permission to partially update this session.")}, status=403)
        serializer = self.get_serializer(session, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": _("Session partially updated successfully"), "session": serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(tags=['Sessions'], operation_description=_("Delete a session"))
    def destroy(self, request, pk=None):
        if not request.user.is_superuser:
            return Response({"error": _("You do not have permission to delete this session.")}, status=403)
        session = self.get_object()
        session.delete()
        return Response({"message": _("Session deleted successfully")}, status=status.HTTP_204_NO_CONTENT)

    @swagger_auto_schema(tags=['Sessions'], operation_description=_("List sessions for the user. Staff sees all sessions."))
    def list(self, request):
        """
        - Admins: Get all sessions.
        - Users: Get only incomplete sessions from their assigned program.
        """
        from users_app.models import UserProgram

        # 🔹 If user is an admin, return all sessions
        if request.user.is_superuser or request.user.is_staff:
            sessions = Session.objects.all().order_by('session_number')
            serializer = self.get_serializer(sessions, many=True)
            return Response({"sessions": serializer.data}, status=status.HTTP_200_OK)

        # 🔹 Check if the user has an active program
        user_program = UserProgram.objects.filter(user=request.user).first()
        if not user_program:
            return Response({"error": _("No active program found for the user.")}, status=404)

        # 🔹 Get the user's incomplete sessions
        incomplete_sc = SessionCompletion.objects.filter(
            user=request.user,
            session__program=user_program.program,
            is_completed=False
        ).select_related('session').order_by('session__session_number')

        if not incomplete_sc.exists():
            return Response({"message": _("You have completed all sessions!")}, status=200)

        # 🔹 Get next session number
        next_sc = incomplete_sc.first()
        next_session_number = next_sc.session.session_number

        # 🔹 Get all incomplete session IDs
        session_ids = [sc.session_id for sc in incomplete_sc]

        # 🔹 Retrieve sessions and mark future ones as locked
        sessions = Session.objects.filter(id__in=session_ids).order_by('session_number')
        data = [
            {**self.get_serializer(s).data, "locked": (s.session_number > next_session_number)}
            for s in sessions
        ]

        return Response({"sessions": data}, status=status.HTTP_200_OK)

    @swagger_auto_schema(tags=['Sessions'], operation_description=_("Retrieve session by session_number"))
    @action(detail=False, methods=['get'], url_path='by-session-number')
    def get_by_session_number(self, request):
        from users_app.models import UserProgram
        user_program = UserProgram.objects.filter(user=request.user, is_active=True).first()
        if not user_program:
            return Response({"error": _("No active program found.")}, status=404)
        session_number = request.query_params.get('session_number')
        if not session_number:
            return Response({"error": "session_number is required."}, status=400)
        try:
            session = Session.objects.get(program=user_program.program, session_number=session_number)
        except Session.DoesNotExist:
            return Response({"error": "Session not found."}, status=404)
        serializer = self.get_serializer(session)
        return Response(serializer.data, status=200)

    @swagger_auto_schema(tags=['Sessions'], operation_description=_("Reset today's session for the user"))
    @action(detail=False, methods=['post'], url_path='reset-today-session')
    def reset_today_session(self, request):
        from users_app.models import SessionCompletion
        today_sc = SessionCompletion.objects.filter(user=request.user, session_date=now().date()).first()
        if not today_sc:
            return Response({"error": _("No session found for today.")}, status=404)
        today_sc.is_completed = False
        today_sc.completion_date = None
        today_sc.save()
        return Response({"message": _("Today's session has been reset successfully.")}, status=200)


class ExerciseBlockViewSet(viewsets.ModelViewSet):
    queryset = ExerciseBlock.objects.all()
    serializer_class = NestedExerciseBlockSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly, IsSubscriptionActive]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return ExerciseBlock.objects.all()

        # Non-admin: only blocks assigned to the user's active program sessions
        from users_app.models import UserProgram, SessionCompletion
        user_program = UserProgram.objects.filter(user=user, is_active=True).first()
        if not user_program or not user_program.is_subscription_active():
            return ExerciseBlock.objects.none()

        user_sessions = SessionCompletion.objects.filter(user=user).values_list('session_id', flat=True)
        return ExerciseBlock.objects.filter(session__id__in=user_sessions).distinct()

    def get_serializer_context(self):
        language = self.request.query_params.get('lang', 'en')
        return {
            **super().get_serializer_context(),
            "language": language,
            "request": self.request
        }

    @swagger_auto_schema(
        operation_description=(
            "Create a new ExerciseBlock with an optional 'block_image' and nested exercises. "
            "Exercises can also have an 'image' field in the actual request, but it's omitted "
            "from the schema to avoid Swagger issues."
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'block_name': openapi.Schema(type=openapi.TYPE_STRING),
                'block_image': openapi.Schema(
                    type=openapi.TYPE_FILE,
                    description="Optional block image"
                ),
                'block_kkal': openapi.Schema(type=openapi.TYPE_STRING),
                'block_water_amount': openapi.Schema(type=openapi.TYPE_STRING),
                'description': openapi.Schema(type=openapi.TYPE_STRING),
                'video_url': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_URI
                ),
                'block_time': openapi.Schema(type=openapi.TYPE_INTEGER),
                'calories_burned': openapi.Schema(type=openapi.TYPE_STRING),
                'exercises': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(
                                type=openapi.TYPE_INTEGER,
                                description="If given, update that existing exercise (not typical on create)."
                            ),
                            'name': openapi.Schema(type=openapi.TYPE_STRING),
                            'exercise_time': openapi.Schema(type=openapi.TYPE_STRING),
                            'description': openapi.Schema(type=openapi.TYPE_STRING),
                            # 'image' omitted from schema (but code still accepts it).
                        }
                    )
                ),
            },
            required=['block_name']
        ),
        responses={
            201: openapi.Response(
                description="ExerciseBlock created",
                schema=NestedExerciseBlockSerializer()
            )
        },
        consumes=['multipart/form-data']
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description=(
            "Update an existing ExerciseBlock. Optionally upload 'block_image'. If 'exercises' is given, "
            "existing IDs get updated, new items get created, unmentioned remain attached."
        ),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'block_name': openapi.Schema(type=openapi.TYPE_STRING),
                'block_image': openapi.Schema(
                    type=openapi.TYPE_FILE,
                    description="New or replacement block image"
                ),
                'block_kkal': openapi.Schema(type=openapi.TYPE_STRING),
                'block_water_amount': openapi.Schema(type=openapi.TYPE_STRING),
                'description': openapi.Schema(type=openapi.TYPE_STRING),
                'video_url': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_URI
                ),
                'block_time': openapi.Schema(type=openapi.TYPE_INTEGER),
                'calories_burned': openapi.Schema(type=openapi.TYPE_STRING),
                'exercises': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Items(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'name': openapi.Schema(type=openapi.TYPE_STRING),
                            'exercise_time': openapi.Schema(type=openapi.TYPE_STRING),
                            'description': openapi.Schema(type=openapi.TYPE_STRING),
                            # 'image' omitted from schema (but code still accepts it).
                        }
                    )
                ),
            }
        ),
        responses={
            200: openapi.Response(
                description="ExerciseBlock updated",
                schema=NestedExerciseBlockSerializer()
            )
        },
        consumes=['multipart/form-data']
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        method='patch',
        operation_description="Upload or replace only the 'block_image' field.",
        consumes=['multipart/form-data'],
        manual_parameters=[
            openapi.Parameter(
                name="block_image",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                description="Upload block image"
            )
        ],
        responses={
            200: openapi.Response(
                description="Block image updated",
                schema=NestedExerciseBlockSerializer()
            )
        }
    )
    @action(detail=True, methods=['patch'], url_path='upload-image', parser_classes=[MultiPartParser, FormParser])
    def upload_image(self, request, pk=None):
        block = self.get_object()
        file_obj = request.FILES.get('block_image')
        if not file_obj:
            return Response({"detail": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        block.block_image = file_obj
        block.save()
        serializer = self.get_serializer(block)
        return Response(serializer.data, status=status.HTTP_200_OK)
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
        responses={200: "Block completed successfully. Session completion checked."}
    )
    def post(self, request):
        block_id = request.data.get("block_id")
        if not block_id or not isinstance(block_id, int):
            return Response({"error": _("Valid block_id is required.")}, status=400)
        block = get_object_or_404(ExerciseBlock.objects.select_related('session'), id=block_id)
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
        session = block.session
        all_blocks = session.blocks.all()
        completed_blocks = all_blocks.filter(completions__user=request.user, completions__is_completed=True)
        if completed_blocks.count() == all_blocks.count():
            from users_app.models import SessionCompletion
            session_completion, _ = SessionCompletion.objects.get_or_create(user=request.user, session=session)
            session_completion.is_completed = True
            session_completion.completion_date = now().date()
            session_completion.save()
            return Response({"message": _("Block completed. Session is now completed.")}, status=200)
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
            return Response({"error": _("Authentication credentials were not provided.")}, status=403)
        session_id = request.query_params.get('session_id')
        if session_id:
            try:
                session_id = int(session_id)
            except ValueError:
                return Response({"error": _("Invalid session ID.")}, status=400)
            queryset = self.get_queryset().filter(sessions__id=session_id)
        else:
            queryset = self.get_queryset()
        if not request.user.is_superuser:
            queryset = queryset.filter(sessions__program__is_active=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response({"exercises": serializer.data})

    @swagger_auto_schema(tags=['Exercises'], operation_description=_("Retrieve exercise by ID"))
    def retrieve(self, request, pk=None):
        exercise = self.get_object()
        serializer = self.get_serializer(exercise)
        return Response({"exercise": serializer.data})

    @swagger_auto_schema(
        tags=['Exercises'],
        operation_description=_("Create a new exercise."),
        request_body=NestedExerciseSerializer,
        consumes=['multipart/form-data']
    )
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
    queryset = UserProgram.objects.select_related('program').all()
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
        queryset = self.get_queryset()
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

        # ✅ Ensure program_id is valid
        if not program_id or not str(program_id).isdigit():
            return Response({"error": _("Valid program_id is required.")}, status=status.HTTP_400_BAD_REQUEST)

        program_id = int(program_id)

        # ✅ Validate program existence
        try:
            program = Program.objects.get(id=program_id, is_active=True)
        except Program.DoesNotExist:
            return Response({"error": _("Invalid or inactive program_id.")}, status=status.HTTP_404_NOT_FOUND)

        create_serializer = UserProgramCreateSerializer(data=request.data)
        if create_serializer.is_valid():
            user_program = create_serializer.save(user=request.user, program=program)
            message = translate_text("Program selected. Complete payment to access sessions.", language)
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

        # ✅ Ensure only the owner can update
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

        # ✅ Ensure only the owner can update
        if user_program.user != request.user:
            message = translate_text("You do not have permission to partially update this user program.", language)
            return Response({"error": message}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(user_program, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            message = translate_text("User program partially updated successfully", language)
            return Response({"message": message, "user_program": serializer.data})

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        tags=['User Programs'],
        operation_description=_("Delete a user program")
    )
    def destroy(self, request, pk=None):
        language = self.get_user_language()
        user_program = self.get_object()

        # ✅ Ensure only the owner can delete
        if user_program.user != request.user:
            message = translate_text("You do not have permission to delete this user program.", language)
            return Response({"error": message}, status=status.HTTP_403_FORBIDDEN)

        user_program.delete()
        message = translate_text("User program deleted successfully", language)
        return Response({"message": message})

class UserFullProgramDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user_program = UserProgram.objects.filter(user=request.user, is_active=True).select_related("program").first()

            if not user_program:
                return Response({"error": _("No active program found for the user.")},
                                status=status.HTTP_404_NOT_FOUND)

            if not user_program.is_subscription_active():
                return Response({"error": _("Your subscription has ended. Please renew.")}, status=status.HTTP_403_FORBIDDEN)

            # ✅ Optimize query using select_related and prefetch_related
            sessions = Session.objects.filter(program=user_program.program)\
                .prefetch_related('exercises', 'meals__preparations')

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
            return Response({"error": _("An unexpected error occurred: ") + str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _is_session_completed(self, user, session):
        completion = SessionCompletion.objects.filter(user=user, session=session).only("is_completed").first()
        return completion.is_completed if completion else False

    def _is_meal_completed(self, user, session, meal):
        meal_completion = MealCompletion.objects.filter(user=user, session=session, meal=meal).only("is_completed").first()
        return meal_completion.is_completed if meal_completion else False
from django.utils.dateparse import parse_date

class ProgressView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "type": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["daily", "weekly", "monthly"],
                    description="Progress type (daily, weekly, or monthly)"
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

        # ✅ Validate the `type`
        if query_type not in ["daily", "weekly", "monthly"]:
            return Response({"error": _("Invalid type. Expected 'daily', 'weekly', or 'monthly'.")}, status=400)

        # ✅ Validate and parse the date
        date = parse_date(date_str)
        if not date:
            return Response({"error": _("Invalid date format. Expected 'YYYY-MM-DD'.")}, status=400)

        # ✅ Determine progress type
        if query_type == "daily":
            progress = self.calculate_daily_progress(request.user, date)
        elif query_type == "weekly":
            progress = self.calculate_weekly_progress(request.user, date)
        else:
            progress = self.calculate_monthly_progress(request.user, date)

        return Response(progress, status=200)

    def calculate_daily_progress(self, user, date):
        completed_sessions = SessionCompletion.objects.filter(user=user, session_date=date).select_related("session__block")
        completed_meals = MealCompletion.objects.filter(user=user, meal_date=date).select_related("meal")

        sessions = [
            {
                "id": session.session.id,
                "calories_burned": float(session.session.block.calories_burned) if session.is_completed and session.session.block else 0.0,
                "status": "completed" if session.is_completed else "missed"
            }
            for session in completed_sessions
        ]

        meals = [
            {
                "id": meal.meal.id,
                "calories": float(meal.meal.calories) if meal.is_completed else 0.0,
                "status": "completed" if meal.is_completed else "missed"
            }
            for meal in completed_meals
        ]

        return self._generate_summary(date, sessions, meals)

    def calculate_weekly_progress(self, user, date):
        week_start = date - timedelta(days=date.weekday())
        week_end = week_start + timedelta(days=6)

        completed_sessions = SessionCompletion.objects.filter(
            user=user, session_date__range=(week_start, week_end)
        ).select_related("session__block")

        completed_meals = MealCompletion.objects.filter(
            user=user, meal_date__range=(week_start, week_end)
        ).select_related("meal")

        sessions = [
            {
                "id": session.session.id,
                "calories_burned": float(session.session.block.calories_burned) if session.is_completed and session.session.block else 0.0,
                "status": "completed" if session.is_completed else "missed"
            }
            for session in completed_sessions
        ]

        meals = [
            {
                "id": meal.meal.id,
                "calories": float(meal.meal.calories) if meal.is_completed else 0.0,
                "status": "completed" if meal.is_completed else "missed"
            }
            for meal in completed_meals
        ]

        return self._generate_summary(week_start, sessions, meals, week_end=week_end)

    def calculate_monthly_progress(self, user, date):
        month_start = date.replace(day=1)
        next_month = month_start.replace(day=28) + timedelta(days=4)
        month_end = next_month - timedelta(days=next_month.day)

        completed_sessions = SessionCompletion.objects.filter(
            user=user, session_date__range=(month_start, month_end)
        ).select_related("session__block")

        completed_meals = MealCompletion.objects.filter(
            user=user, meal_date__range=(month_start, month_end)
        ).select_related("meal")

        sessions = [
            {
                "id": session.session.id,
                "calories_burned": float(session.session.block.calories_burned) if session.is_completed and session.session.block else 0.0,
                "status": "completed" if session.is_completed else "missed"
            }
            for session in completed_sessions
        ]

        meals = [
            {
                "id": meal.meal.id,
                "calories": float(meal.meal.calories) if meal.is_completed else 0.0,
                "status": "completed" if meal.is_completed else "missed"
            }
            for meal in completed_meals
        ]

        return self._generate_summary(month_start, sessions, meals, month_end=month_end)

    def _generate_summary(self, start_date, sessions, meals, week_end=None, month_end=None):
        """
        ✅ Generates a summarized progress report.
        """
        summary = {
            "date": str(start_date),
            "completed_sessions_count": sum(1 for s in sessions if s["status"] == "completed"),
            "missed_sessions_count": sum(1 for s in sessions if s["status"] == "missed"),
            "total_calories_burned": sum(s["calories_burned"] for s in sessions),
            "completed_meals_count": sum(1 for m in meals if m["status"] == "completed"),
            "missed_meals_count": sum(1 for m in meals if m["status"] == "missed"),
            "calories_gained": sum(m["calories"] for m in meals),
            "sessions": sessions,
            "meals": meals,
        }

        # ✅ Add week or month end date for better clarity
        if week_end:
            summary["week_end_date"] = str(week_end)
        if month_end:
            summary["month_end_date"] = str(month_end)

        return summary
