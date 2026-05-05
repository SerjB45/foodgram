class ValidationUtils:

    @staticmethod
    def validate_unique_ids(ids, model_class, id_name='id'):

        if not ids:
            return True, None
        existing = model_class.objects.filter(id__in=ids)
        missing_ids = set(ids) - set(existing.values_list(id_name, flat=True))
        if missing_ids:
            return False, list(missing_ids)
        return True, None

    @staticmethod
    def validate_positive_amount(amount):
        return isinstance(amount, (int, float)) and amount > 0


class UserUtils:

    @staticmethod
    def is_user_authenticated(request):
        return request is not None and not request.user.is_anonymous
