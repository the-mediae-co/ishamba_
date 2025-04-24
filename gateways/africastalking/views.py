from logging import getLogger

from gateways.views import BaseDeliveryReportView
from sms.views import BaseIncomingSMSView

from .forms import ATDeliveryReportForm, ATIncomingSMSForm
from .gateway import AfricasTalkingGateway

logger = getLogger(__name__)


class ATIncomingSMSView(BaseIncomingSMSView):
    form = ATIncomingSMSForm
    gateway = AfricasTalkingGateway


class ATDeliveryReportView(BaseDeliveryReportView):
    form = ATDeliveryReportForm
    gateway = AfricasTalkingGateway
