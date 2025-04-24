import json
from urllib.parse import parse_qs
import uuid

import responses

from django.conf import settings


def _success_response_callback(request):
    """
    Dynamically creates success response with record for each recipient
    """
    payload = parse_qs(request.body)
    recipients = payload['to'][0].split(',')
    resp_body = {
        'SMSMessageData': {
            'Recipients': [
                {
                    'number': num,
                    'cost': 'KES 0.0400',
                    'status': 'Success',
                    'messageId': 'ATXid_%d' % uuid.uuid4()
                } for num in recipients
            ]
        }
    }
    return (200, {}, json.dumps(resp_body))


def _unsupported_number_type_response_callback(request):
    """
    Dynamically creates a success response with UnsupportedNumberType status for each recipient
    """
    payload = parse_qs(request.body)
    recipients = payload['to'][0].split(',')
    resp_body = {
        'SMSMessageData': {
            'Recipients': [
                {
                    'number': num,
                    'cost': 'KES 0.0400',
                    'status': 'UnsupportedNumberType',
                    'messageId': 'ATSid_%d' % uuid.uuid4()
                } for num in recipients
            ]
        }
    }
    return (200, {}, json.dumps(resp_body))


def activate_success_response(f):
    def wrapper(*args, **kwargs):
        responses.add_callback(
            responses.POST, settings.AT_SMS_ENDPOINT,
            callback=_success_response_callback,
            content_type='application/json'
        )

        return f(*args, **kwargs)

    return responses.activate(wrapper)


def activate_unsupported_number_type_response(f):
    def wrapper(*args, **kwargs):
        responses.add_callback(
            responses.POST, settings.AT_SMS_ENDPOINT,
            callback=_unsupported_number_type_response_callback,
            content_type='application/json'
        )

        return f(*args, **kwargs)

    return responses.activate(wrapper)


def activate_error_response(f):
    def wrapper(*args, **kwargs):
        responses.add(
            responses.POST,
            settings.AT_SMS_ENDPOINT,
            body="Internal server error",
            status=500
        )

        return f(*args, **kwargs)

    return responses.activate(wrapper)
