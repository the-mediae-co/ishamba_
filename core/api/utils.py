def get_user_secret(user):
    from django.conf import settings
    return settings.SECRET_KEY + user.password
