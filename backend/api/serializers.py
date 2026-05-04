import base64
import mimetypes

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from djoser.serializers import UserCreateSerializer
from rest_framework import serializers

from recipes.models import Ingredient, Recipe, RecipeIngredient, Tag

USERNAME_REGEX = r'^[\w.@+-]+\Z'

User = get_user_model()


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]

            data = ContentFile(base64.b64decode(imgstr), name='temp.' + ext)

        return super().to_internal_value(data)

    def to_representation(self, value):
        if not value:
            return None
        try:
            file_path = value.path
        except Exception:
            return super().to_representation(value)

        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = 'application/octet-stream'

        try:
            with value.open('rb') as f:
                data = base64.b64encode(f.read()).decode()
        except Exception:
            return super().to_representation(value)

        return f'data:{mime_type};base64,{data}'


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


class IngredientSerializer(serializers.ModelSerializer):

    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class ShortRecipeSerializer(serializers.ModelSerializer):
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class RecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(),
        source='ingredient'
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'amount')


class RecipeSerializer(serializers.ModelSerializer):

    image = Base64ImageField()
    ingredients = RecipeIngredientSerializer(
        source='recipe_ingredients',
        many=True,
    )

    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True
    )

    class Meta:
        model = Recipe
        fields = ('ingredients', 'tags', 'image',
                  'name', 'text', 'cooking_time')

        # fields = ( 'name', 'image',
        #           'text', 'ingredients', 'tags', 'cooking_time')

    def create(self, validated_data):
        recipe_ingredients_data = validated_data.pop('recipe_ingredients')
        tags_data = validated_data.pop('tags')

        recipe = Recipe.objects.create(**validated_data)

        for ingredient_data in recipe_ingredients_data:
            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient=ingredient_data['ingredient'],
                amount=ingredient_data['amount']
            )

        recipe.tags.set(tags_data)

        return recipe

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.text = validated_data.get('text', instance.text)
        instance.cooking_time = validated_data.get(
            'cooking_time', instance.cooking_time)

        image = validated_data.get('image')
        if image is not None:
            instance.image = image

        if 'recipe_ingredients' in validated_data:
            instance.recipe_ingredients.all().delete()
            for ingredient_data in validated_data['recipe_ingredients']:
                RecipeIngredient.objects.create(
                    recipe=instance,
                    ingredient=ingredient_data['ingredient'],
                    amount=ingredient_data['amount']
                )

        if 'tags' in validated_data:
            instance.tags.clear()
            for tag_data in validated_data['tags']:
                instance.tags.add(tag_data['id'])

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
    recipes = ShortRecipeSerializer(many=True, read_only=True)
    recipes_count = serializers.SerializerMethodField()
    avatar = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'email',
                  'is_subscribed', 'avatar', 'recipes_count', 'recipes')

    def get_is_subscribed(self, obj):
        return True

    def get_recipes_count(self, obj):
        return obj.recipes.count()
