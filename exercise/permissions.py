from  rest_framework.permissions import  BasePermission,SAFE_METHODS


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        print(f"Request Method: {request.method}")
        print(f"User Authenticated: {request.user.is_authenticated}, Is Superuser: {request.user.is_superuser}")

        if request.method in SAFE_METHODS:
            return True

        if request.user and request.user.is_authenticated:
            if request.user.is_superuser:
                print("User is authenticated and is superuser.")
                return True
            else:
                print("User is authenticated but not superuser.")

        return False
