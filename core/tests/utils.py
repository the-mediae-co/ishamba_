import csv
import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from customers.models import Customer
from subscriptions.models import Subscription

User = get_user_model()


def create_subscribed_customer(phone, start_date, end_date, **kwargs):
    customer = Customer.objects.create(
        phone=phone,
        **kwargs
    )
    subscription = Subscription.objects.create(
        customer=customer,
        start_date=start_date,
        end_date=end_date,
    )
    return customer, subscription


class UserAuthenticationMixin(object):
    def create_user(self):
        email = 'staff@example.com'
        self.user_password = 'abc'
        self.user = User.objects.create_user('testuser', email=email,
                                             password=self.user_password)
        self.user.is_staff = True
        self.user.save()
        self.client.login(username=self.user.username, password=self.user_password)

    def create_superuser(self):
        email = 'superuser@example.com'
        self.superuser_password = 'superpasswd'
        self.superuser = User.objects.create_superuser('superuser', email=email,
                                                       password=self.superuser_password)
        self.superuser.is_staff = True
        self.superuser.is_superuser = True
        self.superuser.save()
        self.client.login(username=self.superuser.username, password=self.superuser_password)


class UploadCSVFileMixin(object):
    def generate_csv_file(self, *rows, **kwargs):
        """ Creates a fake uploaded file, without touching the file system.
        """
        stream = io.StringIO()
        wr = csv.writer(stream)
        for row in rows:
            wr.writerow(row)
        return self.generate_file(stream, **kwargs)

    def generate_file(self, stream, filename='test.csv', encoding='utf-8'):
        return SimpleUploadedFile(filename, stream.getvalue().encode(encoding))
