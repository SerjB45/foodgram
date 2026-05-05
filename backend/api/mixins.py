from rest_framework import status
from rest_framework.response import Response

from .serializers import ShortRecipeSerializer


class RecipeActionMixin:

    def _toggle_recipe_action(self, request, model, error_exists_msg,
                              error_not_found_msg):

        user = request.user
        recipe = self.get_object()

        if request.method == 'POST':
            if model.objects.filter(user=user, recipe=recipe).exists():
                return Response(
                    {'errors': error_exists_msg},
                    status=status.HTTP_400_BAD_REQUEST
                )
            model.objects.create(user=user, recipe=recipe)
            serializer = ShortRecipeSerializer(recipe)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        item = model.objects.filter(user=user, recipe=recipe)
        if not item.exists():
            return Response(
                {'errors': error_not_found_msg},
                status=status.HTTP_400_BAD_REQUEST
            )
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
