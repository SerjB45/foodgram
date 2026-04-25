import csv

from django.core.management.base import BaseCommand

from recipes.models import Ingredient


class Command(BaseCommand):
    help = 'Загружает ингредиенты из CSV-файла в базу данных'

    def handle(self, *args, **options):
        with open('data/ingredients.csv', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            ingredients = [
                Ingredient(
                    name=row[0],
                    measurement_unit=row[1]
                )
                for row in reader
            ]
            Ingredient.objects.bulk_create(ingredients)
        print('Ингредиенты успешно загружены.')
