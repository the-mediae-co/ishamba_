from random import randint
from unittest.mock import Mock

from django.utils import timezone


def get_sms_data(text, number_from, number_to, date=None):
    date_str = date.strftime('%Y-%m-%d %H:%M:%S') if date else timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    return {
        'from': number_from,
        'to': number_to,
        'text': text,
        'date': date_str,
        'id': randint(1000, 9999),
    }


class FakeGateway(Mock):
    pass


def fake_send_message(numbers, text, from_):
    return [
        {
            'status': 'Success',
            'number': number,
            'messageId': 'some_fake_id_string',
            'cost': '1,000,000',
        }
        for number in numbers.split(',') if number
    ]
