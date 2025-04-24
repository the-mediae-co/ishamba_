from unittest import skip
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import BLANK_CHOICE_DASH
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now

from django_tenants.test.client import TenantClient as Client

from callcenters.models import CallCenter, CallCenterOperator
from core.test.cases import TestCase
from customers.models import Customer, CustomerPhone
from customers.tests.factories import CustomerFactory
from gateways.africastalking.testing import activate_success_response
from sms.models import OutgoingSMS, SMSRecipient
from sms.tests.factories import IncomingSMSFactory, OutgoingSMSFactory
from world.models import Border

from ..models import Task, TaskUpdate
from .factories import TaskFactory


class TaskThreadCreationTest(TestCase):

    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(name='TaskThreadCreationTest')
        self.phone = CustomerPhone(number='+25420882270', is_main=True, customer=self.customer)
        self.description = "This is a dummy task."
        self.task_source = self.customer

    def test_task_thread_creation(self):
        try:
            Task.objects.create(customer=self.customer,
                                description=self.description,
                                source=self.task_source,
                                priority=Task.PRIORITY.low)
        except Exception:
            self.fail("Task creation raised an error unexpectedly.")

    def test_new_task_has_new_status(self):
        task = Task.objects.create(customer=self.customer,
                                   description=self.description,
                                   source=self.task_source,
                                   priority=Task.PRIORITY.low)
        self.assertEqual(task.status, Task.STATUS.new)

    def test_that_a_task_thread_can_be_created_with_any_source(self):
        """
        """
        pass


class TaskUpdateTests(TestCase):

    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(name='TaskUpdateTests')
        self.phone = CustomerPhone(number='+25420882270', is_main=True, customer=self.customer)
        self.description = "This is a dummy task."
        self.task = Task.objects.create(customer=self.customer,
                                        description=self.description,
                                        source=self.customer,
                                        priority=Task.PRIORITY.low)

    def tearDown(self):
        for model in [Customer]:
            model.objects.all().delete()

    def test_newly_created_saveable_if_contain_message(self):
        try:
            new_update = TaskUpdate.objects.create(
                task=self.task,
                message='I\'m looking into it.'
            )
        except Exception:
            self.fail("TaskUpdate creation raised an error unexpectedly.")
        self.assertEqual(new_update.status, self.task.status)

    def test_newly_created_tasks_do_not_change_status(self):
        new_update = TaskUpdate(task=self.task)  # NB not create
        self.assertEqual(new_update.status, self.task.status)

    @skip("Removed this check from the TaskUpdate model for now.")
    def test_no_taskupdate_created_if_no_message_or_change_to_status(self):
        tu_count = TaskUpdate.objects.count()
        with self.assertRaises(ValidationError):
            TaskUpdate.objects.create(task=self.task)
        self.assertEqual(tu_count, TaskUpdate.objects.count())


class TaskTestCase(TestCase):
    def setUp(self):
        super().setUp()
        User = get_user_model()

        self.operator = User.objects.create_user(username='test',
                                                 password='testing123')

        self.customer = Customer.objects.create(name='TaskTestCase')
        self.phone = CustomerPhone(number='+25420123456', is_main=True, customer=self.customer)

        self.TASK_ATTRS = {
            'priority': Task.PRIORITY.low,
            'status': Task.STATUS.new,
            'customer': self.customer,
            'source': self.customer,
            'last_editor_id': self.operator.id,
        }

        self.empty_task = Task.objects.create(**self.TASK_ATTRS)

    def test_can_tag_task(self):
        self.empty_task.tags.add('test-tag')
        self.assertEqual(len(self.empty_task.tags.all()), 1)

    def test_updating_status_triggers_action(self):
        self.empty_task.status = Task.STATUS.closed_resolved
        self.empty_task.save()
        self.empty_task.refresh_from_db()

        action = self.empty_task.target_actions.filter(verb='changed').first()
        self.assertEqual(action.data['field'], 'status')
        self.assertEqual(action.data['initial'], Task.STATUS.new)
        self.assertEqual(action.data['final'], Task.STATUS.closed_resolved)

    def test_updating_priority_triggers_action(self):
        self.empty_task.priority = Task.PRIORITY.high
        self.empty_task.save()
        self.empty_task.refresh_from_db()

        action = self.empty_task.target_actions.filter(verb='changed').first()
        self.assertEqual(action.data['field'], 'priority')
        self.assertEqual(action.data['initial'], Task.PRIORITY.low)
        self.assertEqual(action.data['final'], Task.PRIORITY.high)

    def test_updating_tags_triggers_action(self):
        self.empty_task.tags.add('test-tag')
        tag_action = self.empty_task.target_actions.filter(verb='tagged').first()
        self.assertEqual(tag_action.data['tags'], ['test-tag'])

        self.empty_task.tags.remove('test-tag')
        untag_action = self.empty_task.target_actions.filter(verb='untagged').first()
        self.assertEqual(untag_action.data['tags'], ['test-tag'])

    def test_updating_assignees_triggers_action(self):
        self.empty_task.assignees.add(self.operator)
        assigned_action = self.empty_task.target_actions.filter(verb='assigned').first()
        self.assertEqual(assigned_action.action_object, self.operator)

        self.empty_task.assignees.remove(self.operator)
        unassigned_action = self.empty_task.target_actions.filter(verb='unassigned').first()
        self.assertEqual(unassigned_action.action_object, self.operator)

    def test_incoming_sms_triggers_action(self):
        sms = IncomingSMSFactory()
        self.empty_task.incoming_messages.add(sms)

        action = self.empty_task.target_actions.filter(verb='sent').first()
        self.assertEqual(action.action_object, sms)
        self.assertEqual(action.timestamp, sms.at)

    def test_outgoing_sms_triggers_action(self):
        sms = OutgoingSMSFactory(sent_by=self.operator, time_sent=now())
        self.empty_task.outgoing_messages.add(sms)

        action = self.empty_task.target_actions.filter(verb='sent').first()
        self.assertEqual(action.action_object, sms)
        self.assertEqual(action.timestamp, sms.time_sent)


class CannotContactTests(TestCase):

    def setUp(self):
        super().setUp()
        User = get_user_model()

        self.operator = User.objects.create_user(username='test',
                                                 password='testing123')
        self.task = TaskFactory(last_editor_id=self.operator.pk)

    def test_count_is_incremented(self):
        self.task.add_cannot_contact_customer_update(self.operator)
        self.task.save(user=self.operator)
        self.task.refresh_from_db()
        self.assertEqual(self.task.contact_attempts, 1)
        self.task.add_cannot_contact_customer_update(self.operator)
        self.task.save(user=self.operator)
        self.task.refresh_from_db()
        self.assertEqual(self.task.contact_attempts, 2)

    @activate_success_response
    @patch('tasks.models.get_populated_sms_templates_text')
    def test_send_sms_on_n_attempt(self, mocked_sms_message):
        mocked_sms_message.return_value = 'contact failed', '21606'
        failures = 5

        with override_settings(CONTACT_CUSTOMER_FAILURES_BEFORE_SMS=failures):
            # For n-1 times we shouldn't send a message
            for i in range(failures - 1):
                self.task.add_cannot_contact_customer_update(self.operator)
                self.task.save(user=self.operator)
                self.task.refresh_from_db()
            # For the n-th time we should send a message
            self.task.add_cannot_contact_customer_update(self.operator)
            self.task.save(user=self.operator)
            self.assertEqual(1, OutgoingSMS.objects.count())
            self.assertEqual(1, SMSRecipient.objects.count())
            sms = OutgoingSMS.objects.first()
            self.assertEqual(sms.text, 'contact failed')
            self.assertIn(sms, self.task.outgoing_messages.all())

    def test_attempt_creates_action(self):
        self.task.add_cannot_contact_customer_update(self.operator)
        self.task.save(user=self.operator)

        actions = self.task.target_actions.filter(verb='contact_failed')
        self.assertEqual(actions.count(), 1)
        action = actions.first()
        self.assertEqual(action.data['field'], 'contact_attempts')
        self.assertEqual(action.data['attempt'], 1)


class TestTaskListViews(TestCase):

    def setUp(self):
        super().setUp()
        self.client = Client(self.tenant)
        User = get_user_model()

        self.operator = User.objects.create_user('foo', password='foo')
        self.call_center = CallCenter.objects.get(border=Border.objects.get(country='Kenya', level=0))
        self.call_center_operator = CallCenterOperator.objects.create(operator=self.operator, active=True, call_center=self.call_center)
        self.client.login(username='foo', password='foo')

        self.test_customer_1 = CustomerFactory()
        self.test_customer_2 = CustomerFactory()

        self.tasks = [
            TaskFactory(last_editor_id=self.operator.pk, customer=self.test_customer_1, status=Task.STATUS.new),
            TaskFactory(last_editor_id=self.operator.pk, status=Task.STATUS.progressing),
            TaskFactory(last_editor_id=self.operator.pk, priority='medium', status=Task.STATUS.progressing),
            TaskFactory(last_editor_id=self.operator.pk, status=Task.STATUS.closed_resolved),
            TaskFactory(last_editor_id=self.operator.pk, status=Task.STATUS.closed_unresolved),
            TaskFactory(last_editor_id=self.operator.pk, priority='low'),
            TaskFactory(last_editor_id=self.operator.pk, priority='high', customer=self.test_customer_2),
            TaskFactory(last_editor_id=self.operator.pk, priority='critical'),
        ]

    def test_task_factory(self):
        self.assertEqual(self.tasks[0].customer, self.test_customer_1)
        self.assertEqual(8, len(self.tasks))

    def test_customer_list_renders_correct_template(self):
        response = self.client.get(reverse('task_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/tasks.html', 'tasks/task_list.html'], response.template_name)

    def test_task_list_renders_customer(self):
        response = self.client.get(reverse('task_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.test_customer_1.id)

    def test_customer_list_renders_all_open_tasks(self):
        response = self.client.get(reverse('task_list'))
        self.assertEqual(response.status_code, 200)
        for task in self.tasks:
            if task.status in (Task.STATUS.new, Task.STATUS.progressing):
                self.assertContains(response, task.customer.id)
            else:
                self.assertNotContains(response, task.customer.id)

    def test_task_list_sorts_open_tasks_by_priority(self):
        response = self.client.get(reverse('task_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.test_customer_1.id)
        task_list = response.context_data.get('current_page_data')
        # Tasks should be displayed in sequence by date
        offset = 0  # only non-closed tasks are displayed
        for index in range(0, len(self.tasks)):
            if not self.tasks[index].status in ('closed_resolved', 'closed_unresolved'):
                self.assertEqual(self.tasks[index], task_list[index - offset])
            else:
                offset += 1
        self.assertEqual(len(self.tasks) - 2, len(task_list))  # Ensure all (and only) open tasks are displayed

    def test_task_list_filters_priority(self):
        response = self.client.get(reverse('task_list'), data={'priority': 'high'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.test_customer_2.id)
        task_list = response.context_data.get('current_page_data')
        self.assertEqual(1, len(task_list))  # Ensure only the high priority task is displayed

    def test_task_list_filters_blank_priority(self):
        response = self.client.get(reverse('task_list'), data={'priority': BLANK_CHOICE_DASH[0][1]})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.test_customer_1.id)
        task_list = response.context_data.get('current_page_data')
        # Tasks should be displayed in sequence by date
        for index in range(0, len(self.tasks)):
            self.assertEqual(self.tasks[index], task_list[index])
        self.assertEqual(len(self.tasks), len(task_list))  # Ensure all tasks are displayed

    def test_task_list_filters_status(self):
        response = self.client.get(reverse('task_list'), data={'status': 'new'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.test_customer_1.id)
        task_list = response.context_data.get('current_page_data')
        # Ensure only the new tasks are displayed. Note that if a status is not specified, new is assumed
        self.assertEqual(4, len(task_list))

    def test_task_list_filters_all(self):
        response = self.client.get(reverse('task_list'), data={'status': 'all'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.test_customer_1.id)
        task_list = response.context_data.get('current_page_data')
        # Ensure only the new tasks are displayed. Note that if a status is not specified, new is assumed
        self.assertEqual(len(self.tasks), len(task_list))

    def test_task_list_filters_all_open(self):
        response = self.client.get(reverse('task_list'), data={'status': 'open'})
        self.assertEqual(response.status_code, 200)
        task_list = response.context_data.get('current_page_data')
        # Ensure only the new tasks are displayed. Note that if a status is not specified, new is assumed
        for task in self.tasks:
            if task.status in (Task.STATUS.new, Task.STATUS.progressing):
                self.assertContains(response, task.customer.id)
            else:
                self.assertNotContains(response, task.customer.id)

    def test_task_list_filters_all_closed(self):
        response = self.client.get(reverse('task_list'), data={'status': 'closed'})
        self.assertEqual(response.status_code, 200)
        task_list = response.context_data.get('current_page_data')
        # Ensure only the new tasks are displayed. Note that if a status is not specified, new is assumed
        for task in self.tasks:
            if task.status in (Task.STATUS.closed_resolved, Task.STATUS.closed_unresolved):
                self.assertContains(response, task.customer.id)
            else:
                self.assertNotContains(response, task.customer.id)
