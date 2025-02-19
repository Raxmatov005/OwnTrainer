from django.contrib import admin
from users_app.models import UserProgram, UserSubscription

class UserProgramAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "program", "start_date", "end_date", "get_is_paid"]

    def get_is_paid(self, obj):
        subscription = UserSubscription.objects.filter(user=obj.user, is_active=True).first()
        return subscription.is_active if subscription else False

    get_is_paid.short_description = "Is Paid"
    get_is_paid.boolean = True  # Shows as a boolean (✔/❌) in the admin panel

admin.site.register(UserProgram, UserProgramAdmin)
