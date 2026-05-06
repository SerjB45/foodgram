import django_filters
from bookmark.models import Favorite, ShoppingList
from django.db.models import Exists, OuterRef
from recipes.models import Ingredient, Recipe


class IngredientFilter(django_filters.FilterSet):

    name = django_filters.CharFilter(lookup_expr='istartswith')

    class Meta:
        model = Ingredient
        fields = ('name', )


class BaseRecipeFilter(django_filters.FilterSet):

    is_favorited = django_filters.CharFilter(method='filter_by_bool_field')
    is_in_shopping_cart = django_filters.CharFilter(
        method='filter_by_bool_field')

    def _parse_bool(self, value):
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        value = str(value).strip().lower()
        if value in ('1', 'true', 't', 'yes', 'y'):
            return True
        if value in ('0', 'false', 'f', 'no', 'n'):
            return False
        return None

    def filter_queryset(self, queryset):
        user = self.request.user

        if user.is_authenticated:
            fav_subquery = Favorite.objects.filter(
                user=user, recipe=OuterRef('pk'))
            cart_subquery = ShoppingList.objects.filter(
                user=user, recipe=OuterRef('pk'))

            queryset = queryset.annotate(
                is_favorited=Exists(fav_subquery),
                is_in_shopping_cart=Exists(cart_subquery),
            )

        return super().filter_queryset(queryset)

    def filter_by_bool_field(self, queryset, name, value):
        """Универсальный фильтр для булевых полей."""
        user = self.request.user

        if not user.is_authenticated:
            return queryset.none()

        bool_value = self._parse_bool(value)
        if bool_value is None:
            return queryset

        return queryset.filter(**{name: bool_value})


class RecipeFilter(BaseRecipeFilter):

    tags = django_filters.AllValuesMultipleFilter(field_name='tags__slug')
    author = django_filters.NumberFilter(field_name='author__id')

    class Meta:
        model = Recipe
        fields = []
