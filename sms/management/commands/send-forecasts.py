import argparse
import csv
import datetime
import re
import time
import math

from django.core.management.base import BaseCommand
from django.db import connection
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from django_tenants.management.commands import InteractiveTenantOption

from customers.models import Customer
from sms.models.outgoing import OutgoingSMS
from sms.constants import KENYA_COUNTRY_CODE, UGANDA_COUNTRY_CODE, OUTGOING_SMS_TYPE
from sms.tasks import send_message
from world.models import Border


class Command(BaseCommand, InteractiveTenantOption):
    help = 'Send PlantVillage weather forecast SMS messages'

    # Usage: ./manage.py send-forecasts -t -v1 -f forecasts.csv -s ishamba -d 2

    # csv file column headers
    BORDER3_COLUMN_TITLE = "border_id"

    def add_arguments(self, parser: argparse.ArgumentParser):

        parser.add_argument("-d", "--delay", dest="delay_hours",
                            type=int, default=0, help="hours to delay before sending")
        parser.add_argument('-f', '--forecasts', required=True,
                            type=argparse.FileType('r'), help='group forecasts file')
        parser.add_argument("-s", "--schema", dest="schema_name",
                            help="tenant schema", default="ishamba")
        parser.add_argument("-sw", "--swahili", dest="swa_msg", action='store',
                            help="Swahili message to append")
        parser.add_argument("-en", "--english", dest="eng_msg", action='store',
                            help="English message to append")
        parser.add_argument("-t", "--test", dest="test_run", action='store_true',
                            help="test run: no sms messages are sent")
        # parser.add_argument("-v", "--verbose", action="count", default=0,
        #                     help="increase output verbosity")

    def handle(self, *args, **options):

        # Track performance for summary report
        tic = time.perf_counter()

        tenant = self.get_tenant_from_options_or_interactive(**options)
        connection.set_tenant(tenant)

        delay_hours = options['delay_hours']
        verbosity = options['verbosity']
        test_run = options['test_run']
        input_file = options['forecasts']
        swa_msg = options['swa_msg']
        eng_msg = options['eng_msg']

        include_spei = False

        csv_reader = csv.reader(input_file, delimiter=',', quotechar='"')

        # Preflight the file contents to make sure forecasts exist for all wards
        row_counter = 0
        for row in csv_reader:
            row_counter += 1
            if len(row) < 3:
                raise ValidationError(f"Row {row_counter} does not contain full data: {row}")
            if row[2] is None or len(row[2]) == 0:
                raise ValidationError(f"Row {row_counter} does not contain a rain forecast: {row}")

        # Now go back to the beginning and do the real work
        input_file.seek(0)
        column_headers = next(csv_reader)

        # Raises ValueError if not found
        b3_column = column_headers.index(self.BORDER3_COLUMN_TITLE)
        nearterm_column = None
        spei_column = None

        forecast_endstr = 'in the next 7 days'
        nearterm_pattern = re.compile('^202\d\d\d\d\d_(202\d\d\d\d\d)')
        spei_pattern = re.compile('^SPEI_')
        col_index = -1
        nearterm_found = False
        spei_found = False
        for col in column_headers:
            col_index += 1
            if match := nearterm_pattern.match(col):
                nearterm_column = col_index
                nearterm_found = True
                matchstr = match.groups(1)[0]
                forecast_enddate = datetime.datetime.strptime(matchstr, '%Y%m%d')
                forecast_endstr = 'from now to ' + datetime.datetime.strftime(forecast_enddate, '%d %b')
            elif spei_pattern.match(col):
                spei_column = col_index
                spei_found = True

        if not nearterm_found:
            raise ValidationError("Forecast column not found")
        if not spei_found:
            raise ValidationError("SPEI column not found")

        task_kwargs = {}
        if delay_hours:
            eta = timezone.localtime(timezone.now()) + datetime.timedelta(hours=delay_hours)  # Delay message delivery by N hours
            task_kwargs = {'eta': eta}

        page_counts = {'digifarm': 0}
        msg_counts = {'digifarm': 0}
        longest_message_size = 0
        longest_message = ""
        total_page_count = 0
        total_msg_count = 0

        medium_spei_risk = 39
        high_spei_risk = 69

        verylarge_threshold = 100
        large_threshold = 50

        for row in csv_reader:
            b3_id = int(row[b3_column])
            nearterm_forecast = round(float(row[nearterm_column]))
            if row[spei_column]:
                raw_spei_risk = float(row[spei_column])
                spei_risk = round(-(raw_spei_risk * 100))
            else:
                spei_risk = 0

            # Find all customers who have not requested stop and are in this ward
            customers = Customer.objects.filter(has_requested_stop=False, border3_id=b3_id)

            # Either digifarm or Only customers with valid phone numbers in the countries in which we operate.
            customers = customers.filter(
                Q(phones__number__startswith=f"+{KENYA_COUNTRY_CODE}") |
                Q(phones__number__startswith=f"+{UGANDA_COUNTRY_CODE}") |
                Q(digifarm_farmer_id__isnull=False)
            )
            digifarm_count = customers.filter(digifarm_farmer_id__isnull=False).count()
            msg_counts['digifarm'] += digifarm_count

            try:
                b3_obj = Border.objects.get(country__in=['Kenya', 'Uganda'], level=3, pk=b3_id)
                b3_name = b3_obj.name
                country_name = b3_obj.country
                if country_name == 'Kenya':
                    sender = 'iShamba'
                    # sender = '21606'
                elif country_name == 'Uganda':
                    sender = '6115'
                else:
                    sender = None
                    raise ValueError(f"ERROR invalid country for border3: {b3_id}")

                # Seed the page_counts and msg_counts keys
                if country_name not in page_counts:
                    page_counts[country_name] = 0
                if country_name not in msg_counts:
                    msg_counts[country_name] = 0

            except Border.DoesNotExist as e:
                b3_name = None
                raise ValueError(f"ERROR querying border3: {b3_id}")

            if verbosity >= 2:
                print(f"Border3 {b3_name} [{b3_id}], sending {nearterm_forecast} to {len(customers)} customers")

            langs = customers.order_by('preferred_language').distinct('preferred_language').values_list('preferred_language', flat=True)
            for lang in langs:
                # Seed the lang keys
                if lang not in page_counts:
                    page_counts[lang] = 0
                if lang not in msg_counts:
                    msg_counts[lang] = 0

                msg = ""
                lang_customers = customers.filter(preferred_language=lang).distinct('id')

                if lang == 'lug':
                    # msg += f"Okuva Nuru: "
                    msg += f"Faamu yo {b3_name.title()} eteberezebwa "
                    if nearterm_forecast > verylarge_threshold:
                        msg += f"okufuna ekuba nyinji nyo ({nearterm_forecast}mm) "
                    elif nearterm_forecast > large_threshold:
                        msg += f"okufuna ekuba nyinji ({nearterm_forecast}mm) "
                    elif nearterm_forecast == 0:
                        msg += f"obutafuna nkuba "
                    elif nearterm_forecast < 5:
                        msg += f"okufuna ekuba ntono nyo ({nearterm_forecast}mm) "
                    else:
                        msg += f"nkuba ({nearterm_forecast}mm) "

                    msg += f"okuva kati okutuuka {datetime.datetime.strftime(forecast_enddate, '%d %b')}."

                    if include_spei:
                        if spei_risk > high_spei_risk:
                            msg += f" Waliwo obulabe obutono obulabe bw'ekyeya sizoni eno."
                        elif spei_risk > medium_spei_risk:
                            msg += f" Waliwo obulabe obulabe bw'ekyeya sizoni eno."
                        # elif spei_risk > 0:
                        #     msg += "Waliwo obulabe obw'amanyi obulabe bw'ekyeya sizoni eno."

                elif lang == 'swa':
                    # msg += f"iShamba&Nuru:"
                    if len(b3_name) > 10:
                        msg += f"{b3_name.title()} kunatabiriwa "
                    else:
                        msg += f"Shamba lako la {b3_name.title()} linatabiriwa "
                    if nearterm_forecast > verylarge_threshold:
                        msg += f"mvua kubwa zaidi ({nearterm_forecast}mm) "
                    elif nearterm_forecast > large_threshold:
                        msg += f"mvua kubwa ({nearterm_forecast}mm) "
                    elif nearterm_forecast == 0:
                        msg += f"kutopekea mvua "
                    elif nearterm_forecast < 5:
                        msg += f"kupokea mvua kidogo zaidi ({nearterm_forecast}mm) "
                    else:
                        msg += f"mvua ({nearterm_forecast}mm) "

                    msg += f"kuanzia sasa hadi {datetime.datetime.strftime(forecast_enddate, '%d %b')}."

                    #if nearterm_forecast > 0:
                    #    msg += f" Huu ndio wakati mzuri wa kupanda mimea."

#                    if b3_obj.parent.parent.name in ('Mombasa', 'Kilifi', 'Kwale', 'Tana River', 'Lamu', 'Taita Taveta'):
#                        msg += f" Panda na uvune maji ya mvua."
#                    else:
#                        # msg += f" Palilia mimea na uvune maji ya mvua."
#                        msg += f' Kagua uwepo wa wadudu na magonjwa kwenye mimea shambani.'

#                    end_long = f' Endelea kuondoa magugu, udhibiti wadudu, na vune maji ya mvua.'
#                    end_short = f' Ondoa magugu, dhibiti wadudu, na vune maji.'
#
#                    if len(msg) + len(end_long) <= 160:
#                        msg += end_long
#                    elif len(msg) + len(end_short) > 160:
#                        msg += end_long
#                    else:
#                        msg += end_short

                    if include_spei:
                        if spei_risk > high_spei_risk:
                            spei_risk_term = "hatari kubwa"
                        elif spei_risk > medium_spei_risk:
                            spei_risk_term = "hatari"
                        elif spei_risk > 0:
                            spei_risk_term = "hatari ndogo"

                        if spei_risk > medium_spei_risk:
                            msg += f" Kuna {spei_risk_term} ya ukame msimu huu."
                    if swa_msg:
                        msg += f' {swa_msg}'

                else:  # Default to English
                    # msg += "iShamba&Nuru:"

                    if nearterm_forecast > verylarge_threshold:
                        rainfall_term = "very heavy rainfall"
                    elif nearterm_forecast > large_threshold:
                        rainfall_term = "heavy rainfall"
                    elif nearterm_forecast < 5:
                        rainfall_term = "very little rain"
                    else:
                        rainfall_term = "rain"

                    if include_spei:
                        if spei_risk > high_spei_risk:
                            spei_risk_term = " high"
                        elif spei_risk > medium_spei_risk:
                            spei_risk_term = ""
                        else:
                            spei_risk_term = " low"
                    if b3_name:
                        if len(b3_name) > 10:
                            b3_str = f" in {b3_name.title()}"
                        else:
                            b3_str = f" for your shamba in {b3_name.title()}"
                    else:
                        b3_str = ""

                    if int(nearterm_forecast) == 0:
                        msg += f"We predict no rain{b3_str} {forecast_endstr}."
                    else:
                        msg += f"We predict {rainfall_term} ({nearterm_forecast}mm){b3_str} {forecast_endstr}."

                    #if nearterm_forecast > 0:
                    #    msg += f" This is the right time for planting."

#                    if b3_obj.parent.parent.name in ('Mombasa', 'Kilifi', 'Kwale', 'Tana River', 'Lamu', 'Taita Taveta'):
#                        msg += f" Plant & harvest rainwater."
#                    else:
                        # msg += f" Weed and harvest rainwater."
#                        msg += f' Scout for pests and diseases in the farm.'

#                    end_long = f' Continue removing weeds, controlling pests, and harvesting water.'
#                    end_short = f' Remove weeds, control pests, and harvest water.'
#
#                    if len(msg) + len(end_long) <= 160:
#                        msg += end_long
#                    elif len(msg) + len(end_short) > 160:
#                        msg += end_long
#                    else:
#                        msg += end_short

                    if include_spei:
                        if spei_risk > medium_spei_risk:
                            msg += f" There is a{spei_risk_term} risk of drought this season."

                    if eng_msg:
                        msg += f' {eng_msg}'

                if len(msg) > 320:
                    raise ValidationError(f"msg too long: {len(msg)} {msg}")
                elif len(msg) == 0:
                    raise ValidationError(f"Trying to send an empty msg")

                longest_message = msg if len(msg) > longest_message_size else longest_message
                longest_message_size = len(msg) if len(msg) > longest_message_size else longest_message_size

                customers_count = lang_customers.count()
                lang_digifarm_count = lang_customers.filter(digifarm_farmer_id__isnull=False).count()
                # It is possible to receive forecasts for farmers for whom has_requested_stop==True
                if customers_count > 0:
                    try:
                        if not test_run:
                            sms, created = OutgoingSMS.objects.get_or_create(
                                text=msg,
                                message_type=OUTGOING_SMS_TYPE.WEATHER_PLANTVILLAGE,
                            )
                            send_message.apply_async([sms.id, list(lang_customers.values_list('id', flat=True))], {'sender': sender}, **task_kwargs)
                        page_counts[country_name] += customers_count * math.ceil(float(len(msg)) / 160)
                        page_counts[lang] += customers_count * math.ceil(float(len(msg)) / 160)
                        total_page_count += customers_count * math.ceil(float(len(msg)) / 160)
                        page_counts['digifarm'] += lang_digifarm_count * math.ceil(float(len(msg)) / 160)
                        msg_counts[country_name] += customers_count
                        msg_counts[lang] += customers_count
                        total_msg_count += customers_count

                        if verbosity:
                            print(msg)
                            print(f"{country_name} Counters: {msg_counts[country_name]} msgs, {page_counts[country_name]} pages")
                    except ValidationError as e:  # e.g. invalid phone numbers
                        print(f"ValidationError {e}: {list(lang_customers.values_list('id', flat=True))}")
                        # For now, skip the batch and continue. TODO: Implement partial retry.
                        pass

        toc = time.perf_counter()

        total_msgs = 0
        total_pages = 0
        print("\nSUMMARY:")
        for c in page_counts.keys():
            print(f"\t{c}: {msg_counts[c]} messages ({page_counts[c]} pages) sent in {toc - tic:0.1f} seconds")
            if c == 'digifarm':
                continue
            if len(c) > 3: # Don't count languages
                total_pages += page_counts[c]
                total_msgs += msg_counts[c]
        print(f"\tTOTAL: {total_msg_count} messages ({total_page_count} pages) sent in {toc - tic:0.1f} seconds")
        print(f"\tMaximum message length = {longest_message_size}: {longest_message}")
        if total_msgs != total_msg_count:
            print(f"ERROR: total_pages != total_page_count: {total_msgs}, {total_msg_count}")
        if total_pages != total_page_count:
            print(f"ERROR: total_pages != total_page_count: {total_pages}, {total_page_count}")
