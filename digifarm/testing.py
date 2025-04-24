import json
import re

from django.conf import settings

import responses


def _success_response_callback(request):
    """
    Dynamically creates success response with record for each recipient
    """
    # return (status, headers, json.dumps(response_body))
    response_body = [{'farmerId': i['farmerId'],
                      'result': 'success',
                      'outboundSmsResultId': 'idk'}
                     for i in json.loads(request.body)]
    return (200, {}, json.dumps(response_body))


def _blocked_response_callback(request):
    """
    Dynamically creates success response with record for each recipient
    """
    # return (status, headers, json.dumps(response_body))
    return (422, {}, "")


def activate_success_response(f):
    def wrapper(*args, **kwargs):
        responses.add_callback(
            responses.POST, re.compile(settings.DIGIFARM_SMS_GATEWAY_URL.format("[^/]*")),
            callback=_success_response_callback,
            content_type='application/json'
        )

        return f(*args, **kwargs)

    return responses.activate(wrapper)


def activate_blocked_response(f):
    def wrapper(*args, **kwargs):
        responses.add_callback(
            responses.POST, re.compile(settings.DIGIFARM_SMS_GATEWAY_URL.format("[^/]*")),
            callback=_blocked_response_callback,
            content_type='application/json'
        )

        return f(*args, **kwargs)

    return responses.activate(wrapper)
