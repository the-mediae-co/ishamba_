iShamba
=======

iShamba is a Django application for storing customer and agricultural
information; collating information from various sources and providing it on a
scheduled basis (via incoming phone calls, incoming and outgoing SMS messages
and USSD sessions) with these Customers.

## Clone

```
git clone https://github.com/the-mediae-co/ishamba
```

## Setup

To set up for development on a new machine:

1. Ensure you have the following system dependencies installed:

   * [PostgreSQL](https://www.postgresql.org/)
   * [PostGIS](https://docs.djangoproject.com/en/stable/ref/contrib/gis/install/postgis/)

   The recommended steps to install these on an Ubuntu server are:

   ```bash
   # PostgreSQL
   sudo apt install postgresql libpq-dev postgresql-client postgresql-contrib python3-dev

   # For development purposes grant your user all privileges on postgres (replace <YOUR_USERNAME> with your username).
   sudo su - postgres -c "createuser -s <YOUR_USERNAME>"

   # PostGIS
   sudo apt install binutils libproj-dev gdal-bin postgis
   ```

2. Create a `basecamp` database on your PostgreSQL server. Historically, the database
   has been called basecamp. The origin of this name is unknown but this does help
   eliminate a db name collision in development when working on both the ishamba
   portal and the ishamba web site ('w/ db named ishamba').

   ```bash
   psql postgres
   > CREATE DATABASE basecamp;
   > CREATE USER basecamp WITH ENCRYPTED PASSWORD 'strong_password'; # customize username and password
   > GRANT ALL ON DATABASE basecamp to basecamp;
   ```

3. Copy .env.example to .env

   ```bash
   cp .env.example .env
   ```

   Update the settings in the .env file esp the database settings

## Setup for Mac Users
If you're a Mac user, use a `local.py` file for system-specific overrides. It's important to note that `local.py` is intended for system-specific configurations, not environment-specific variables.

Note: The file `local.py` is git ignored and should not be added to the repository.

4. In a virtual environment, install the development dependencies:

   ```bash
   pip install -r requirements/development.txt
   ```

6. Comment out the following line in `ishamba/settings/base.py`, to work around
   a bug in django-tenants that prevents initial migration when any
   extensions are defined:

   ```python
   PG_EXTRA_SEARCH_PATHS = ['extensions']
   ```

7. Run the initial migrations:

   ```bash
   python manage.py migrate_schemas
   ```

8. Uncomment the PG_EXTRA_SEARCH_PATHS line mentioned two steps prior.

9. Create a tenant (Client) in the new database:
   Specify required settings. These are required for proper running of the portal
   They can be dummy values to start with and can be later updated to real values when testing

   ```python
   python manage.py shell
   >>> from core.models import Client, Domain
   >>>c = Client.objects.create(
      name='iShamba',
      schema_name='ishamba',
      voice_queue_number='+254700000000',
      voice_dequeue_number='+254700000001',
      sms_shortcode=21606,
      mpesa_till_number=21606,
      monthly_price=10.0,
      yearly_price=110.0,
      tip_reports_to="<email_address>",
      at_api_key = "some_key",
      at_username = "sandbox",
      at_sender = "ishamba",
      pusher_app_id = "",
      pusher_key = "",
      pusher_secret = "",
   )
   Domain.objects.create(
      domain='localhost',
      is_primary=True,
      tenant=c
   )

   ```

   Ensure that the `domain` used here matches the hostname that you
   intend to use for this project in development. If testing with multiple
   tenants you will need to use a different `Client` with a primary `Domain` with a unique `domain` for each, and map
   these to your development server IP address in your hosts file.

10. Create a superuser on the new tenant so that you can log in:

    ```bash
    python manage.py tenant_command createsuperuser --schema=ishamba
    ```

11. Your development server should be all set up, and ready to run:

    ```bash
    python manage.py runserver 7000
    ```

    _Note that any free server port can be used. The default is 8000, but we
    typically use 7000 for ishamba portal work, so as to not conflict with
    work on other django web server projects that default to 8000._

12. Point your browser to the same port as above, on the same domain as defined in the
    Client domain_url defined in step 9 above, to make sure the server is working: <http://localhost:7000/>

___

#### _**Deprecated**_: Digifarm USSD authentication

Requests made to the old Digifarm USSD handler view were authenticated using Basic Auth. The
username and password used in the request must belong to an existing user account
that has the `auth.ussd_access` permission. To generate this permission, run the following:

```bash
./manage.py tenant_command generate_ussd_permission
```

Once generated the permission will appear in the permission's list as

`auth | user | Can call ussd webhook`

---

## Libraries and dependencies

We're using [django-phonenumber-field][], an interface to a python port of the
Google [libphonenumber][] library, and [django-import-export][] for CSV
importing and exporting (of customers, market prices on a schedule, voucher codes in a
view, county forecasts and SMS data in management commands). [Django-extensions][]
is installed for dev (giving the `shell_plus` and `runserver_plus` commands).

The front-end styling is mostly bespoke CSS, rather than a particular
framework. jQuery is installed and required. The Call Centre part of the app
uses [Angular JS][] (not to be confused with <https://angular.io/>) for the
front-end app and [Django REST framework][] for the back-end views.

Other less common dependencies and service integrations include [Leaflet][]
for geo mapping, [Pusher][] for call centre communication.

[django-import-export]: https://django-import-export.readthedocs.org/
[django-phonenumber-field]: https://github.com/stefanfoulis/django-phonenumber-field
[libphonenumber]: https://github.com/googlei18n/libphonenumber
[Django-extensions]: http://django-extensions.readthedocs.org/en/latest/
[Django REST framework]: http://www.django-rest-framework.org/
[Angular JS]: https://angularjs.org/
[Leaflet]: http://leafletjs.com/
[Pusher]: https://pusher.com/

Lots of the front-end views use Django's class based views (CBVs) for the
internals, and [django-tables2][] and [django-crispy-forms][] for presentation.

[django-tables2]: https://django-tables2.readthedocs.org/
[django-crispy-forms]: http://django-crispy-forms.readthedocs.org/en/d-0/index.html

## AWS Bedrock Integration

To configure the AWS Bedrock dependency locally:

1. Add the following environment variables to your **.env** file:
`AWS_BEDROCK_REGION=<aws-region>`

2. Ensure you have AWS credentials configured locally.
This can be done by making sure the `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are in the **.env** file.

3. When you're testing locally, make sure the AWS SDK for Python (boto3) is installed:
`pip install boto3`

---

## External services

In addition to [Pusher][] for application operation we talk to
[Africa's Talking][] for calls and SMS messages.

[Africa's Talking]: https://www.africastalking.com/

---

## Coding style

* Lots of use of Django CBVs. This should not be considered a binding
   requirement for future features. See [Classy Class-Based Views][] for a good
   resource.
* Aim to use `django.utils.timezone.localtime` for timezone aware times wherever possible.
* Python code should adhere to the [Google Python Style Guide][], however, not
   all existing code does.
* The project is migrating toward the use of the [Black Uncompromising Code Formatter][] to enforce more consistency and readability.

[Classy Class-Based Views]: http://ccbv.co.uk/
[Google Python Style Guide]: https://google.github.io/styleguide/pyguide.html
[Black Uncompromising Code Formatter]: https://github.com/psf/black

---

## Testing

There is a still-growing test suite. The test suite can be run by executing
`pytest` on the development machine. To test individual modules simply pass the
app/directory name as the first argument to `pytest` (e.g. `pytest agri`).

Parallel testing is enabled by including these command-line parameters: `-n auto --dist loadscope`

At the time of writing it is also required to have values for the following
settings: `PUSHER_APP_ID, PUSHER_KEY, PUSHER_SECRET`. You can create a free
Pusher account or use the existing Pusher staging account which has no other
purpose currently. In the longer term, a better fix is to refactor the relevant
tests to mock the external service.

### AfricasTalking Sandbox

AfricasTalking provides a testing sandbox to simulate their services and APIs.
To test against these services:

1. Set `MUTE_SMS = False` and `IP_AUTHORIZATION = False` in .env.
2. Set `at_username` to `sandbox` and `at_api_key` properties in the database on `Client` model.
   Ask for the api key from your admin

   ```
      from core.models import Client
      c = Client.objects.get(name='ishamba')

      c.at_username = 'sandbox'
      c.at_api_key = '<<the_long_at_sandbox_api_key>>'
   ```

3. Install [ngrok app](https://ngrok.com/download) and launch it with: `ngrok http 8000`
4. Go to the [AT sandbox SMS callbacks website](https://account.africastalking.com/apps/sandbox/sms/dlr/callback)
   and paste the following URL, replacing the ngrok domain portion with the one generated
   above when you launched ngrok. E.g. `https://abc123xyz.ngrok.io/gateways/africastalking/delivery-report/`
4. Launch the [AT phone simulator](https://simulator.africastalking.com:1517/).
   Enter the phone number of a customer _**in your development database**_ that you would like to
   use for testing and who is allowed to receive SMS messages.
5. In a browser tab, open the local [ngrok inspector](http://localhost:4040/inspect/http)
6. Ensure a celery worker is running: `celery -A ishamba worker -E --loglevel DEBUG`
7. Optionally run flower for monitoring celery workers: `celery -A ishamba flower --port=5566`
8. Optionally open [flower local web port](http://localhost:5566/)
9. Ensure that rabbitmq is running. E.g. `brew services start rabbitmq` or `sudo systemctl start rabbitmq`
10. `./manage.py runserver 7000`
11. Open the [bulk_sms composition page](http://localhost:7000/management/bulk_sms/).
    Enter the phone number from the customer you selected above and configured in the AT phone simulator.
12. Send an sms message to this customer.
13. Confirm that the AT phone simulator received the sms.
14. Confirm that your local server received the delivery notification from
    the AfricasTalking sandbox server.
15. If there are issues, the ngrok inspector opened above can be useful
    for debugging payloads, replaying delivery reports, etc.

_TODO: Get calls working from the sandbox_
___

## Django apps overview

### Agri

Stores `Region`, and `Commodity` models. It also contains the
***deprecated*** `AgriTipSMS` model and the outdated functionality for
sending weekly agri-tips SMS messages.

### Calls

Contains the call centre Angular app, the Django `Call` model, and API views
needed for the call centre app.

### Core

Contains some widely used utility functions, the [django-import-export][]
classes for regular imports of market price data, and one-off imports via
management commands, some base classes and widgets, etc.

Imports via the Django admin site are defined in each app's admin module, but
as they depend on resources defined in the core app, they are described here.

#### Customer CSV import

This can be used for importing new customers or updating existing customers.
Customers are identified by phone number. To define whether existing customers
can be updated, see this setting: `settings.CUSTOMER_IMPORT_PERMIT_UPDATE`.

Basic fields on the model are just plain imported. Boolean fields should use a
value of `1` or `0` or `True` or `False`. Many-to-many fields and foreign-key fields
can use either ids or names. Many-to-many fields should use a quoted, comma-separated
list, e.g. `"3,11"`.

Market and Tip subscriptions and County Forecasts are imported separately.

Specific interesting customer fields include:

* 'commodities': we only import one field of commodities, which becomes the
  customer's initial commodities (farmed) field.
* 'categories': a many-to-many relationship to
  `customers.models.CustomerCategory`.
* 'farm_size': valid options are found in
  `customers.models.Customer.FARM_SIZE_CHOICES`, and are decimal numbers
  marking the lower-limit of an interval, e.g. `0.75`.
* 'location': a quoted, comma-separated, decimal longitude-latitude pair, e.g.
  `"35.2697611,0.5107284"`.

Example import data:

```csv
name,sex,phones,village,country,county,subcounty,ward,agricultural_region,preferred_language,farm_size,notes,is_registered,has_requested_stop,location,commodities,categories,market_id
Jimbo Jones,m,'+254714571022,,Kenya,Nairobi,Kibra,Makina,Rift Valley,eng,5,some notes,TRUE,FALSE,"35.2697611,0.5107284",Maize,acre africa,12
```

#### Market subscription CSV import

Customers are identified by their phone number, and multiple rows should be used
to describe multiple subscriptions. #TODO: Use customer_id instead.

Currently this import only supports validation on the `dry_run` step of the
import process, which means that it does not stop imports that add more than
the customers usage limit, unless the customer has already reached their limit
before the import.

Example import data:

```csv
customer_phone,market_id,backup_market_id
+2547000000001,1,2
+2547000000001,20,5
+2547000000007,12,3
```

### Commodities

`agri.models.Commodity` objects may be either livestock or crops. This
model is used for both `TipSeries` and `MarketPriceSubscription` to
determine what information is to be sent to subscribers.

Livestock Tips are stored without regions assigned, and the same set of
tips is sent to subscribers anywhere in Kenya. Crop Tips can be different by
County.

Commodities may be event-based (also called 'epoch-based'), or
calendar-based. If they are calendar-based, then the Tip that is
retrieved is dependent on the current [ISO week date][] week number, using
`date.isocalendar()` (note the issues with this around the start of the year,
and the function `core.utils.datetime.first_day_of_iso_week_date_year(date)`).
If they are event-based, then a subscription to this commodity must have an
epoch date set, and the Tip retrieved will be based on the relative delta
in weeks of the current date from the epoch date.

[ISO week date]: http://en.wikipedia.org/wiki/ISO_week_date

### Customers

Contains models for `Customer`, `CustomerCategory`, `CustomerPhone`,
`Subscription`, and `SubscriptionType` as well as several other `Customer`
related models.

`Customer` has some useful model methods and custom manager `Querysets`
defined. E.g.:

* `Customer.objects.should_receive_messages()`
* `Customer.objects.should_receive_tips()`
* `Customer.objects.can_access_call_centre()`
* `Customer.objects.subscribed(date=None)`
* `customer.should_receive_messages`
* `customer.can_access_call_centre`

### Digifarm ***deprecated***

Contains the code for integrating with Safaricom's Digifarm platform.

### Exports ***deprecated***

Provided a view for exporting customers, incoming messages and heat maps. This
functionality was determined to be a PII security issue, so removed. A future
enhancement will enable administrators to generate such exports, but have them
emailed and logged / flagged appropriately.

### Interrogation

Provides a state machine USSD engine that integrations with AfricasTalking
and can collect various details from customers such as location, crops and
livestock, gender, etc.

The architecture consists of the following components:
1. ussd_handler view that accepts the http POSTs and sets up the sessions
2. SessionManager: When a USSD session is started, the SessionManager is responsible for asking each of the registered Directors to bid on whether they need to interrogate this customer. The highest bidder wins.
3. InterrogationSession: A pickle'able object that stores the state of the interrogation between USSD sessions. Intended to survive reboots.
4. Directors: Conduct the actual interrogation, calling Interrogators in sequence, depending on their design.
5. Interrogators: Each interrogator is designed to capture specific data from the user by asking one or more questions, parsing the answers, and storing the data.

Note that the interrogation engine can be used to conduct USSD surveys. It uses the combination of
the BaseSurveyDirector, SurveyMenuInterrogator and others to conduct the survey. The SurveyMenuInterrogator
reads the survey questions from a structure in the Director class and stores the results in a JSON
structure in the CustomerSurvey table in the database. To activate a survey, the engine compares the
survey_title from the URL callback from AT against the survey_title in the subclasses of BaseSurveyDirector.


### Markets

Contains the `Market`, `MarketPrice`, and `MarketPriceMessage` models. These
are used in conjunction with `markets.delivery.MarketPriceSender` and a
collection of celery tasks (see `markets.delivery.tasks`) to deliver market prices
to `Customer`s on a weekly basis.

### Payments ***deprecated***

The `payments` module contains `VerifyInStoreOffer` which is no longer used.
`VerifyInStoreOffer` was used to create voucher codes for redemption in-store
(and verification via text message or call) which were in turn used to provide
discounts/offers on a partner's products/services.

The module also includes `FreeSubscriptionOffer`, however, it has not been
updated to work with the new style subscriptions.

### SMS

Contains the `IncomingSMS` and `OutgingSMS` models.
The submodule `sms.api` has code for sending and receiving SMS
messages. See [Sending SMS](#sending-sms) for more on this.

### Subscriptions

The `Subscription` model is used to track the number of `TipSeriesubscription`
and `MarketSubscription` instances a `Customer` is allowed. The
allowances that a given `Subscription` affords are defined by the
`SubscriptionType` associated with the `Subscription`.

All customers are associated with a `Subscription` with the type set to
`SubscriptionType(name='Free', is_permanent=True)`. Note that `is_permanent`
will mean that the associated `Subscription` will never be counted as expired.

Currently additional subscriptions (beyond the universal free subscription)
are manually allocated via the admin.

There are a number of manager methods provided. In the following examples
`date=None` defaults to the current date:

* `Subscription.objects.active(date=None)`
* `Subscription.objects.potent(date=None)` returns a `QuerySet` of
  subscriptions which end after the given date, i.e. which are either active
  now, or due to be active in the future (used for extending a customer's
  membership: we want to add the new subscription to the end of their
  latest-ending one)
* `Subscription.objects.latest_by_customer()` currently unused, but attempts to
  do something similar
* `Subscription.objects.get_usage_allowance('agri_tips')` aggregates allowances
  for the given allowance code across the subscriptions. Most useful when used
  via the reverse relationship on `Customer`, i.e.:
  `customer.subscriptions.get_usage_allowance('markets')`
* `Subscription.objects.count_usage_allowances()` aggregates all the allowances
  for the given subscriptions and returns a `dict`. Again, most useful when
  used via the reverse relationship on `Customer`.

### Tasks

Contains the `Task` and `TaskUpdate` which allow the organising of call centre
tasks. Do not confuse this with Celery tasks, which share the same name. By
convention, source files named tasks.py are typically for celery tasks, not this app.

### Tips

Contains the `Tip`, `TipSeries`, `TipSeriesSubscription` and `TipSent` models
that provide a more generic and flexible mechanism for sending tips to
customers than the old/_**deprecated**_ `AgriTip` approach.

### USSD Handler ***deprecated***

Exposed USSD service that were used as part of supporting _**deprecated**_ Digifarm.

### Weather

#### Current Functionality

The weather app contains `CountyForecast`. Each instance of this model contains
a single forecast to be sent to customers within a county. The `CountyForecast`
can also only be sent to customers within a `CustomerCategory` as well as
only those with a Premium `Subscription`. By default, forecasts are sent
to all categories, but only to premium subscribers.

#### _**Deprecated**_ Functionality

A weather forecast is retrieved and stored as `ForecastDay` objects, which
relate to a given location (the world partitioned into 5-arc-minute 'boxes')
on a given day. The retrieved forecast data is stored in the JSON field,
`.json`.

The sub-module `api.awhere` contains code specific to the former integration
with the aWhere service, including:

* function `format_weather_forecast_text(forecastdays)` to return a text string
  from a queryset of `ForecastDay` objects (this lives in this sub-module as
  the JSON field structure is presumed to be provider-specific),
* function `create_awhere_box_for_location(point)` to create and determine the
  boundaries of the aWhere 'box' around a given location, so we can group
  customers by weather area,
* code to communicate with the API

All of the above have lots more in the docstrings. The aWhere documentation is
not easy to find ([link][awhere_documentation]), and not easy to navigate.

[awhere_documentation]: http://help.awhere.com/AWhere%20Help%20Files/InSite/API_Weather/Introduction.htm

### World

The world app contains the `Border` and `BorderName` models. The `Border` model
is a public table containing multiple levels of administrative boundaries for
each country we operate in, and includes geo multipolygon shapes for area.

---

## Sending SMS

To send an SMS, create an instance of `OutgoingSMS`, and then call its `.send()`
method. It then handles the calling of `SMSGateway.send_message()`.

`SMSGateway.send_message()` partitions the list of recipients into batches
(configured in `sms.constants.AT_BATCH_SIZE`) and will make a request with the
`enqueue` flag set if the list is longer than 100 recipients (configured in
`sms.constants.AT_ENQUEUE_THRESHOLD`). In this latter case, the remote API will
respond with a 'Success' status immediately for all recipients, rather than
waiting until sending has been performed. We can optionally configure a
callback for updating sending status, but at the time of writing this has not
been done (see [below][#sms-status-callback]).

By default a `OutgoingSMS` instance will not allow sending to international
numbers (i.e. outside of Kenya); use the keyword argument `allow_international=True`
to override this. Nor will it allow itself to be sent to anyone who has already
received this same message. To send a repeat message to a recipient, create a
second instance. (This aspect is used in the various weekly SMS sending scripts,
to guard against spamming customers if the function is run twice within a short
period.)

In tests we frequently use mock to patch `SMSGateway.send_message()`. If this is
not done, the inadvertent sending of SMS messages is prevented by `SEND_SMS = False`
in local settings everywhere apart from on the production server.
---

## Call Centre

The call centre app is written in AngularJS (<https://angularjs.org/>, not <https://angular.io/>).
The main app structure can be seen in `calls/static/calls/call_center_app.js`.

Incoming calls are received via AfricasTalking making HTTP requests to
`calls.views.VoiceApiCallbackView`. Access to this view is IP-restricted to
just the AfricasTalking servers. The many methods on this view determine how
an incoming call is handled by the application.

The presence of calls in the queue, and of operators (CCOs) in the call centre
is communicated with front-end clients via Pusher. Code for processing these
events is in `members_controller.js` and `in_call_controller.js`. The files
`call_centre_directives.js`, `call_centre_services.js` and
`in_call_controller.js` contain much of the front-end code for displaying an
incoming call, while the Django API CBVs are declared in `calls.api` and
`calls.serializers`.

### Local development

To mock events in the call centre requires a connection to Pusher,
externally-visible endpoints (via [ngrok]), and local mocking of API calls
(via management commands).

[ngrok]: https://ngrok.com/

Using our Pusher account's staging channel. It is important that this is in the United
States server cluster, and that the app details are set in the `Client`
object in the database:

```
from core.models import Client
c = Client.objects.get(name='ishamba')

c.pusher_app_id = '<<the_pusher_app_id_number>>'
c.pusher_key = '<<the_long_pusher_key_string>>'
c.pusher_secret = 'the_long_pusher_secret_string'
```

In one shell run the development server, then in another shell, run the
following commands. Note that if you want to set breakpoints in your IDE, be sure
to run the server (not the callmock command) in debug mode in your IDE.

#### Simple call response checking

NOTE: _ngrok is not needed for this._

To make an incoming call, from +254 20 000001:

```bash
python manage.py callmock -f  '+25420000001'
```

To hang up:

```bash
python manage.py callmock -f  '+25420000001' -a hang
```

The response you see will be different depending on whether the caller is new
(never before been subscribed), a lapsed subscriber, or an active subscriber.

#### Call queue

It is possible to run the following `callmock` commands without setting up ngrok.
However, you will only see the XML response output in the terminal. To see realtime
results in the call queue in the browser, however, you _must_ use ngrok.

Download and extract ngrok if you don't have it set up.

To open an ngrok tunnel on your machine, in a new terminal `cd` to the
extracted folder or where you have set up ngrok and run:

```bash
./ngrok http 7000
```

or

```bash
./ngrok http <app port number>
```

Set the Pusher app's webhook to the ngrok subdomain assigned to your channel.
This README used to say that the url should have "/calls/" appended, but this
does not seem necessary. E.g. <http://87ae40fd883a.ngrok.io/>

Add the IP address for your ngrok subdomain to the AUTHORIZED_IPS list.

Create a `calls.models.CallCenterPhone` object, with `is_active=True`
(e.g. `+25420000002`).

Sign in to the call centre with the `CallCenterPhone` number just created
`http://localhost:7000/calls/` (If you have the Pusher debug console open in
a browser, you can follow these events). Check the box for `Connect anyway` and
click the `OK` button to connect.

Make the call from the customer:

```bash
python manage.py callmock -f  '+25420000001'
```

This should appear in the call queue without needing to refresh the page.

Make the dequeue-instruction call, from +254 20 000002:

```bash
python manage.py callmock -f  '+25420000002' -a dequeue
```

You will see nothing at this stage, but the provided id of the incoming call
from the operator will now be stored in the attribute
`PusherSession.provided_call_id`, and in the terminal the response should
include the XML tag `<Dequeue phoneNumber="{{ settings.CALL_QUEUE_NUMBER }}">`

Now fake the 'dequeue confirmation' request from the telecoms provider:

```bash
python manage.py callmock -f  '+25420000001' -a dequeue_ok -d '+25420000002'
```

(You will see that the POST data doesn't include the CCO's phone number, but
does include the `sessionId` mentioned previously). You should now be in the
in-call screen in the browser.

You can terminate each call in the same way as previously:

```bash
python manage.py callmock -f '+25420000001' -a hang
python manage.py callmock -f '+25420000002' -a hang
```

---

## Incoming SMS

Incoming SMS is received via HTTP requests made to
`sms.api.views.incoming_sms_callback()`. Access to this view is IP-restricted
to AfricasTalking servers.

Currently an `IncomingSMS` object is created, and all processing takes place
in methods on that object. This needs to change, see
[Incoming SMS processing](#incoming-sms-processing).

### Local development

To mock incoming SMS, use the `smsmock` management command.

In one shell run the development server, then in another shell, run the
following commands.

To fake receiving an SMS from +254 20 000001 saying "JOIN":

```bash
python manage.py smsmock -f '+25420000001' -t 'JOIN'
```

To change the sent-to number also:

```bash
python manage.py smsmock -f '+25420000001' -n 21606 -t 'JOIN'
```

---

## Periodic tasks ([Celery beat](http://docs.celeryproject.org/en/latest/userguide/periodic-tasks.html))

iShamba performs the following on a weekly basis:

* _**deprecated**_ : Sends market prices / combined market price and weather forecast SMSs
* Checks whether there are new KenyaMet weather forecasts to send via SMS
* Sends Tip SMSs

These jobs are scheduled using [Periodic Celery Tasks][]. For specific
schedule details see `ishamba/settings/production.py`.

[Periodic Celery Tasks]: http://docs.celeryproject.org/en/latest/userguide/periodic-tasks.html

### _**Deprecated**_ Market prices and Weather Forecasts

* `markets.tasks.send_scheduled_market_prices(include_weather=False)`
* `weather.tasks.send_weather_forecasts(exclude_prices_recipients=True)`

#### Weather-specific details

Weather forecast sending is broken up into three parts:

* `send_weather_forecasts()` which creates separate tasks for each county:
* `send_weather_forcast` which sends the pre-imported forecast to the relevant
   customers, optionally for only those in a `CustomerCagegory` or only premium
   `Subscription` customers.

#### Market-price-specific details

Market prices are not currently send, and need to be rewritten to include `Commodity`.
Generally, they are sent weekly via
`markets.tasks.send_scheduled_market_prices()`.

The main body of the sending code can be found in the `MarketPriceSender`
class. `MarketPriceSender.send_messages()` dispatches a
`markets.tasks.send_market_price_sms()` task to send the message as an OutgoingSMS.
---

## Vouchers

There are two ways that customers can use vouchers to get discounts.

### _**Deprecated**_ : FreeSubscriptionOffer workflow

1. Create an `Offer` in the front-end, specifying _n_ free months, generate a
   number of offer codes, download a csv of offer codes, and distribute them by
   [sneakernet][].
1. Customers then SMS the code only, e.g. "A7XFLD" back to the application.
1. If they have never before subscribed, we first create a subscription for 1
   month (or whatever the value of `customers.constants.FREE_MONTHS`), tell
   the customer that we will call them soon, and create a `Task` instance
   scheduling that call from a CCO.
1. We add _n_ months to the end date of their latest-ending still-potent
   subscription, or if they are a lapsed subscriber, add a brand new _n_-month
   subscription, and tell the customer that we have added this time too.

[sneakernet]: http://en.wikipedia.org/wiki/Sneakernet "Wikipedia: Sneakernet"

### VerifyInStoreOffer

1. Create an `Offer` instance in the front-end, specifying an outgoing-message
   template and a confirmation message.
2. Send the offer to customers via the bulk SMS message filter and send form.
3. Customers take the code to a shop.
4. Shop keepers text the code back to the application, and we respond with the
   confirmation message.

### Offer usage

In both of the above cases, the voucher is marked as used during the response
process. A CSV can be downloaded showing all vouchers created so far and the
customers who used them.
---

## Customer Activity

iShamba uses [django-activity-stream](https://github.com/justquick/django-activity-stream) to
record various actions performed by a customer and/or customer care agent. All
actions consist of an `actor`
(the customer in this case) and a `verb` (what the customer did). The action can
also have a `target` (to whom or what the action was done) and/or an
`action_object` (the object used to perform the action). If an action is done on
behalf of the customer by a site admin, then the admin's user id is to be recorded
as `[action data](http://django-activity-stream.readthedocs.io/en/latest/data.html)`
under the key `agent_id` (since the admin is acting on the customer's behalf,
they are their agent). This can be resolved to an object wherever it is required.

Actions are generally recorded after a model is saved, but [they can be recorded
anywhere](http://django-activity-stream.readthedocs.io/en/latest/actions.html).
Each model that is going to be part of an action has to be registered and we do
this in the model app's `AppConfig`. See `[sms.apps.SMSConfig](sms/apps.py)` for
an example.

The actions are displayed as a stream in the Customer's detail view. Each action
type is rendered using its own template. When you record a new action, you will
also need to define a template that will be used to render it in the detail view.
All this is done in `customers.tables.ActivityStreamTable`.
