import logging
import pickle

from customers.models import CustomerSurvey
from interrogation.counties import get_county_options
from django.conf import settings
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from interrogation.interface import Director
from interrogation.models import InterrogationSession
from interrogation.session_manager import SessionManager
from interrogation.tasks import send_survey_email_via_celery
from ipware import get_client_ip

LOGGER = logging.getLogger(__name__)


def ussd_handler(request: HttpRequest, survey_title: str = "") -> HttpResponse:
    if getattr(settings, "IP_AUTHORIZATION", True):
        client_ip, _ = get_client_ip(request)
        if client_ip not in settings.AUTHORIZED_IPS:
            LOGGER.warning(f"Access attempt from non-whitelisted IP: {client_ip}")
            return HttpResponseForbidden()

    qd = request.POST or request.GET
    phone_number = qd.get("phoneNumber", None)
    if survey_title:
        session_type = InterrogationSession.SessionType.SURVEY.value
    else:
        session_type = InterrogationSession.SessionType.REGISTRATION.value

    session: InterrogationSession = (
        InterrogationSession.objects.filter(phone=phone_number, session_type=session_type).order_by("-created").first()
    )
    if session is None or session.finished or timezone.now() - session.last_updated > timezone.timedelta(days=7):
        session = InterrogationSession(phone=phone_number, session_type=session_type)
        mgr = SessionManager()
    else:
        mgr = pickle.loads(session.session_mgr)
        assert isinstance(mgr, SessionManager)

    response = mgr.handler(request, survey_title)
    session.finished = mgr.is_finished()
    session.session_mgr = pickle.dumps(mgr)
    session.save()
    return response

@login_required
def surveys_list(request: HttpRequest):
    surveys = [dc.survey_title for dc in Director.registry if hasattr(dc, "survey_title")]
    return render(request, "interrogation/surveys_list.html", {"surveys_list": surveys})

@login_required
def survey_detail(request: HttpRequest, survey_title: str):
    # Get filters from request
    age_filter = request.GET.get("age")
    county_filter = request.GET.get("county")
    sex_filter = request.GET.get("sex")

    county_options = get_county_options()

    director = next(dc() for dc in Director.registry if getattr(dc, "survey_title", None) == survey_title)
    headers = ["Customer", "Phone Number", "Survey Started", "Survey Finished"] + [
        q[0] for q in director.questions if q[0] not in director.hidden
    ]

    # Filter customer surveys based on filters
    customer_surveys = CustomerSurvey.objects.filter(survey_title=survey_title, finished_at__isnull=False, responses__Sex__isnull=False)

    if age_filter:
        customer_surveys = customer_surveys.filter(responses__Age=age_filter)
    if county_filter and county_filter != "None":
        customer_surveys = customer_surveys.filter(responses__County=county_filter)
    if sex_filter:
        customer_surveys = customer_surveys.filter(responses__Sex=sex_filter)

    total_respondents = customer_surveys.count()

    paginator = Paginator(customer_surveys, 30)
    page_number = request.GET.get('page', 1)
    try:
        customer_surveys_page = paginator.page(page_number)
    except PageNotAnInteger:
        customer_surveys_page = paginator.page(1)
    except EmptyPage:
        customer_surveys_page = paginator.page(paginator.num_pages)

    survey_data = [
        [cs.customer.id, cs.customer.formatted_phone, cs.created, cs.finished_at] + [cs.responses.get(header) for header in headers[4:]]
        for cs in customer_surveys_page
    ]

    # Retrieve selected records from session
    selected_records = request.session.get('selected_records', [])

    # Add selected records to context
    context = {
        "survey_data": survey_data,
        "headers": headers,
        "survey_title": survey_title,
        "export_formats": ["xlsx", "csv"],
        "customer_surveys": customer_surveys,
        "total_respondents": total_respondents,
        "page_obj": customer_surveys_page,
        "selected_records": selected_records,
        "selected_records_count": len(selected_records),
        "county_options": county_options,
    }

    if request.method == 'POST':
        export_format = request.POST.get('export-format', 'csv')
        selected_records = request.POST.getlist('selected_records')

        # Store selected records in session
        request.session['selected_records'] = selected_records

        send_survey_email_via_celery.delay(
                request.user.email,
                survey_title,
                headers,
                selected_records=list(selected_records),
                export_format=export_format
        )

        return JsonResponse({'success': True, 'user_email': request.user.email})

    return render(request, "interrogation/survey_detail.html", context)
