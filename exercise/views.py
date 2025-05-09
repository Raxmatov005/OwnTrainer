from rest_framework import viewsets, status
from users_app.models import *
from exercise.serializers import *
from django.utils.translation import gettext_lazy as _
from drf_yasg.utils import swagger_auto_schema, no_body
from exercise.permissions import IsAdminOrReadOnly
from users_app.models import translate_text, SessionCompletion, ExerciseBlock
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
from django.db.models import Q
from django.db.models import Prefetch
from django.utils.timezone import now, localdate
from django.db.models import Sum, Count







    # ProgramViewSet
class ProgramViewSet(viewsets.ModelViewSet):
        queryset = Program.objects.all()
        serializer_class = ProgramSerializer
        permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
        parser_classes = [JSONParser]

        def get_serializer_context(self):
            context = super().get_serializer_context()
            if self.request.user.is_authenticated:
                context['language'] = self.request.user.language
            else:
                context['language'] = self.request.query_params.get('lang', 'en')
            return context


        def get_queryset(self):
            # if self.request.user.is_superuser:
                return Program.objects.all()
            # user_goal = getattr(self.request.user, 'goal', None)
            # return Program.objects.filter(is_active=True, program_goal=user_goal)

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
            if self.request.user.is_authenticated:
                context['language'] = self.request.user.language
            else:
                context['language'] = self.request.query_params.get('lang', 'en')
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

        @swagger_auto_schema(tags=['Sessions'],
                             operation_description=_("List sessions for the user. Staff sees all sessions."))
        def list(self, request):
            """
            - Admins: Get all sessions.
            - Users: Get only incomplete sessions from their assigned program, with daily unlock logic.
            """
            from users_app.models import UserProgram, SessionCompletion

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

            # 🔹 Determine the next session number to unlock based on daily progression
            today = timezone.now().date()

            # Get the last completed session
            last_completed = SessionCompletion.objects.filter(
                user=request.user,
                is_completed=True,
                session__program=user_program.program
            ).order_by('-session__session_number').first()

            if not last_completed:
                # No sessions completed yet, so the first incomplete session is unlocked
                next_session_number = incomplete_sc.first().session.session_number
            else:
                # Check if today is at least the next day after the last completion
                completion_date = last_completed.completion_date
                next_day = completion_date + timedelta(days=1)
                last_completed_number = last_completed.session.session_number

                if today < next_day:
                    # It's not yet the next day, so the next session remains locked
                    # The next session number to unlock is the last completed + 1,
                    # but we'll set the unlocked session number to the last completed
                    next_session_number = last_completed_number
                else:
                    # It's the next day or later, so unlock the next session
                    next_session_number = last_completed_number + 1

            # 🔹 Get all incomplete session IDs
            session_ids = [sc.session_id for sc in incomplete_sc]

            # 🔹 Retrieve sessions and mark future ones as locked based on next_session_number
            sessions = Session.objects.filter(id__in=session_ids).order_by('session_number')
            data = [
                {**self.get_serializer(s).data, "locked": (s.session_number > next_session_number)}
                for s in sessions
            ]

            return Response({"sessions": data}, status=status.HTTP_200_OK)

        @swagger_auto_schema(
            tags=['Sessions'],
            operation_description=_("Retrieve session by session_number"),
            manual_parameters=[
                openapi.Parameter(
                    'session_number',
                    openapi.IN_QUERY,
                    description="Session number to retrieve",
                    type=openapi.TYPE_INTEGER,
                    required=True
                )
            ],
            responses={
                200: SessionPKSerializer(),
                404: "Session not found."
            }
        )
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

        @swagger_auto_schema(
            tags=['Sessions'],
            operation_description=_("Reset the last completed session (or block) for the user"),
            request_body=no_body,  # Hide request body in Swagger
            responses={200: "The last completed session or block has been reset successfully."}
        )
        @action(
            detail=False,
            methods=['post'],
            url_path='reset-last-session',
            permission_classes=[IsAuthenticated]
        )
        def reset_last_session(self, request):
            """
            1. Attempt to find the most recently completed SessionCompletion
            2. If none found, attempt to find the most recently completed ExerciseBlockCompletion
               (for the case where the session was already reset but the block wasn't)
            3. Reset that block + session + meals
            """
            from users_app.models import SessionCompletion, ExerciseBlockCompletion, MealCompletion

            # 1) Try last completed session
            last_completed_sc = SessionCompletion.objects.filter(
                user=request.user,
                is_completed=True
            ).order_by('-completion_date').first()

            if last_completed_sc:
                # We found a completed session
                session_to_reset = last_completed_sc.session
                # Reset the session
                last_completed_sc.is_completed = False
                last_completed_sc.completion_date = None
                last_completed_sc.save()

                # Reset its single block
                block_comp = ExerciseBlockCompletion.objects.filter(
                    user=request.user,
                    block__session=session_to_reset,
                    is_completed=True
                ).first()
                if block_comp:
                    block_comp.is_completed = False
                    block_comp.completion_date = None
                    block_comp.save()

                # Reset meals
                MealCompletion.objects.filter(
                    user=request.user,
                    session=session_to_reset
                ).update(is_completed=False, completion_date=None, missed=False)

                return Response(
                    {"message": _("The last completed session has been reset successfully.")},
                    status=200
                )

            # 2) No completed session found, so look for a completed block
            last_completed_bc = ExerciseBlockCompletion.objects.filter(
                user=request.user,
                is_completed=True
            ).order_by('-completion_date').first()

            if last_completed_bc:
                # We found a block that’s completed, but presumably the session was partially reset
                session_to_reset = last_completed_bc.block.session

                # 2a) Reset the block
                last_completed_bc.is_completed = False
                last_completed_bc.completion_date = None
                last_completed_bc.save()

                # 2b) Optionally reset its session if it still shows completed
                sc = SessionCompletion.objects.filter(
                    user=request.user,
                    session=session_to_reset
                ).first()
                if sc and sc.is_completed:
                    sc.is_completed = False
                    sc.completion_date = None
                    sc.save()

                # 2c) Reset meals
                MealCompletion.objects.filter(
                    user=request.user,
                    session=session_to_reset
                ).update(is_completed=False, completion_date=None, missed=False)

                return Response(
                    {"message": _("The last completed block has been reset successfully.")},
                    status=200
                )

            # 3) If neither a completed session nor a completed block is found...
            return Response({"error": _("No completed session or block left to reset.")}, status=404)


class ExerciseBlockViewSet(viewsets.ModelViewSet):
    """
    List/Detail: show URL fields for images
    Create/Update: JSON-only (no block_image).
    Separate endpoints for uploading images.
    """
    queryset = ExerciseBlock.objects.all()
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly, IsSubscriptionActive]
    parser_classes = [JSONParser]

    def get_serializer_class(self):
        # Use distinct serializers for create vs. update/partial_update
        if self.action == 'list':
            return ExerciseBlockListSerializer
        elif self.action == 'retrieve':
            return ExerciseBlockDetailSerializer
        elif self.action == 'create':
            return ExerciseBlockCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ExerciseBlockUpdateSerializer
        return ExerciseBlockListSerializer  # fallback

    # def get_queryset(self):
    #     if getattr(self, 'swagger_fake_view', False):
    #         return ExerciseBlock.objects.none()
    #
    #     user = self.request.user
    #     if user.is_staff or user.is_superuser:
    #         return ExerciseBlock.objects.all()
    #
    #     user_program = UserProgram.objects.filter(user=user, is_active=True).first()
    #     if not user_program:
    #         return ExerciseBlock.objects.none()
    #
    #     # Add subscription check
    #     has_active_subscription = UserSubscription.objects.filter(
    #         user=user,
    #         is_active=True,
    #         end_date__gte=timezone.now().date()
    #     ).exists()
    #
    #     if not has_active_subscription:
    #         return ExerciseBlock.objects.none()
    #
    #     return ExerciseBlock.objects.filter(
    #         session__program=user_program.program
    #     ).distinct()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return ExerciseBlock.objects.none()

        user = self.request.user
        if not user.is_authenticated:
            return ExerciseBlock.objects.none()

        if user.is_staff or user.is_superuser:
            return ExerciseBlock.objects.all()

        user_program = UserProgram.objects.filter(user=user, is_active=True).first()
        if not user_program or not UserSubscription.objects.filter(
                user=user, is_active=True, end_date__gte=timezone.now().date()
        ).exists():
            return ExerciseBlock.objects.none()

        return ExerciseBlock.objects.filter(
            session__program=user_program.program
        ).distinct()


    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.user.is_authenticated:
            context['language'] = self.request.user.language
        else:
            context['language'] = self.request.query_params.get('lang', 'en')
        return context

    @swagger_auto_schema(
        operation_description="List all accessible exercise blocks (subscription required for non-admins)",
        responses={
            200: ExerciseBlockListSerializer(many=True),
            403: openapi.Response(
                description="Subscription expired",
                examples={
                    "application/json": {
                        "error": "Please upgrade your subscription to access exercise blocks.",
                        "subscription_options_url": "https://owntrainer.uz/api/subscriptions/options/"
                    }
                }
            )
        }
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        # Return custom error message if queryset is empty due to subscription
        if not queryset.exists() and not (request.user.is_staff or request.user.is_superuser):
            user_program = UserProgram.objects.filter(user=request.user, is_active=True).first()
            if user_program:
                has_active_subscription = UserSubscription.objects.filter(
                    user=request.user,
                    is_active=True,
                    end_date__gte=timezone.now().date()
                ).exists()
                if not has_active_subscription:
                    return Response({
                        "error": _("Please upgrade your subscription to access exercise blocks."),
                        "subscription_options_url": "https://owntrainer.uz/api/subscriptions/options/"
                    }, status=status.HTTP_403_FORBIDDEN)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Retrieve a specific exercise block (subscription required for non-admins)",
        responses={
            200: ExerciseBlockDetailSerializer(),
            403: openapi.Response(
                description="Subscription expired",
                examples={
                    "application/json": {
                        "error": "Please upgrade your subscription to access exercise blocks.",
                        "subscription_options_url": "https://owntrainer.uz/api/subscriptions/options/"
                    }
                }
            ),
            404: openapi.Response(description="Exercise block not found")
        }
    )
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()  # This uses get_queryset
        if not instance and not (request.user.is_staff or request.user.is_superuser):
            user_program = UserProgram.objects.filter(user=request.user, is_active=True).first()
            if user_program:
                has_active_subscription = UserSubscription.objects.filter(
                    user=request.user,
                    is_active=True,
                    end_date__gte=timezone.now().date()
                ).exists()
                if not has_active_subscription:
                    return Response({
                        "error": _("Please upgrade your subscription to access exercise blocks."),
                        "subscription_options_url": "https://owntrainer.uz/api/subscriptions/options/"
                    }, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create an ExerciseBlock (JSON-only). No block_image here.",
        request_body=ExerciseBlockCreateSerializer,  # <-- changed here
        responses={201: ExerciseBlockDetailSerializer()}
    )
    def create(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({"detail": "Admins only"}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Update an ExerciseBlock (JSON-only). No block_image here.",
        request_body=ExerciseBlockUpdateSerializer,  # <-- changed here
        responses={200: ExerciseBlockDetailSerializer()}
    )
    def update(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({"detail": "Admins only"}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Partially update an ExerciseBlock (JSON-only). No block_image here.",
        request_body=ExerciseBlockUpdateSerializer,  # <-- changed here
        responses={200: ExerciseBlockDetailSerializer()}
    )
    def partial_update(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({"detail": "Admins only"}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response({"detail": "Admins only"}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    # -----------
    # Upload block_image (unchanged)
    # -----------
    @swagger_auto_schema(
        method='patch',
        operation_description="Upload or replace block_image (admins only).",
        consumes=['multipart/form-data'],
        request_body=ExerciseBlockImageUploadSerializer,
        responses={200: "Block image uploaded"}
    )
    @action(detail=True, methods=['patch'], url_path='upload-block-image', parser_classes=[MultiPartParser, FormParser])
    def upload_block_image(self, request, pk=None):
        if not request.user.is_staff:
            return Response({"detail": "Admins only"}, status=status.HTTP_403_FORBIDDEN)

        block = self.get_object()
        serializer = ExerciseBlockImageUploadSerializer(block, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Block image uploaded."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # -----------
    # Upload an Exercise's image (unchanged)
    # -----------

class ExerciseViewSet(viewsets.ModelViewSet):
    """
    Endpoints for listing, retrieving, creating, and updating Exercises.
    Uses separate serializers for create and update operations.
    """
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    parser_classes = [JSONParser]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Exercise.objects.none()

        user = self.request.user
        if not user.is_authenticated:
            return Exercise.objects.none()

        if user.is_superuser or user.is_staff:
            return Exercise.objects.all()

        user_program = UserProgram.objects.filter(user=user, is_active=True).first()
        if not user_program or not user_program.is_subscription_active():
            return Exercise.objects.none()

        return Exercise.objects.filter(
            blocks__session__program=user_program.program,
            exercise_type=user.goal
        ).distinct()


    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.user.is_authenticated:
            context['language'] = self.request.user.language
        else:
            context['language'] = self.request.query_params.get('lang', 'en')
        return context

    def get_serializer_class(self):
        if self.action == 'list':
            return ExerciseListSerializer
        elif self.action == 'retrieve':
            return ExerciseDetailSerializer
        elif self.action == 'create':
            return ExerciseCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ExerciseUpdateSerializer
        return ExerciseListSerializer

    @swagger_auto_schema(
        method='patch',
        operation_description="Upload or replace an Exercise's image (admins only). Only the image field will be updated.",
        consumes=['multipart/form-data'],
        request_body=ExerciseImageUploadSerializer,
        responses={200: "Exercise image updated"}
    )
    @action(
        detail=True,
        methods=['patch'],
        url_path='upload-image',
        parser_classes=[MultiPartParser, FormParser]
    )
    def upload_image(self, request, pk=None):
        if not request.user.is_staff:
            return Response({"detail": "Admins only"}, status=status.HTTP_403_FORBIDDEN)

        # Retrieve the Exercise instance using the pk provided in the URL.
        exercise = self.get_object()

        # Validate only the image field using the dedicated serializer.
        serializer = ExerciseImageUploadSerializer(exercise, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Exercise image updated."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def maybe_mark_session_completed(user, session):
    # 1) Check if block is completed
    block_completed = ExerciseBlockCompletion.objects.filter(
        user=user,
        block=session.block,  # because session has a OneToOneField to block
        is_completed=True
    ).exists()

    if not block_completed:
        return False

    # 2) Check if all meals are completed
    meal_ids = session.meals.values_list('id', flat=True)
    total_meals = len(meal_ids)
    completed_meals = MealCompletion.objects.filter(
        user=user,
        session=session,
        meal_id__in=meal_ids,
        is_completed=True
    ).count()

    if completed_meals < total_meals:
        return False

    # 3) If both block and meals are completed, mark session as completed.
    sc, created = SessionCompletion.objects.get_or_create(
        user=user,
        session=session,
        defaults={'session_number_private': session.session_number}  # Provide default value here
    )
    sc.is_completed = True
    sc.completion_date = timezone.now().date()
    sc.save()

    return True



class CompleteBlockView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        tags=['Sessions'],
        operation_description=_("Complete the exercise block (one block per session)."),
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'block_id': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="ID of the ExerciseBlock"
                )
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
        session = block.session  # OneToOne

        # # Check if all exercises in the block match the user's goal
        # mismatched_exercises = block.exercises.filter(~Q(exercise_type=request.user.goal))
        # if mismatched_exercises.exists():
        #     return Response({"error": _("This block contains exercises that do not match your goal.")}, status=400)

        # Mark the block as completed for this user
        bc, created = block.completions.get_or_create(user=request.user)
        if bc.is_completed:
            session_completed = maybe_mark_session_completed(request.user, session)
            return Response({
                "message": _("Block already completed."),
                "block_time": block.block_time,
                "calories_burned": block.calories_burned,
                "session_completed": session_completed
            }, status=200)

        bc.is_completed = True
        bc.completion_date = timezone.now().date()
        bc.save()

        session_completed = maybe_mark_session_completed(request.user, session)

        return Response({
            "message": _("Block completed."),
            "block_time": block.block_time,
            "calories_burned": block.calories_burned,
            "session_completed": session_completed
        }, status=200)

class UserProgramViewSet(viewsets.ModelViewSet):
        queryset = UserProgram.objects.select_related('program').all()
        serializer_class = UserProgramSerializer
        permission_classes = [IsAuthenticated]

        def get_user_language(self):
            """
            Determines the user's language preference.
            Checks authenticated user's language attribute first,
            then falls back to 'lang' query parameter,
            and finally defaults to 'en'.
            """
            # Check authenticated user first
            if self.request.user.is_authenticated and hasattr(self.request.user,
                                                              'language') and self.request.user.language:
                return self.request.user.language

            # Fallback to query parameter
            lang_param = self.request.query_params.get('lang')
            if lang_param:
                return lang_param

            # Default language if none found
            return 'en'  # Or get default from settings: settings.LANGUAGE_CODE

        def get_serializer_context(self):
            context = super().get_serializer_context()
            # Use the new method to ensure consistency
            context['language'] = self.get_user_language()
            return context

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

            if not program_id or not str(program_id).isdigit():
                return Response({"error": _("Valid program_id is required.")}, status=status.HTTP_400_BAD_REQUEST)

            program_id = int(program_id)

            try:
                program = Program.objects.get(id=program_id, is_active=True)
            except Program.DoesNotExist:
                return Response({"error": _("Invalid or inactive program_id.")}, status=status.HTTP_404_NOT_FOUND)

            # Check if the program's goal matches the user's goal
            if program.program_goal != request.user.goal:
                return Response({"error": _("This program does not match your goal.")},
                                status=status.HTTP_400_BAD_REQUEST)

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
                user_program = UserProgram.objects.filter(user=request.user, is_active=True).select_related(
                    "program").first()

                if not user_program:
                    return Response({"error": _("No active program found for the user.")},
                                    status=status.HTTP_404_NOT_FOUND)

                if not user_program.is_subscription_active():
                    return Response({"error": _("Your subscription has ended. Please renew.")},
                                    status=status.HTTP_403_FORBIDDEN)

                sessions = Session.objects.filter(program=user_program.program) \
                    .prefetch_related(
                    Prefetch('exercises', queryset=Exercise.objects.filter(exercise_type=request.user.goal)),
                    Prefetch('meals', queryset=Meal.objects.filter(goal_type=request.user.goal))
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
                                    "exercise_type": exercise.exercise_type,
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
                                    "goal_type": meal.goal_type,
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





class StatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Returns daily, weekly, or monthly statistics in a specific JSON format.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "type": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["daily", "weekly", "monthly"],
                    description="Choose a time range: daily, weekly, or monthly"
                ),
                "date": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="date",
                    description="Specify a date (format: YYYY-MM-DD)"
                ),
            },
            required=["type", "date"],
        ),
        responses={200: "Success", 400: "Invalid request"},
    )
    def post(self, request):
        query_type = request.data.get("type")  # "daily", "weekly", or "monthly"
        date_str = request.data.get("date")    # "YYYY-MM-DD"

        # Validate query_type
        if query_type not in ["daily", "weekly", "monthly"]:
            return Response({"error": "Invalid type. Use 'daily', 'weekly', or 'monthly'."}, status=400)

        # Parse date
        try:
            date = localdate().fromisoformat(date_str)
        except (TypeError, ValueError):
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        # Dispatch to the correct function
        if query_type == "daily":
            result = self.get_daily_data(request.user, date)
        elif query_type == "weekly":
            result = self.get_weekly_data(request.user, date)
        else:  # "monthly"
            result = self.get_monthly_data(request.user, date)

        return Response(result, status=200)

    def get_daily_data(self, user, date):
        """
        Return a dict with one key (the date) -> { total_calories_burned, calories_gained, session_complete }.
        Example:
        {
          "2025-03-01": {
            "total_calories_burned": 0,
            "calories_gained": 165,
            "session_complete": true
          }
        }
        """
        data_for_day = self._get_day_info(user, date, include_calories=True)
        return {
            str(date): data_for_day
        }

    def get_weekly_data(self, user, date):
        """
        Return a dict with 7 keys (one for each day of the week).
        Example:
        {
          "2025-03-01": { ... },
          "2025-03-02": { ... },
          ...
        }
        """
        # Calculate start (Monday) and end (Sunday) of that week
        start_date = date - timedelta(days=date.weekday())  # Monday
        end_date = start_date + timedelta(days=6)           # Sunday

        result = {}
        current = start_date
        while current <= end_date:
            data_for_day = self._get_day_info(user, current, include_calories=True)
            result[str(current)] = data_for_day
            current += timedelta(days=1)

        return result

    def get_monthly_data(self, user, date):
        """
        Return a dict with one key per day in that month,
        only showing { "session_complete": True/False } for each date.
        Example:
        {
          "2025-03-01": { "session_complete": true },
          "2025-03-02": { "session_complete": false },
          ...
        }
        """
        # First day of the month
        start_date = date.replace(day=1)

        # Compute last day of the month
        next_month = (start_date.replace(day=28) + timedelta(days=4))
        last_day = (next_month - timedelta(days=next_month.day)).day
        end_date = start_date.replace(day=last_day)

        result = {}
        current = start_date
        while current <= end_date:
            # We only want session_complete for monthly
            day_info = self._get_day_info(user, current, include_calories=False)
            result[str(current)] = {
                "session_complete": day_info["session_complete"]
            }
            current += timedelta(days=1)

        return result

    def _get_day_info(self, user, date, include_calories=False):
        # Check for completed blocks directly, instead of relying on SessionCompletion
        blocks_this_day = ExerciseBlockCompletion.objects.filter(
            user=user,
            is_completed=True,
            completion_date=date,
            block__session__block__exercises__exercise_type=user.goal
        ).distinct()

        # Consider the session "complete" for statistics purposes if the block is completed
        session_complete = blocks_this_day.exists()
        day_info = {"session_complete": session_complete}

        if include_calories:
            # Calculate calories burned from completed blocks
            total_burned = ExerciseBlockCompletion.objects.filter(
                user=user,
                completion_date=date,
                is_completed=True,
                block__session__block__exercises__exercise_type=user.goal
            ).aggregate(Sum('block__calories_burned'))['block__calories_burned__sum'] or 0.0

            # Calories gained from meals (unchanged)
            total_gained = MealCompletion.objects.filter(
                user=user,
                completion_date=date,
                is_completed=True,
                meal__goal_type=user.goal
            ).aggregate(Sum('meal__calories'))['meal__calories__sum'] or 0.0

            day_info["total_calories_burned"] = float(total_burned)
            day_info["calories_gained"] = float(total_gained)

        return day_info




from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from datetime import datetime, timedelta
from django.db.models import Sum
from dateutil import parser as date_parser

class WeeklyCaloriesView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Returns calorie statistics for a month, divided into four weeks, with total calories burned and gained per week.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "date": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format="date",
                    description="Specify a date in the month (format: YYYY-MM-DD)"
                ),
            },
            required=["date"],
        ),
        responses={200: "Success", 400: "Invalid request"},
    )
    def post(self, request):
        date_str = request.data.get("date")  # "YYYY-MM-DD"

        # Parse date
        try:
            date = date_parser.isoparse(date_str).date()
        except (TypeError, ValueError):
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        result = self.get_monthly_weekly_calories(request.user, date)
        return Response(result, status=200)

    def get_monthly_weekly_calories(self, user, date):
        """
        Return a dict with four keys (week_1, week_2, week_3, week_4), each containing
        total calories burned and gained for that week in the month.
        Example:
        {
          "week_1": {
            "total_calories_burned": 1200.0,
            "calories_gained": 5600.0
          },
          "week_2": {
            "total_calories_burned": 1100.0,
            "calories_gained": 5400.0
          },
          ...
        }
        """
        # First day of the month
        start_date = date.replace(day=1)

        # Compute last day of the month
        next_month = (start_date.replace(day=28) + timedelta(days=4))
        last_day = (next_month - timedelta(days=next_month.day)).day
        end_date = start_date.replace(day=last_day)

        # Divide month into roughly 4 weeks (7-day periods, may not align with calendar weeks)
        week_length = (end_date - start_date).days // 4 + 1
        result = {}

        for week in range(4):
            week_start = start_date + timedelta(days=week * week_length)
            week_end = min(week_start + timedelta(days=week_length - 1), end_date)

            # Calculate calories for the week
            total_burned = ExerciseBlockCompletion.objects.filter(
                user=user,
                completion_date__range=[week_start, week_end],
                is_completed=True,
                block__session__block__exercises__exercise_type=user.goal
            ).aggregate(Sum('block__calories_burned'))['block__calories_burned__sum'] or 0.0

            total_gained = MealCompletion.objects.filter(
                user=user,
                completion_date__range=[week_start, week_end],
                is_completed=True,
                meal__goal_type=user.goal
            ).aggregate(Sum('meal__calories'))['meal__calories__sum'] or 0.0

            result[f"week_{week + 1}"] = {
                "total_calories_burned": float(total_burned),
                "calories_gained": float(total_gained)
            }

        return result