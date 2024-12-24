from django.contrib import admin


from users_app.models import UserProgram


class UserProgramAdmin(admin.ModelAdmin):
    """
    Custom admin interface for PaymeTransactions model.
    """
    list_display = ('id', 'user_id', 'program_id', 'amount', 'is_paid', 'payment_method', 'start_date', 'end_date')
    list_filter = ('is_paid', 'payment_method')
    search_fields = ('id', 'user_id', 'amount', 'payment_method')



admin.site.register(UserProgram, UserProgramAdmin)
