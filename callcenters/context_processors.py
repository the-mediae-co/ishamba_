from django.http import HttpRequest
from callcenters.models import CallCenterOperator
from core.utils.clients import client_setting


def my_call_centers(request: HttpRequest):
    user = request.user
    if user.is_authenticated:
        callcenters = CallCenterOperator.objects.filter(operator=user, active=True).order_by('-current', '-id')
        current_callcenter = callcenters.first()
        tips_enabled = client_setting('tips_enabled')
        return {
            'call_center_data': {
                'current_call_center': current_callcenter.to_dict() if current_callcenter else None,
                'call_centers': [callcenter.to_dict() for callcenter in callcenters],
                'tips_enabled': tips_enabled
            },
            'current_call_center': current_callcenter,
            'my_call_centers_count': callcenters.count(),
        }
    return {'current_call_center': None, 'call_center_data': None, 'my_call_centers_count': 0}
