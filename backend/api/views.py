import base64

from django.db.models import Sum, F
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponse
from django.urls import reverse
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import (AllowAny, IsAuthenticated,
                                        IsAuthenticatedOrReadOnly)
from rest_framework.response import Response

from bookmark.models import Favorite, Follow, ShoppingList
from recipes.models import Ingredient, Recipe, RecipeIngredient, ShortLink, Tag
from users.models import User
from .filters import IngredientFilter, RecipeFilter
from .mixins import RecipeActionMixin
from .pagination import CustomPagination
from .permissions import IsAuthorOrReadOnly
from .serializers import (AvatarSerializer, CustomUserSerializer,
                          IngredientSerializer, RecipeWriteSerializer,
                          RecipeReadSerializer, SubscriptionSerializer,
                          TagSerializer)


class CustomUserViewSet(UserViewSet):
    """Работа с пользователями и подписками."""

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
        """Получение списка подписок текущего пользователя."""

        user = request.user
        queryset = User.objects.filter(following__user=user)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = SubscriptionSerializer(
                page,
                many=True,
                context={'request': request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = SubscriptionSerializer(
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
        """Подписка/отписка на автора."""

        user = request.user
        author = self.get_object()
        follow = Follow.objects.filter(user=user, author=author)

        if request.method == 'POST':
            if user == author:
                return Response(
                    {'errors': 'Нельзя подписаться на самого себя'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if follow.exists():
                return Response(
                    {'errors': 'Вы уже подписаны на этого пользователя'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            Follow.objects.create(user=user, author=author)
            serializer = SubscriptionSerializer(
                author, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if not follow.exists():
            return Response(
                {'errors': 'Вы не подписаны на этого пользователя'},
                status=status.HTTP_400_BAD_REQUEST
            )
        follow.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=('put', 'delete'),
        url_path='me/avatar',
        permission_classes=(IsAuthenticated,),
    )
    def avatar(self, request):
        """Загрузка и удаление аватара пользователя."""

        user = request.user

        if request.method == 'DELETE':
            user.avatar.delete(save=False)
            user.avatar = None
            user.save()
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = AvatarSerializer(user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """Работа с тегами."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (AllowAny,)
    pagination_class = None


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """Работа с ингредиентами."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = (AllowAny,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter
    pagination_class = None


class RecipeViewSet(RecipeActionMixin, viewsets.ModelViewSet):
    """Работа с рецептами."""

    queryset = Recipe.objects.all()
    permission_classes = (IsAuthorOrReadOnly,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = RecipeFilter
    ordering_fields = ('name', 'pub_date', 'author__username',)
    ordering = ('-id',)
    pagination_class = CustomPagination

    def get_serializer_class(self):
        """Определяем, какой сериализатор использовать."""
        if self.action in ['list', 'retrieve']:
            return RecipeReadSerializer
        return RecipeWriteSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(
        detail=True,
        methods=('post', 'delete'),
        permission_classes=(IsAuthenticated,),
        url_path='favorite',
    )
    def favorite(self, request, pk=None):
        """Добавление/удаление рецепта из избранного."""

        return self._toggle_recipe_action(
            request, Favorite,
            'Рецепт уже в избранном',
            'Рецепта нет в избранном'
        )

    @action(
        detail=True,
        methods=('post', 'delete'),
        permission_classes=(IsAuthenticated,),
        url_path='shopping_cart',
    )
    def shopping_cart(self, request, pk=None):
        """Добавление/удаление рецепта из списка покупок."""
        return self._toggle_recipe_action(
            request, ShoppingList,
            'Рецепт уже в списке покупок',
            'Рецепта нет в списке покупок'
        )

    @action(
        detail=True,
        methods=('get',),
        url_path='get-link',
        permission_classes=(AllowAny,),
    )
    def get_link(self, request, pk=None):
        """Получение короткой ссылки на рецепт."""

        recipe = self.get_object()
        short_link, created = ShortLink.objects.get_or_create(
            recipe=recipe,
            defaults={'short_code': base64.urlsafe_b64encode(
                str(recipe.id).encode()).decode()[:8]}
        )
        short_path = reverse(
            'short_link_redirect',
            args=[short_link.short_code]
        )
        short_url = request.build_absolute_uri(short_path)
        return Response({
            "short-link": short_url
        }, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=('get',),
        url_path='download_shopping_cart',
        permission_classes=(IsAuthenticated,),
    )
    def download_shopping_cart(self, request):
        """Скачивание списка покупок."""

        ingredients_query = (
            RecipeIngredient.objects
            .filter(recipe__shopping_list__user=request.user)
            .values('ingredient__name', 'ingredient__measurement_unit')
            .annotate(total_amount=Sum(F('amount')))
            .order_by('ingredient__name')
        )

        if not ingredients_query.exists():
            return Response(
                {'errors': 'Список покупок пуст'},
                status=status.HTTP_400_BAD_REQUEST
            )

        shop_list = 'Список покупок:\n\n'
        for ingredient in ingredients_query:
            shop_list += (
                f"{ingredient['ingredient__name']}: "
                f"{ingredient['total_amount']} "
                f"{ingredient['ingredient__measurement_unit']}\n"
            )

        response = HttpResponse(
            shop_list,
            content_type='text/plain; charset=utf-8'
        )
        response['Content-Disposition'] = (
            'attachment; filename="shop_list.txt"'
        )
        return response


class StaticPagesViewSet(viewsets.ViewSet):
    """Статические страницы"""
    pages = {
        'about': {'title': 'О проекте'},
        'technologies': {'title': 'Технологии'}
    }

    def list(self, request):
        titles = {slug: data['title'] for slug, data in self.pages.items()}
        return Response(titles)

    def retrieve(self, request, pk=None):
        if pk in self.pages:
            return Response(self.pages[pk])
        return Response(
            {'error': 'Страница не найдена'},
            status=status.HTTP_404_NOT_FOUND
        )


def redirect_short_link(request, short_code):
    """Перенаправление с короткой ссылки на страницу рецепта."""

    short_link = get_object_or_404(ShortLink, short_code=short_code)
    return redirect(f'/recipes/{short_link.recipe.id}/')
