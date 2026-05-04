from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user.is_authenticated and user.is_admin
        )


# class IsAdminOrReadOnly(IsAdminRole):
#     def has_permission(self, request, view):
#         return (
#             request.method in SAFE_METHODS
#             or super().has_permission(request, view)
#         )


class IsAuthorOrAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method == 'POST':
            return request.user.is_authenticated
        return True

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        if not request.user.is_authenticated:
            return False

        return (
            obj.author == request.user
            or request.user.is_admin
        )
