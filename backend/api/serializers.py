from django.contrib.auth import get_user_model
from djoser.serializers import UserCreateSerializer
from rest_framework import serializers

from bookmark.models import Favorite, ShoppingList
from recipes.models import Ingredient, Recipe, RecipeIngredient, Tag
from .fields import Base64ImageField
from .utils import UserUtils, ValidationUtils


USERNAME_REGEX = r'^[\w.@+-]+\Z'

User = get_user_model()


class TagSerializer(serializers.ModelSerializer):
    """Сериализатор для тегов."""

    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')


class CustomUserSerializer(UserCreateSerializer):
    """Сериализатор для пользователей."""

    username = serializers.RegexField(
        regex=USERNAME_REGEX,
        max_length=150,
    )
    is_subscribed = serializers.SerializerMethodField(
        default=False, read_only=True)

    class Meta:
        model = User
        fields = ('email', 'id', 'username',
                  'first_name', 'last_name', 'is_subscribed', 'avatar')

    def get_is_subscribed(self, obj):
        """Проверяет, подписан ли текущий пользователь на данного автора."""
        request = self.context.get('request')
        if request is None or request.user.is_anonymous:
            return False
        return obj.following.filter(user=request.user).exists()


class CustomUserCreateSerializer(CustomUserSerializer):
    """Сериализатор для создания пользователей."""

    class Meta:
        model = User
        fields = ('id', 'username', 'email',
                  'first_name', 'last_name', 'password')
        extra_kwargs = {'password': {'write_only': True}}

    def validate(self, data):
        username = data.get('username')
        email = data.get('email')

        if User.objects.filter(username=username, email=email).exists():
            raise serializers.ValidationError(
                'Пользователь с таким username и email уже существует.'
            )
        if User.objects.filter(username=username).exists():
            raise serializers.ValidationError(
                {'username': 'Пользователь с таким username уже существует.'}
            )
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError(
                {'email': 'Пользователь с таким email уже существует.'}
            )
        return data


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для ингредиентов."""

    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class ShortRecipeSerializer(serializers.ModelSerializer):
    """Сериализатор для представления рецептов в списке избранного)."""

    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class RecipeIngredientDetailSerializer(serializers.ModelSerializer):
    """Сериализатор для представления ингредиентов в рецепте."""

    id = serializers.IntegerField(source='ingredient.id')
    name = serializers.CharField(source='ingredient.name')
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit')

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения рецептов (list, retrieve)."""

    image = Base64ImageField()
    author = CustomUserSerializer(read_only=True)
    ingredients = RecipeIngredientDetailSerializer(
        source='recipe_ingredients',
        many=True,
        read_only=True
    )
    tags = TagSerializer(many=True, read_only=True)
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = ('id', 'tags', 'author', 'ingredients', 'is_favorited',
                  'is_in_shopping_cart', 'name', 'image', 'text',
                  'cooking_time')

        read_only_fields = ('id', 'author', 'is_favorited',
                            'is_in_shopping_cart')

    def _check_relation(self, obj, relation_model):
        """Проверяет, существует ли связь между текущим пользователем
        и связанной моделью для данного рецепта."""

        request = self.context.get('request')
        if not UserUtils.is_user_authenticated(request):
            return False
        return relation_model.objects.filter(
            user=request.user,
            recipe=obj
        ).exists()

    def get_is_favorited(self, obj):
        return self._check_relation(obj, Favorite)

    def get_is_in_shopping_cart(self, obj):
        return self._check_relation(obj, ShoppingList)


class RecipeWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания/обновления рецептов"""

    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = ('name', 'image', 'text', 'cooking_time')

    def to_representation(self, instance):
        """Используем RecipeReadSerializer для ответа."""
        serializer = RecipeReadSerializer(instance, context=self.context)
        return serializer.data

    def validate(self, data):
        ingredients_data = self.initial_data.get('ingredients', [])
        tags_data = self.initial_data.get('tags', [])

        self._validate_ingredients(ingredients_data)
        self._validate_tags(tags_data)
        self._validate_cooking_time(data.get('cooking_time'))
        return data

    def _validate_cooking_time(self, cooking_time):
        try:
            cooking_time = int(cooking_time)
        except (ValueError, TypeError):
            raise serializers.ValidationError(
                {
                    'cooking_time':
                        'Некорректное значение времени приготовления.'
                }
            )
        if not ValidationUtils.validate_positive_amount(cooking_time):
            raise serializers.ValidationError(
                {
                    'cooking_time':
                        'Время приготовления должно быть положительным.'
                }
            )

    def _validate_ingredients(self, ingredients_data):
        if not ingredients_data:
            raise serializers.ValidationError(
                {'ingredients': 'Должен быть указан хотя бы один ингредиент.'}
            )

        ingredient_ids = set()
        for item in ingredients_data:
            ingredient_id = item.get('id')
            try:
                amount = int(item.get('amount', 0))
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    {
                        'ingredients':
                            'Некорректное значение количества ингредиента.'
                    }
                )

            if not ValidationUtils.validate_positive_amount(amount):
                raise serializers.ValidationError(
                    {
                        'ingredients':
                        'Количество ингредиента должно быть положительным.'
                    }
                )
            if ingredient_id in ingredient_ids:
                raise serializers.ValidationError(
                    {'ingredients': 'Ингредиенты должны быть уникальными.'}
                )
            ingredient_ids.add(ingredient_id)

        valid, missing = ValidationUtils.validate_unique_ids(
            ingredient_ids, Ingredient
        )
        if not valid:
            raise serializers.ValidationError(
                {'ingredients':
                    f'Ингредиенты с id {missing} не найдены.'
                 }
            )

    def _validate_tags(self, tags_data):
        if not tags_data:
            raise serializers.ValidationError(
                {'tags': 'Должен быть указан хотя бы один тег.'}
            )

        if len(tags_data) != len(set(tags_data)):
            raise serializers.ValidationError(
                {'tags': 'Теги должны быть уникальными.'}
            )

        valid, missing = ValidationUtils.validate_unique_ids(
            tags_data, Tag
        )
        if not valid:
            raise serializers.ValidationError(
                {'tags': f'Теги с id {missing} не найдены.'}
            )

    def _set_tags(self, recipe, tags_data):
        """Установить теги для рецепта."""
        recipe.tags.set(tags_data)

    def _set_ingredients(self, recipe, ingredients_data):
        """Установить ингредиенты для рецепта."""
        recipe.recipe_ingredients.all().delete()
        recipe_ingredients = [
            RecipeIngredient(
                recipe=recipe,
                ingredient_id=ingredient_data.get('id'),
                amount=ingredient_data.get('amount')
            )
            for ingredient_data in ingredients_data
        ]
        RecipeIngredient.objects.bulk_create(recipe_ingredients)

    def create(self, validated_data):
        ingredients_data = self.initial_data.get('ingredients', [])
        tags_data = self.initial_data.get('tags', [])

        recipe = Recipe.objects.create(**validated_data)
        self._set_tags(recipe, tags_data)
        self._set_ingredients(recipe, ingredients_data)

        return recipe

    def update(self, instance, validated_data):
        ingredients_data = self.initial_data.get('ingredients')
        tags_data = self.initial_data.get('tags')

        instance = super().update(instance, validated_data)

        if tags_data is not None:
            self._set_tags(instance, tags_data)
        if ingredients_data is not None:
            self._set_ingredients(instance, ingredients_data)

        return instance


class AvatarSerializer(serializers.ModelSerializer):
    """Сериализатор для обновления аватара пользователя."""

    avatar = Base64ImageField(
        required=True,
        allow_null=True,
    )

    class Meta:
        model = User
        fields = ('avatar',)

    def update(self, instance, validated_data):
        avatar = validated_data.get('avatar')
        if avatar is not None:
            instance.avatar = avatar
            instance.save()
        return instance


class UserMeSerializer(CustomUserSerializer):
    role = serializers.CharField(read_only=True)


class SubscriptionSerializer(serializers.ModelSerializer):
    """Сериализатор для представления информации о подписках."""

    is_subscribed = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()
    avatar = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'email',
                  'is_subscribed', 'avatar', 'recipes_count', 'recipes')

    def get_is_subscribed(self, obj):
        return True

    def get_recipes(self, obj):
        request = self.context.get('request')
        recipes = obj.recipes.all()
        if request is not None:
            limit = request.query_params.get('recipes_limit')
            if limit is not None:
                try:
                    limit = int(limit)
                    if limit >= 0:
                        recipes = recipes[:limit]
                except (TypeError, ValueError):
                    raise serializers.ValidationError(
                        {
                            'recipes_limit':
                                'Ошибка при получении лимита рецептов.'
                        }
                    )

        return ShortRecipeSerializer(
            recipes, many=True,
            context=self.context
        ).data

    def get_recipes_count(self, obj):
        return obj.recipes.count()
