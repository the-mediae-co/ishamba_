from django.core.mail import EmailMessage, get_connection
from django.utils.timezone import now
from django.conf import settings
from celery.utils.log import get_task_logger
from django.urls import resolve

ALLOWED_IPS = ["197.232.148.101"]  # company network range
ADMIN_IPS = ["102.217.127.108"]  # admin's external IP

logger = get_task_logger(__name__)

class IPMonitorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            resolved_view = resolve(request.path_info)
            if "login" in resolved_view.url_name and request.method == "POST":
                user_ip = self.get_client_ip(request)
                response = self.get_response(request)

                if request.user.is_authenticated:
                    user = request.user
                    alert_key = f"alert_sent_{user.username}_{user_ip}"
                    if not request.session.get(alert_key) and not self.is_allowed_ip(user_ip):
                        self.alert_admin(user, user_ip)
                        request.session[alert_key] = True
                return response
        except Exception as e:
            logger.error(f"IPMonitorMiddleware failed: {str(e)}")

        return self.get_response(request)

    def get_client_ip(self, request):
        """Extracts the client's IP address."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    def is_allowed_ip(self, ip):
        """Checks if an IP is in the allowed list or admin list."""
        return ip in ALLOWED_IPS or ip in ADMIN_IPS

    def alert_admin(self, user, ip):
        """Alerts admin when staff logs in from an unrecognized IP."""
        message = f"ALERT: {user.username} accessed the site from {ip} on {now()}!"
        logger.warning(message)

        # Send Email Notification
        notification_email = EmailMessage(
            subject=f'Unauthorized access',
            body=f'{message}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=['elizabeth@mediae.org'],
        )
        try:
            notification_email.send(fail_silently=False)
            logger.info("Email successfully sent")
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
