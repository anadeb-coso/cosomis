from django.contrib import admin

from usermanager.models import UserToken

# Register your models here.


# class UserTokenAdmin(admin.ModelAdmin):
    
#     list_display = ("user", "token", "service_name", "expires_at")

#     search_fields =  ("user__username", "user__email", "token", "service_name", "expires_at"),



admin.site.register(UserToken)