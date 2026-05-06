import csv

from django.core.management.base import BaseCommand

from recipes.models import Tag


class Command(BaseCommand):
    help = 'Загружает теги из CSV-файла в базу данных'

    def handle(self, *args, **options):
        with open('data/tags.csv', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            tags = [
                Tag(
                    name=row[0],
                    slug=row[1]
                )
                for row in reader
            ]
            Tag.objects.bulk_create(tags)
        print('Теги успешно загружены.')
