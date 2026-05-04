from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (AllowAny, IsAuthenticated,
                                        IsAuthenticatedOrReadOnly)
from rest_framework.response import Response

from bookmark.models import Favorite, Follow, ShoppingList
from recipes.models import Ingredient, Recipe, Tag
from users.models import User

from .filters import IngredientFilter
from .pagination import CustomPagination
from .permissions import IsAuthorOrAdminOrReadOnly
from .serializers import (AvatarSerializer, CustomUserSerializer,
                          IngredientSerializer, RecipeSerializer,
                          TagSerializer, ShortRecipeSerializer,
                          SubscriptionSerializer)


class CustomUserViewSet(UserViewSet):
    queryset = User.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = (IsAuthenticatedOrReadOnly,)
    pagination_class = CustomPagination

    @action(
        detail=False,
        methods=('get', 'patch', 'put', 'delete'),
        permission_classes=(IsAuthenticated,),
        url_path='me',
    )
    def me(self, request, *args, **kwargs):
        return super().me(request, *args, **kwargs)

    @action(
        detail=False,
        methods=('get',),
        permission_classes=(IsAuthenticated,),
        url_path='subscriptions',
    )
    def subscriptions(self, request):
        user = request.user
        queryset = User.objects.filter(followers__user=user)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = CustomUserSerializer(
                page,
                many=True,
                context={'request': request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = CustomUserSerializer(
            queryset,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=('post', 'delete'),
        permission_classes=(IsAuthenticated,),
        url_path='subscribe',
    )
    def subscribe(self, request, *args, **kwargs):
        user = request.user
        author = self.get_object()

        if request.method == 'POST':
            if user == author:
                return Response(
                    {'errors': 'Нельзя подписаться на самого себя'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if Follow.objects.filter(user=user, author=author).exists():
                return Response(
                    {'errors': 'Вы уже подписаны на этого пользователя'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            Follow.objects.create(user=user, author=author)
            serializer = SubscriptionSerializer(
                author, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        follow = Follow.objects.filter(user=user, author=author)
        if not follow.exists():
            return Response(
                {'errors': 'Вы не подписаны на этого пользователя'},
                status=status.HTTP_400_BAD_REQUEST
            )
        follow.delete()
        return Response(
            {'success': 'Вы успешно отписались от пользователя'},
            status=status.HTTP_204_NO_CONTENT
        )

    @action(
        detail=False,
        methods=('put', 'delete'),
        url_path='me/avatar',
        permission_classes=(IsAuthenticated,),
    )
    def avatar(self, request):
        user = request.user

        if request.method == 'DELETE':
            user.avatar.delete(save=False)
            user.avatar = None
            user.save()
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = AvatarSerializer(user, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (AllowAny,)
    pagination_class = None


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = (AllowAny,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter
    search_fields = ('^name',)
    pagination_class = None


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    permission_classes = (IsAuthorOrAdminOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filterset_fields = ('author', 'tags')

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(
        detail=True,
        methods=('post', 'delete'),
        permission_classes=(IsAuthenticated,),
        url_path='favorite',
    )
    def favorite(self, request, pk=None):
        user = request.user
        recipe = self.get_object()

        if request.method == 'POST':
            if Favorite.objects.filter(user=user, recipe=recipe).exists():
                return Response(
                    {'errors': 'Рецепт уже в избранном'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            Favorite.objects.create(user=user, recipe=recipe)
            serializer = ShortRecipeSerializer(recipe)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        favorite = Favorite.objects.filter(user=user, recipe=recipe)
        if not favorite.exists():
            return Response(
                {'errors': 'Рецепта нет в избранном'},
                status=status.HTTP_400_BAD_REQUEST
            )
        favorite.delete()
        return Response(
            {'success': 'Рецепт удален из избранного'},
            status=status.HTTP_204_NO_CONTENT
        )

    @action(
        detail=True,
        methods=('post', 'delete'),
        permission_classes=(IsAuthenticated,),
        url_path='shopping_cart',
    )
    def shopping_cart(self, request, pk=None):
        user = request.user
        recipe = self.get_object()

        if request.method == 'POST':
            if ShoppingList.objects.filter(user=user, recipe=recipe).exists():
                return Response(
                    {'errors': 'Рецепт уже в списке покупок'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            ShoppingList.objects.create(user=user, recipe=recipe)
            serializer = ShortRecipeSerializer(recipe)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        shopping_cart = ShoppingList.objects.filter(user=user, recipe=recipe)
        if not shopping_cart.exists():
            return Response(
                {'errors': 'Рецепта нет в списке покупок'},
                status=status.HTTP_400_BAD_REQUEST
            )
        shopping_cart.delete()
        return Response(
            {'success': 'Рецепт удален из списка покупок'},
            status=status.HTTP_204_NO_CONTENT
        )
