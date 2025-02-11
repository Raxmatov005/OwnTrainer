from drf_yasg.inspectors import SwaggerAutoSchema
from drf_yasg import openapi
from .models import Program

class DynamicGoalSchema(SwaggerAutoSchema):
    """
    Custom Swagger schema to dynamically fetch goal choices for API documentation.
    """

    def get_override_parameters(self):
        """
        Override the 'goal' parameter to dynamically update choices from the database.
        """
        goal_choices = list(Program.objects.values_list('program_goal', flat=True))

        dynamic_goal_param = openapi.Parameter(
            'goal',
            openapi.IN_FORM,
            description="Goal",
            type=openapi.TYPE_STRING,
            required=True,
            enum=goal_choices,  # ✅ Now dynamically fetches choices for Swagger UI
        )

        return super().get_override_parameters() + [dynamic_goal_param]
