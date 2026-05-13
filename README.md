# Foodgram

Проект доступен по ссылке: https://foodgramserj.sytes.net

Проект по публикации рецептов. Позволяет публиковать свои рецепты, добавлять их в избранное. Подписываться на других пользователей. Есть возможность по составлению списка покупок ингридиентов, необходимых для рецепта.

# Стек технологий
- Python 3.12
- Django 6.0
- Gunicorn 26.0
- Django Rest Framework 3.17
- Pillow 12.0
- PostgreSQL
- Docker
- Nginx



# Как запустить проект:
## 1 вариант(из готовых образов)
1. скачать docker-compose.production.yml
2. создать файл с переменными окружениями .env в корне проекта(пример заполнения в .env.example)
3. выполнить команду docker compose -f docker-compose.production.yml up
4. выполнить миграции 
- sudo docker compose -f docker-compose.production.yml exec backend python manage.py migrate
- sudo docker compose -f docker-compose.production.yml exec backend python manage.py collectstatic
5. Проверить доступность проекта по localhost

## 2 вариант(сборка проекта из исходников)
1. Клонировать репозиторий и перейти в него:

```
git clone https://github.com/SerjB45/foodgram.git
```

```
cd foodgram_backend
```

2. Cоздать и активировать виртуальное окружение:

```
python3 -m venv env
```

* Если у вас Linux/macOS

    ```
    source env/bin/activate
    ```

* Если у вас windows

    ```
    source env/scripts/activate
    ```

```
python3 -m pip install --upgrade pip
```

3. Установить зависимости из файла requirements.txt:

```
pip install -r backend/requirements.txt
```

4. создать файл с переменными окружениями .env в корне проекта(пример заполнения в .env.example)

5. Запустите проект 
```
sudo docker compose up
```

6. выполнить миграции 
- sudo docker compose exec backend python manage.py migrate
- sudo docker compose exec backend python manage.py collectstatic

7. Проверить доступность проекта по localhost


# Документация по API
Спецификация по API находится по адресу http://localhost/api/docs/.

