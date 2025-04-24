import random
from random import randint

import phonenumbers

from core.utils.clients import client_setting


def get_make_call_data(session_id=None, caller_number=None):
    if not session_id:
        session_id = random.randint(1000, 100000)
    if not caller_number:
        caller_number = random.randint(1000000, 9999999)

    return {
        'sessionId': session_id,
        'isActive': '1',
        'direction': 'incoming',
        'destinationNumber': client_setting('voice_queue_number'),
        'callerNumber': str(caller_number),
    }


def get_hang_call_data(session_id, caller_number, duration=None, cost=None):
    if not duration:
        duration = random.randint(100, 500)
    if not cost:
        cost = random.randint(1000, 10000)

    return {
        'sessionId': session_id,
        'isActive': '0',
        'direction': 'incoming',
        'destinationNumber': client_setting('voice_queue_number'),
        'callerNumber': caller_number,
        'durationInSeconds': duration,
        'amount': cost,
    }


def get_make_dequeue_call_data(call_center_phone_number):
    return {
        'sessionId': '12321',
        'isActive': '1',
        'direction': 'incoming',
        'destinationNumber': client_setting('voice_dequeue_number'),
        'callerNumber': call_center_phone_number,
    }


def get_hang_up_dequeue_call_data(call_center_phone_number):
    return {
        'sessionId': '12321',
        'isActive': '0',
        'direction': 'incoming',
        'destinationNumber': client_setting('voice_dequeue_number'),
        'callerNumber': call_center_phone_number,
    }


def get_dequeue_call_data(cust_session_id, caller_number, cco_session_id):
    return {
        'sessionId': cust_session_id,
        'isActive': '1',
        'direction': 'incoming',
        'destinationNumber': client_setting('voice_queue_number'),
        'callerNumber': caller_number,
        'dequeuedToPhoneNumber': client_setting('voice_dequeue_number'),
        'dequeuedToSessionId': cco_session_id,
    }


def generate_phone_number(prefix, length, max_iter=1000):
    """Generate random phone number for a given country code (prefix) and length,
    with digifarm +492 prefix handling special-cased.
    Gives up after max_iter iterations.
    """
    if prefix == 49:
        prefix = 492
        length -= 1
    lower = int('9' * (length - 1))
    upper = int('9' * length)
    tries = 0
    while (tries := tries + 1) < max_iter:
        phone_number = '{}{}{}'.format('+', prefix, randint(int(lower), int(upper)))
        if phonenumbers.is_valid_number(phonenumbers.parse(phone_number)):
            return phone_number
    print(f'Failed to generate random number for prefix {prefix}, length {length}')
    return None
