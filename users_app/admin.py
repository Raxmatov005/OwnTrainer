from django.contrib import admin

from users_app.models import (User, UserProgram, UserProgress, Program, Preparation, PreparationSteps,
                              SessionCompletion, MealCompletion, Exercise,
                              Notification, Meal, Session)

# Register your models here.
admin.site.register(User)
admin.site.register(UserProgress)
admin.site.register(Program)
admin.site.register(Session)
admin.site.register(SessionCompletion)
admin.site.register(Exercise)
admin.site.register(Meal)
admin.site.register(MealCompletion)
admin.site.register(Preparation)
admin.site.register(PreparationSteps)
admin.site.register(Notification)



