# To avoid rewriting the entire sms app to treat digifarm SMSes differently before sending, we store the digifarm farmer
# id in the Customer.phone field with a country prefix (not Kenya). We then filter out all the phone numbers with said
# prefix and pass them to a different gateway that sends messages to these using the digifarm api.
DIGIFARM_PHONE_NUMBER_PREFIX = '+492'

# number of digits we can add to the prefix
DIGIFARM_PHONE_NUMBER_DIGIT_COUNT = 13
