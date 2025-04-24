import django.dispatch

# signal triggered when delivery reports are received from SMS gateways
delivery_report_received = django.dispatch.Signal()
