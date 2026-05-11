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
    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')


class CustomUserSerializer(UserCreateSerializer):
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
        request = self.context.get('request')
        if request is None or request.user.is_anonymous:
            return False
        return obj.following.filter(user=request.user).exists()


class CustomUserCreateSerializer(CustomUserSerializer):

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

    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class ShortRecipeSerializer(serializers.ModelSerializer):
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class RecipeIngredientDetailSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='ingredient.id')
    name = serializers.CharField(source='ingredient.name')
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit')

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeSerializer(serializers.ModelSerializer):

    image = Base64ImageField()
    author = CustomUserSerializer(read_only=True)
    ingredients = serializers.SerializerMethodField()
    tags = TagSerializer(many=True, read_only=True)
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = ('id', 'tags', 'author', 'ingredients', 'is_favorited',
                  'is_in_shopping_cart', 'name', 'image', 'text',
                  'cooking_time'
                  )
        read_only_fields = ('id', 'author', 'is_favorited',
                            'is_in_shopping_cart')

    def get_ingredients(self, obj):
        return RecipeIngredientDetailSerializer(
            obj.recipe_ingredients.all(),
            many=True
        ).data

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if not UserUtils.is_user_authenticated(request):
            return False
        return Favorite.objects.filter(user=request.user, recipe=obj).exists()

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if not UserUtils.is_user_authenticated(request):
            return False
        return ShoppingList.objects.filter(
            user=request.user,
            recipe=obj
        ).exists()

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

    def to_internal_value(self, data):
        result = super().to_internal_value(data)
        if 'ingredients' in self.initial_data:
            result['ingredients_data'] = self.initial_data['ingredients']
        if 'tags' in self.initial_data:
            result['tags_data'] = self.initial_data['tags']
        return result

    def create(self, validated_data):
        ingredients_data = validated_data.pop('ingredients_data', [])
        tags_data = validated_data.pop('tags_data', [])

        recipe = Recipe.objects.create(**validated_data)

        recipe.tags.set(tags_data)

        for ingredient_data in ingredients_data:
            amount = ingredient_data.get('amount')
            ingredient = Ingredient.objects.get(id=ingredient_data.get('id'))

            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient=ingredient,
                amount=amount
            )

        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('ingredients_data', None)
        tags_data = validated_data.pop('tags_data', None)

        instance.name = validated_data.get('name', instance.name)
        instance.text = validated_data.get('text', instance.text)
        instance.cooking_time = validated_data.get(
            'cooking_time', instance.cooking_time)

        image = validated_data.get('image')
        if image:
            instance.image = image

        instance.tags.set(tags_data)
        instance.recipe_ingredients.all().delete()
        for ingredient_data in ingredients_data:
            amount = ingredient_data.get('amount')
            ingredient = Ingredient.objects.get(
                id=ingredient_data.get('id')
            )
            RecipeIngredient.objects.create(
                recipe=instance,
                ingredient=ingredient,
                amount=amount
            )

        instance.save()
        return instance


class AvatarSerializer(serializers.ModelSerializer):

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
                                'Ошибка при получении лимита рецептов.'}
                    )

        return ShortRecipeSerializer(
            recipes, many=True,
            context=self.context
        ).data

    def get_recipes_count(self, obj):
        return obj.recipes.count()
