from decouple import config
# SMS settings

MUTE_SMS=config('MUTE_SMS', cast=bool)

AGRI_TIPS_SENDING_PERIOD = 2  # deprecated

# If an sms with identical text from the same customer is received in this
# many hours, it is considered a duplicate so not processed for keywords, etc.
DUPLICATE_SMS_DETECTION_HOURS = 2

# SMS Templates
SMS_JOIN = 'JOIN'
SMS_STOP = 'STOP'

SMS_ACTIVE_CUSTOMER_JOIN = 'active_customer_join'
SMS_INACTIVE_CUSTOMER_STOP = 'inactive_customer_stop'
SMS_INACTIVE_CUSTOMER_REJOIN = 'inactive_customer_rejoin'

SMS_REGISTRATION_COMPLETED_SWAHILI = 'registration_completed_swahili'
SMS_REGISTRATION_COMPLETED_ENGLISH = 'registration_completed_english'

SMS_EMPTY_MESSAGE_RESPONSE = 'empty_message_response'
SMS_SUBSCRIPTION_REMINDER = 'subscription_reminder'
SMS_SUBSCRIPTION_EXPIRED = 'subscription_expired'
SMS_LAPSED_CUSTOMER_REMINDER = 'lapsed_customer_reminder'
SMS_LAPSED_CUSTOMER_REJOINS = 'lapsed_customer_rejoins'
SMS_PAYMENT_RECEIVED_RESPONSE = 'payment_received_response'
SMS_INSUFFICIENT_PAYMENT_RESPONSE = 'insufficient_payment'
SMS_VOUCHER_OFFER_EXPIRED = 'voucher_offer_expired'
SMS_VOUCHER_ALREADY_USED = 'voucher_already_used'
SMS_VOUCHER_ALREADY_USED_BY_YOU = 'voucher_already_used_by_you'
SMS_FREE_MONTHS_VOUCHER_ACCEPTED = 'free_months_voucher_accepted'
SMS_UNSUPPORTED_REGION = 'unsupported_region'
SMS_UNSPECIFIED_PAYMENT_ERROR = 'unspecified_payment_error'
SMS_REMINDER_FINISH_DATA_INTAKE = 'reminder_finish_data_intake'
SMS_SIGNATURE = 'signature'
SMS_CANNOT_CONTACT_CUSTOMER = 'cannot_contact'

ELECTRICITY_QUESTION = "Do you have electricity?"
IRRIGATION_WATER_QUESTION = "Do you have a source of water that you can use for irrigation?"

# -----------------------------------------------------------------------------
# For enforcing safaricom promotional sms blackout hours
ENFORCE_BLACKOUT_HOURS = False
BLACKOUT_BEGIN_HOUR = 16  # 4pm local time (allowing one hour for overflow plus slush for minutes after the hour)
BLACKOUT_END_HOUR = 8     # 8am local time

GATEWAY_SETTINGS = {
    'AT': {
        'senders': [
            {
                'country': 'Kenya',
                'senders': [21606, 'iShambaK']
            },
            {
                'country': 'Uganda',
                'senders': ['81931', 'iShambaU']
            },
        ]
    },
    'DF': {
        'senders': [],
    },
    'ATZMB': {
        'senders': [
            {
                'country': 'Zambia',
                'senders': [384, ]
            },
        ],
    },
}

# The development environment defaults to using the Africas Talking sandbox credentials
GATEWAY_SECRETS = {
    # 'ATZMB': {
    #     'default': {
    #         'username': config('ZAMBIA_AT_USERNAME'),
    #         'api_key': config('ZAMBIA_AT_API_KEY'),
    #         'sender': 'iMunda',
    #     },
    # },
    'AT': {
        'default': {
            'username': config('DEFAULT_AT_USERNAME'),
            'api_key': config('DEFAULT_AT_API_KEY'),
            'sender': 21606,
        },
        'ishamba': {
            'username': config('ISHAMBA_AT_USERNAME'),
            'api_key': config('ISHAMBA_AT_API_KEY'),
            'sender': 21606,
        },
        # 'ichef': {
        #     'username': "ichef",
        #     'api_key': "20c5a922d83186afa428187de690d29fdb233720ea3e635a2e5ba6e33851c912",
        #     'sender': "iChef",
        # },
    },
    'DF': {
        'default': {
            'username': 'ishamba',
            'api_key': 'not used',
            'sender': 'not used',
        }
    },
}
