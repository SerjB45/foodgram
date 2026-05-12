import base64
import mimetypes

from django.core.files.base import ContentFile
from rest_framework import serializers


class Base64ImageField(serializers.ImageField):
    """Поле для обработки изображений, закодированных в base64."""

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
