from unittest import skip

from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.urls import reverse

from django_tenants.test.client import TenantClient as Client
from taggit.models import Tag

from callcenters.models import CallCenter, CallCenterOperator, CallCenterSender
from core.test.cases import TestCase
from customers.tests.factories import CustomerFactory, CustomerPhoneFactory
from gateways.africastalking.testing import activate_success_response
from digifarm.testing import activate_success_response as df_activate_success_response
from sms.models import OutgoingSMS, SMSRecipient
from world.models import Border

from ..forms import TaskBulkUpdateForm, TaskUpdateForm
from ..models import Task, TaskUpdate
from .factories import TaskFactory
from django.test import override_settings


class TaskUpdateFormTests(TestCase):

    def setUp(self):
        super().setUp()
        user = get_user_model()
        self.operator = user.objects.create_user('foo', password='foo')
        self.client = Client(self.tenant)
        self.client.login(username='foo', password='foo')

        self.test_customer_1 = CustomerFactory()
        self.test_customer_2 = CustomerFactory()

        self.tasks = [
            TaskFactory(customer=self.test_customer_1, status=Task.STATUS.new, priority=Task.PRIORITY.low),
            TaskFactory(status=Task.STATUS.progressing),
            TaskFactory(priority='medium', status=Task.STATUS.progressing),
            TaskFactory(last_editor_id=self.operator.pk, status=Task.STATUS.closed_resolved),
            TaskFactory(status=Task.STATUS.closed_unresolved),
            TaskFactory(priority='low'),
            TaskFactory(priority='high', customer=self.test_customer_2),
            TaskFactory(priority='critical'),
        ]

    def test_setup(self):
        # Ensure the DB has our records stored
        self.assertEqual(len(self.tasks), Task.objects.count())
        self.assertEqual(0, TaskUpdate.objects.count())

    def test_form_change_raises_no_validation_error(self):
        task = self.tasks[0]
        form = TaskUpdateForm(self.tasks[0], {'customer': self.test_customer_2.id,
                                              'status': task.status,
                                              'priority': task.priority})
        # There's no assertNotRaises, so I just call the is_valid()
        # method. If an exception is raised, the test will fail.
        self.assertTrue(form.is_valid())

    def test_invalid_status_raises_validation_error(self):
        task = self.tasks[0]
        form = TaskUpdateForm(self.tasks[0], {'customer': task.customer.id,
                                              'status': ('gloobertyfoo'),
                                              'priority': task.priority})
        self.assertFalse(form.is_valid())

    def test_invalid_priority_raises_validation_error(self):
        task = self.tasks[0]
        form = TaskUpdateForm(self.tasks[0], {'customer': task.customer.id,
                                              'status': task.status,
                                              'priority': ('gloobertyfoo')})
        self.assertFalse(form.is_valid())

    def test_logged_out_get_taskupdate_redirect(self):
        self.client.logout()
        task = self.tasks[0]
        response = self.client.get(reverse('task_update', args=[task.id]),
                                   follow=True)
        self.assertRedirects(response, f"/accounts/login/?next=%2Ftasks%2Fupdate%2F{task.id}%2F",
                             status_code=302, target_status_code=200)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)

    def test_logged_in_get_taskupdate_renders(self):
        task = self.tasks[0]
        response = self.client.get(reverse('task_update', args=[task.id]),
                                   follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/task_update.html'], response.template_name)
        self.assertContains(response, f"Task: #{task.id}")
        self.assertContains(response, f"{task.id} Task description")

    def test_logged_out_post_taskupdate_redirect(self):
        self.client.logout()
        task = self.tasks[0]
        response = self.client.post(reverse('task_update', args=[task.id]),
                                    {'status': 'closed_resolved'},
                                    follow=True)
        self.assertRedirects(response, f"/accounts/login/?next=%2Ftasks%2Fupdate%2F{task.id}%2F",
                             status_code=302, target_status_code=200)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)

    def test_logged_in_post_taskupdate_updates(self):
        task = self.tasks[0]
        last_updated = task.last_updated
        last_editor_id = task.last_editor_id
        tag_a = Tag.objects.create(name='a')
        response = self.client.post(reverse('task_update', args=[task.id]),
                                    {'customer': task.customer.id,
                                     'status': Task.STATUS.closed_resolved,
                                     'priority': Task.PRIORITY.medium,
                                     'assignees': [self.operator.id],
                                     'tags': [tag_a.id]},
                                    follow=True)
        # Make sure the user sees what they're supposed to
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/task_update.html'], response.template_name)
        self.assertContains(response, f"Task: #{task.id}")
        self.assertContains(response, f"{task.id} Task description")
        # Make sure Task record changed properly in the DB
        task.refresh_from_db()
        self.assertEqual(self.tasks[0].customer.id, task.customer.id)
        self.assertEqual(Task.STATUS.closed_resolved, task.status)
        self.assertEqual(Task.PRIORITY.medium, task.priority)
        self.assertGreater(task.last_updated, last_updated)
        self.assertEqual(self.operator.id, task.last_editor_id)
        self.assertTrue(self.operator in task.assignees.all())
        self.assertTrue(tag_a in task.tags.all())
        self.assertEqual(1, task.assignees.count())
        self.assertEqual(1, task.tags.count())
        # Make sure the TaskUpdate object was created correctly
        self.assertEqual(1, TaskUpdate.objects.count())
        tu = TaskUpdate.objects.first()
        self.assertEqual(Task.STATUS.closed_resolved, tu.status)
        self.assertEqual(self.operator.id, tu.creator_id)
        self.assertEqual(self.operator.id, tu.last_editor_id)

    def test_logged_in_post_taskupdate_removes_tags_and_assignees(self):
        task = self.tasks[0]
        last_updated = task.last_updated
        last_editor_id = task.last_editor_id
        tag_a = Tag.objects.create(name='a')
        task.assignees.add(self.operator)
        task.tags.add(tag_a)
        response = self.client.post(reverse('task_update', args=[task.id]),
                                    {'customer': task.customer.id,
                                     'status': Task.STATUS.closed_resolved,
                                     'priority': Task.PRIORITY.medium,
                                     'assignees': [],
                                     'tags': []},
                                    follow=True)
        # Make sure the user sees what they're supposed to
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/task_update.html'], response.template_name)
        self.assertContains(response, f"Task: #{task.id}")
        self.assertContains(response, f"{task.id} Task description")
        # Make sure Task record changed properly in the DB
        task.refresh_from_db()
        self.assertEqual(self.tasks[0].customer.id, task.customer.id)
        self.assertEqual(Task.STATUS.closed_resolved, task.status)
        self.assertEqual(Task.PRIORITY.medium, task.priority)
        self.assertGreater(task.last_updated, last_updated)
        self.assertEqual(self.operator.id, task.last_editor_id)
        self.assertFalse(self.operator in task.assignees.all())
        self.assertFalse(tag_a in task.tags.all())
        self.assertEqual(0, task.assignees.count())
        self.assertEqual(0, task.tags.count())
        # Make sure the TaskUpdate object was created correctly
        self.assertEqual(1, TaskUpdate.objects.count())
        tu = TaskUpdate.objects.first()
        self.assertEqual(Task.STATUS.closed_resolved, tu.status)
        self.assertEqual(self.operator.id, tu.creator_id)
        self.assertEqual(self.operator.id, tu.last_editor_id)

    def test_logged_in_post_no_status_change_updates_task_creates_no_taskupdate(self):
        task = self.tasks[0]
        last_updated = task.last_updated
        last_editor_id = task.last_editor_id
        response = self.client.post(reverse('task_update', args=[task.id]),
                                    {'customer': task.customer.id,
                                     'status': task.status,
                                     'priority': Task.PRIORITY.medium,
                                     'assignees': self.operator.id},
                                    follow=True)
        # Make sure the user sees what they're supposed to
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/task_update.html'], response.template_name)
        self.assertContains(response, f"Task: #{task.id}")
        self.assertContains(response, f"{task.id} Task description")
        # Make sure Task record changed properly in the DB
        task.refresh_from_db()
        self.assertEqual(self.tasks[0].customer.id, task.customer.id)
        self.assertEqual(self.tasks[0].status, task.status)
        self.assertEqual(Task.PRIORITY.medium, task.priority)
        self.assertGreater(task.last_updated, last_updated)
        self.assertEqual(self.operator.id, task.last_editor_id)
        self.assertTrue(self.operator in task.assignees.all())
        self.assertEqual(1, task.assignees.count())
        # Make sure no TaskUpdate object was created
        self.assertEqual(0, TaskUpdate.objects.count())

    def test_logged_in_empty_post_does_not_update_records(self):
        task = self.tasks[0]
        last_updated = task.last_updated
        last_editor_id = task.last_editor_id
        response = self.client.post(reverse('task_update', args=[task.id]),
                                    {},
                                    follow=True)
        # Make sure the user sees what they're supposed to
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/task_update.html'], response.template_name)
        self.assertContains(response, f"Task: #{task.id}")
        self.assertContains(response, f"{task.id} Task description")
        # Make sure Task record changed properly in the DB
        task.refresh_from_db()
        self.assertEqual(self.tasks[0].customer.id, task.customer.id)
        self.assertEqual(self.tasks[0].status, task.status)
        self.assertEqual(self.tasks[0].priority, task.priority)
        self.assertEqual(last_updated, task.last_updated)
        self.assertEqual(last_editor_id, task.last_editor_id)
        self.assertTrue(self.operator not in task.assignees.all())
        self.assertEqual(0, task.assignees.count())
        # Make sure a TaskUpdate was not created
        self.assertEqual(0, TaskUpdate.objects.count())

    def test_logged_in_mirror_post_does_not_update_records(self):
        task = self.tasks[0]
        last_updated = task.last_updated
        last_editor_id = task.last_editor_id
        response = self.client.post(reverse('task_update', args=[task.id]),
                                    {'customer': task.customer.id,
                                     'status': task.status,
                                     'priority': task.priority},
                                    follow=True)
        # Make sure the user sees what they're supposed to
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/task_update.html'], response.template_name)
        self.assertContains(response, f"Task: #{task.id}")
        self.assertContains(response, f"{task.id} Task description")
        # Make sure Task record did not change in the DB
        task.refresh_from_db()
        self.assertEqual(self.tasks[0].customer.id, task.customer.id)
        self.assertEqual(self.tasks[0].status, task.status)
        self.assertEqual(self.tasks[0].priority, task.priority)
        self.assertEqual(last_updated, task.last_updated)
        self.assertEqual(last_editor_id, task.last_editor_id)
        self.assertTrue(self.operator not in task.assignees.all())
        self.assertEqual(0, task.assignees.count())
        # Make sure a TaskUpdate object was not created
        self.assertEqual(0, TaskUpdate.objects.count())

    def test_logged_in_invalid_status_post_raises_exception(self):
        task = self.tasks[0]
        last_updated = task.last_updated
        last_editor_id = task.last_editor_id
        response = self.client.post(reverse('task_update', args=[task.id]),
                                    {'customer': task.customer.id,
                                     'status': 'gloobertyfoo',
                                     'priority': task.priority},
                                    follow=True)
        # Make sure the user sees what they're supposed to
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/task_update.html'], response.template_name)
        self.assertContains(response, f"Task: #{task.id}")
        self.assertContains(response, f"Select a valid choice. gloobertyfoo is not one of the available choices")
        # Make sure Task record did not change in the DB
        task.refresh_from_db()
        self.assertEqual(self.tasks[0].customer.id, task.customer.id)
        self.assertEqual(self.tasks[0].status, task.status)
        self.assertEqual(self.tasks[0].priority, task.priority)
        self.assertEqual(last_updated, task.last_updated)
        self.assertEqual(last_editor_id, task.last_editor_id)
        self.assertTrue(self.operator not in task.assignees.all())
        self.assertEqual(0, task.assignees.count())
        # Make sure a TaskUpdate object was not created
        self.assertEqual(0, TaskUpdate.objects.count())

    def test_logged_in_invalid_priority_post_raises_exception(self):
        task = self.tasks[0]
        last_updated = task.last_updated
        last_editor_id = task.last_editor_id
        response = self.client.post(reverse('task_update', args=[task.id]),
                                    {'customer': task.customer.id,
                                     'status': task.status,
                                     'priority': 'gloobertyfoo'},
                                    follow=True)
        # Make sure the user sees what they're supposed to
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/task_update.html'], response.template_name)
        self.assertContains(response, f"Task: #{task.id}")
        self.assertContains(response, f"Select a valid choice. gloobertyfoo is not one of the available choices")
        # Make sure Task record did not change in the DB
        task.refresh_from_db()
        self.assertEqual(self.tasks[0].customer.id, task.customer.id)
        self.assertEqual(self.tasks[0].status, task.status)
        self.assertEqual(self.tasks[0].priority, task.priority)
        self.assertEqual(last_updated, task.last_updated)
        self.assertEqual(last_editor_id, task.last_editor_id)
        self.assertTrue(self.operator not in task.assignees.all())
        self.assertEqual(0, task.assignees.count())
        # Make sure a TaskUpdate object was not created
        self.assertEqual(0, TaskUpdate.objects.count())


class TaskBulkUpdateFormTests(TestCase):

    def setUp(self):
        super().setUp()
        user = get_user_model()
        self.operator = user.objects.create_user('foo', password='foo')

        # Set-up CallCenters (TODO: should use factories)
        self.call_center = CallCenter.objects.get(border=Border.objects.get(country='Kenya', level=0))
        self.call_center_operator = CallCenterOperator.objects.create(operator=self.operator, active=True, call_center=self.call_center)
        self.call_center_sender = CallCenterSender.objects.create(sender_id="iShamba", description="blah")
        self.call_center.senders.add(self.call_center_sender)


        self.client = Client(self.tenant)
        self.client.login(username='foo', password='foo')

        self.test_customer_1 = CustomerFactory()
        self.test_customer_2 = CustomerFactory()
        # Make customer_2 a digifarm farmer
        self.test_customer_2.digifarm_farmer_id = 'abc123'
        phone2 = CustomerPhoneFactory(number="+4929951568174104", is_main=False, customer=self.test_customer_2)
        self.test_customer_2.save()

        self.tasks = [
            TaskFactory(customer=self.test_customer_1, status=Task.STATUS.new, priority=Task.PRIORITY.low),
            TaskFactory(customer=self.test_customer_2,status=Task.STATUS.progressing),
            TaskFactory(priority='medium', status=Task.STATUS.progressing),
            TaskFactory(last_editor_id=self.operator.pk, status=Task.STATUS.closed_resolved),
            TaskFactory(status=Task.STATUS.closed_unresolved),
            TaskFactory(priority='low'),
            TaskFactory(priority='high', customer=self.test_customer_2),
            TaskFactory(priority='critical'),
        ]

    def test_setup(self):
        # Ensure the DB has our records stored
        self.assertEqual(len(self.tasks), Task.objects.count())
        self.assertEqual(0, TaskUpdate.objects.count())

    def test_form_change_raises_no_validation_error(self):
        tasks = Task.objects.all()
        form = TaskBulkUpdateForm(tasks, {'bulk-tasks': tasks.values_list('pk', flat=True),
                                          'bulk-status': Task.STATUS.closed_resolved,
                                          'bulk-priority': Task.PRIORITY.high})
        # There's no assertNotRaises, so I just call the is_valid()
        # method. If an exception is raised, the test will fail.
        result = form.is_valid()
        self.assertTrue(result)

    def test_invalid_status_raises_validation_error(self):
        tasks = Task.objects.all()
        form = TaskBulkUpdateForm(tasks, {'bulk-tasks': tasks.values_list('pk', flat=True),
                                          'bulk-status': 'gloobertyfoo',
                                          'bulk-priority': Task.PRIORITY.high})
        result = form.is_valid()
        self.assertFalse(result)
        self.assertFalse('tasks' in form.errors)
        self.assertTrue('status' in form.errors)
        self.assertFalse('priority' in form.errors)

    def test_invalid_priority_raises_validation_error(self):
        tasks = Task.objects.all()
        form = TaskBulkUpdateForm(tasks, {'bulk-tasks': tasks.values_list('pk', flat=True),
                                          'bulk-status': Task.STATUS.closed_resolved,
                                          'bulk-priority': 'gloobertyfoo'})
        result = form.is_valid()
        self.assertFalse(result)
        self.assertFalse('tasks' in form.errors)
        self.assertFalse('status' in form.errors)
        self.assertTrue('priority' in form.errors)

    def test_logged_out_get_bulktaskupdate_redirect(self):
        self.client.logout()
        # A get request should just render the Task table, and make no modifications
        response = self.client.get(reverse('task_list'), follow=True)
        self.assertRedirects(response, f"/accounts/login/?next=%2Ftasks%2F",
                             status_code=302, target_status_code=200)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)

    def test_logged_in_get_taskupdate_renders(self):
        response = self.client.get(reverse('task_list'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/tasks.html', 'tasks/task_list.html'], response.template_name)
        # Ensure all non-closed Tasks are displayed
        for task in self.tasks:
            if task.status in (Task.STATUS.new, Task.STATUS.progressing):
                self.assertContains(response, task.description)
                self.assertContains(response, f"value=\"{task.id}\"")

    def test_logged_out_post_taskupdate_redirect(self):
        self.client.logout()
        tasks = Task.objects.all()
        response = self.client.post(reverse('task_list'),
                                    {'bulk-tasks': tasks.values_list('pk', flat=True),
                                     'bulk-status': Task.STATUS.closed_resolved,
                                     'bulk-priority': Task.PRIORITY.high},
                                    follow=True)
        self.assertRedirects(response, f"/accounts/login/?next=%2Ftasks%2F",
                             status_code=302, target_status_code=200)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['account/login.html'], response.template_name)

    def test_logged_in_post_taskupdate_updates(self):
        # Closed Tasks are not visible in the Task list, so cannot be selected.
        # The form validation logic enforces this.
        tasks = Task.objects.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing))
        response = self.client.post(reverse('task_list'),
                                    {'bulk-tasks': tasks.values_list('pk', flat=True),
                                     'bulk-status': Task.STATUS.progressing,
                                     'bulk-priority': Task.PRIORITY.medium,
                                     'bulk-assignees_add': self.operator.id,
                                     'update': 'Apply'},
                                    follow=True)
        # Make sure the user sees what they're supposed to
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/tasks.html', 'tasks/task_list.html'], response.template_name)
        for task in tasks.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing)):
            self.assertContains(response, task.description)
            self.assertContains(response, f"value=\"{task.id}\"")
        # Make sure Task record changed properly in the DB
        task_counter = 0
        for task in self.tasks:
            # Only tasks that were visible got through the form validation process and could be selected.
            # Note that priority, tag and assignee changes do not result in TaskUpdate object creation.
            # As a result, only tasks that had a status of 'new' were changed in this test.
            if task.status in (Task.STATUS.new):
                task_counter += 1
                db_task = Task.objects.get(pk=task.pk)
                self.assertEqual(task.customer.id, db_task.customer.id)
                self.assertEqual(Task.STATUS.progressing, db_task.status)
                self.assertEqual(Task.PRIORITY.medium, db_task.priority)
                self.assertGreater(db_task.last_updated, task.last_updated)
                self.assertEqual(self.operator.id, db_task.last_editor_id)
                self.assertTrue(self.operator in db_task.assignees.all())
                self.assertEqual(1, db_task.assignees.count())
                self.assertEqual(self.operator.id, db_task.assignees.first().id)
                # Make sure the TaskUpdate object was created correctly
                tu = TaskUpdate.objects.filter(task=task).first()
                self.assertEqual(Task.STATUS.progressing, tu.status)
                self.assertEqual(self.operator.id, tu.creator_id)
                self.assertEqual(self.operator.id, tu.last_editor_id)
        self.assertEqual(task_counter, TaskUpdate.objects.count())

    def test_logged_in_mirror_post_updates_records(self):
        # Closed Tasks are not visible in the Task list, but can be selected in the session_data.
        # The form validation logic should enable them to be updated.
        tasks = Task.objects.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing))
        task_ids = list(tasks.values_list('pk', flat=True))
        response = self.client.post(reverse('task_list'),
                                    {'bulk-tasks': task_ids,
                                     'bulk-priority': Task.PRIORITY.medium,
                                     'bulk-status': Task.STATUS.closed_resolved,
                                     'update': 'Apply'},
                                    follow=True)
        # Make sure the user sees what they're supposed to
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/tasks.html', 'tasks/task_list.html'], response.template_name)
        # Ensure the task list is displayed correctly without the closed tasks
        for task in Task.objects.filter(id__in=task_ids):
            self.assertNotContains(response, task.description)
            self.assertNotContains(response, f"value=\"{task.id}\"")
        # Make sure Task records were changed correctly in the DB
        self.assertEqual(0, Task.objects.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing)).count())
        for task in self.tasks:
            if task.id in task_ids:  # If it's a task that we modified
                db_task = Task.objects.get(pk=task.pk)
                self.assertEqual(task.customer.id, db_task.customer.id)
                self.assertEqual(task.STATUS.closed_resolved, db_task.status)
                self.assertEqual('medium', db_task.priority)
                self.assertGreater(db_task.last_updated, task.last_updated)
                self.assertEqual(self.operator.id, db_task.last_editor_id)
                self.assertTrue(self.operator not in db_task.assignees.all())
                self.assertEqual(0, db_task.assignees.count())
        # Make sure TaskUpdate objects were created
        self.assertEqual(len(task_ids), TaskUpdate.objects.count())

    def test_logged_in_empty_post_does_not_update_records(self):
        tasks = Task.objects.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing))
        # Post with values identical to the original tasks
        response = self.client.post(reverse('task_list'),
                                    {'bulk-tasks': tasks.values_list('pk', flat=True),
                                     'bulk-status': [],
                                     'bulk-priority': [],
                                     'bulk-assignees_add': [],
                                     'bulk-assignees_remove': [],
                                     'bulk-tags_add': [],
                                     'bulk-tags_remove': [],
                                     'update': 'Apply'},
                                    follow=True)
        # Make sure the user sees what they're supposed to
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/tasks.html', 'tasks/task_list.html'], response.template_name)
        for task in tasks.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing)):
            self.assertContains(response, task.description)
            self.assertContains(response, f"value=\"{task.id}\"")
        # Make sure Task record did not change in the DB
        for task in self.tasks:
            db_task = Task.objects.get(pk=task.pk)
            self.assertEqual(task.customer.id, db_task.customer.id)
            self.assertEqual(task.status, db_task.status)
            self.assertEqual(task.priority, db_task.priority)
            self.assertEqual(task.last_updated, db_task.last_updated)
            self.assertEqual(task.last_editor_id, db_task.last_editor_id)
            self.assertTrue(self.operator not in db_task.assignees.all())
            self.assertEqual(0, db_task.assignees.count())
        # Make sure a TaskUpdate object was no created
        self.assertEqual(0, TaskUpdate.objects.count())

    def test_logged_in_invalid_status_post_raises_exception(self):
        # Closed Tasks are not visible in the Task list, so cannot be selected.
        # The form validation logic enforces this.
        tasks = Task.objects.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing))
        response = self.client.post(reverse('task_list'),
                                    {'bulk-tasks': tasks.values_list('pk', flat=True),
                                     'bulk-status': 'gloobertyfoo',
                                     'bulk-priority': [],
                                     'update': 'Apply'},
                                    follow=True)
        # Make sure the user sees what they're supposed to
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/tasks.html', 'tasks/task_list.html'], response.template_name)
        for task in tasks.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing)):
            self.assertContains(response, task.description)
            self.assertContains(response, f"value=\"{task.id}\"")
        self.assertContains(response, f"Select a valid choice. gloobertyfoo is not one of the available choices")
        # Make sure Task record did not change in the DB
        for task in self.tasks:
            db_task = Task.objects.get(pk=task.pk)
            self.assertEqual(task.customer.id, db_task.customer.id)
            self.assertEqual(task.status, db_task.status)
            self.assertEqual(task.priority, db_task.priority)
            self.assertEqual(task.last_updated, db_task.last_updated)
            self.assertEqual(task.last_editor_id, db_task.last_editor_id)
            self.assertTrue(self.operator not in db_task.assignees.all())
            self.assertEqual(0, db_task.assignees.count())
        # Make sure a TaskUpdate object was no created
        self.assertEqual(0, TaskUpdate.objects.count())

    def test_logged_in_invalid_priority_post_raises_exception(self):
        # Closed Tasks are not visible in the Task list, so cannot be selected.
        # The form validation logic enforces this.
        tasks = Task.objects.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing))
        response = self.client.post(reverse('task_list'),
                                    {'bulk-tasks': tasks.values_list('pk', flat=True),
                                     'bulk-status': [],
                                     'bulk-priority': 'gloobertyfoo',
                                     'update': 'Apply'},
                                    follow=True)
        # Make sure the user sees what they're supposed to
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/tasks.html', 'tasks/task_list.html'], response.template_name)
        for task in tasks.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing)):
            self.assertContains(response, task.description)
            self.assertContains(response, f"value=\"{task.id}\"")
        self.assertContains(response, f"Select a valid choice. gloobertyfoo is not one of the available choices")
        # Make sure Task record did not change in the DB
        for task in self.tasks:
            db_task = Task.objects.get(pk=task.pk)
            self.assertEqual(task.customer.id, db_task.customer.id)
            self.assertEqual(task.status, db_task.status)
            self.assertEqual(task.priority, db_task.priority)
            self.assertEqual(task.last_updated, db_task.last_updated)
            self.assertEqual(task.last_editor_id, db_task.last_editor_id)
            self.assertTrue(self.operator not in db_task.assignees.all())
            self.assertEqual(0, db_task.assignees.count())
        # Make sure a TaskUpdate object was not created
        self.assertEqual(0, TaskUpdate.objects.count())

    def test_logged_in_add_tags_and_assignees_works(self):
        # Closed Tasks are not visible in the Task list, so cannot be selected.
        # The form validation logic enforces this.
        tasks = Task.objects.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing))
        tag_a = Tag.objects.create(name="a")
        tag_b = Tag.objects.create(name="b")
        user_a = User.objects.create(username="user_a")
        response = self.client.post(reverse('task_list'),
                                    {'bulk-tasks': tasks.values_list('pk', flat=True),
                                     'bulk-status': [],
                                     'bulk-priority': [],
                                     'bulk-assignees_add': [self.operator.id, user_a.id],
                                     'bulk-tags_add': [tag_a.id, tag_b.id],
                                     'update': 'Apply'},
                                    follow=True)
        # Make sure the user sees what they're supposed to
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/tasks.html', 'tasks/task_list.html'], response.template_name)
        for task in tasks.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing)):
            self.assertContains(response, task.description)
            self.assertContains(response, f"value=\"{task.id}\"")
        self.assertNotContains(response, f"Select a valid choice.")
        # Make sure each Task's record changed correctly in the DB
        for task in tasks:
            db_task = Task.objects.get(pk=task.pk)
            self.assertEqual(task.customer.id, db_task.customer.id)
            self.assertEqual(task.status, db_task.status)
            self.assertEqual(task.priority, db_task.priority)
            self.assertTrue(self.operator in db_task.assignees.all())
            self.assertTrue(user_a in db_task.assignees.all())
            self.assertEqual(2, db_task.assignees.count())
            self.assertTrue(tag_a in db_task.tags.all())
            self.assertTrue(tag_b in db_task.tags.all())
            self.assertEqual(2, db_task.tags.count())
        # Make sure a TaskUpdate object was not created (only created for status and priority changes)
        self.assertEqual(0, TaskUpdate.objects.count())

    def test_logged_in_remove_tags_and_assignees_works(self):
        # Closed Tasks are not visible in the Task list, so cannot be selected.
        # The form validation logic enforces this.
        tasks = Task.objects.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing))
        tag_a = Tag.objects.create(name="a")
        tag_b = Tag.objects.create(name="b")
        user_a = User.objects.create(username="user_a")
        for task in tasks:
            task.assignees.add(self.operator.id)
            task.assignees.add(user_a)
            task.tags.add(tag_a)
            task.tags.add(tag_b)

        response = self.client.post(reverse('task_list'),
                                    {'bulk-tasks': tasks.values_list('pk', flat=True),
                                     'bulk-status': [],
                                     'bulk-priority': [],
                                     'bulk-assignees_remove': [self.operator.id, user_a.id],
                                     'bulk-tags_remove': [tag_a.id, tag_b.id],
                                     'update': 'Apply'},
                                    follow=True)
        # Make sure the user sees what they're supposed to
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/tasks.html', 'tasks/task_list.html'], response.template_name)
        for task in tasks.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing)):
            self.assertContains(response, task.description)
            self.assertContains(response, f"value=\"{task.id}\"")
        self.assertNotContains(response, f"Select a valid choice.")
        # Make sure each Task's record changed correctly in the DB
        for task in tasks:
            db_task = Task.objects.get(pk=task.pk)
            self.assertEqual(task.customer.id, db_task.customer.id)
            self.assertEqual(task.status, db_task.status)
            self.assertEqual(task.priority, db_task.priority)
            self.assertFalse(self.operator in db_task.assignees.all())
            self.assertFalse(user_a in db_task.assignees.all())
            self.assertEqual(0, db_task.assignees.count())
            self.assertFalse(tag_a in db_task.tags.all())
            self.assertFalse(tag_b in db_task.tags.all())
            self.assertEqual(0, db_task.tags.count())
        # Make sure a TaskUpdate object was not created (only created for status and priority changes)
        self.assertEqual(0, TaskUpdate.objects.count())

    def test_logged_in_remove_non_tags_and_assignees_raises(self):
        # Closed Tasks are not visible in the Task list, so cannot be selected.
        # The form validation logic enforces this.
        tasks = Task.objects.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing))
        tag_a = Tag.objects.create(name="a")
        tag_b = Tag.objects.create(name="b")
        user_a = User.objects.create(username="user_a")
        for task in tasks:
            task.assignees.add(self.operator.id)
            task.tags.add(tag_a)

        response = self.client.post(reverse('task_list'),
                                    {'bulk-tasks': tasks.values_list('pk', flat=True),
                                     'bulk-status': [],
                                     'bulk-priority': [],
                                     'bulk-assignees_remove': [user_a.id],
                                     'bulk-tags_remove': [tag_b.id],
                                     'update': 'Apply'},
                                    follow=True)
        # Make sure the user sees what they're supposed to
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/tasks.html', 'tasks/task_list.html'], response.template_name)
        for task in tasks.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing)):
            self.assertContains(response, task.description)
            self.assertContains(response, f"value=\"{task.id}\"")
        self.assertContains(response, f"Select a valid choice. {tag_b.id} is not one of the available choices.")
        # Make sure each Task's record changed correctly in the DB
        for task in tasks:
            db_task = Task.objects.get(pk=task.pk)
            self.assertEqual(task.customer.id, db_task.customer.id)
            self.assertEqual(task.status, db_task.status)
            self.assertEqual(task.priority, db_task.priority)
            self.assertTrue(self.operator in db_task.assignees.all())
            self.assertFalse(user_a in db_task.assignees.all())
            self.assertEqual(1, db_task.assignees.count())
            self.assertTrue(tag_a in db_task.tags.all())
            self.assertFalse(tag_b in db_task.tags.all())
            self.assertEqual(1, db_task.tags.count())
        # Make sure a TaskUpdate object was not created (only created for status and priority changes)
        self.assertEqual(0, TaskUpdate.objects.count())

    def test_logged_in_add_remove_tags_and_assignees_works(self):
        # Closed Tasks are not visible in the Task list, so cannot be selected.
        # The form validation logic enforces this.
        tasks = Task.objects.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing))
        tag_a = Tag.objects.create(name="a")
        tag_b = Tag.objects.create(name="b")
        user_a = User.objects.create(username="user_a")
        for task in tasks:
            task.assignees.add(self.operator.id)
            task.tags.add(tag_a)

        response = self.client.post(reverse('task_list'),
                                    {'bulk-tasks': tasks.values_list('pk', flat=True),
                                     'bulk-status': [],
                                     'bulk-priority': [],
                                     'bulk-assignees_add': [user_a.id],
                                     'bulk-assignees_remove': [self.operator.id],
                                     'bulk-tags_add': [tag_b.id],
                                     'bulk-tags_remove': [tag_a.id],
                                     'update': 'Apply'},
                                    follow=True)
        # Make sure the user sees what they're supposed to
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/tasks.html', 'tasks/task_list.html'], response.template_name)
        for task in tasks.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing)):
            self.assertContains(response, task.description)
            self.assertContains(response, f"value=\"{task.id}\"")
        self.assertNotContains(response, f"Select a valid choice.")
        # Make sure each Task's record changed correctly in the DB
        for task in tasks:
            db_task = Task.objects.get(pk=task.pk)
            self.assertEqual(task.customer.id, db_task.customer.id)
            self.assertEqual(task.status, db_task.status)
            self.assertEqual(task.priority, db_task.priority)
            self.assertFalse(self.operator in db_task.assignees.all())
            self.assertTrue(user_a in db_task.assignees.all())
            self.assertEqual(1, db_task.assignees.count())
            self.assertTrue(tag_b in db_task.tags.all())
            self.assertFalse(tag_a in db_task.tags.all())
            self.assertEqual(1, db_task.tags.count())
        # Make sure a TaskUpdate object was not created (only created for status and priority changes)
        self.assertEqual(0, TaskUpdate.objects.count())

    def test_logged_in_add_remove_same_tags_and_assignees_fails(self):
        # Closed Tasks are not visible in the Task list, so cannot be selected.
        # The form validation logic enforces this.
        tasks = Task.objects.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing))
        tag_a = Tag.objects.create(name="a")
        tag_b = Tag.objects.create(name="b")
        user_a = User.objects.create(username="user_a")
        for task in tasks:
            task.assignees.add(self.operator.id)
            task.tags.add(tag_a)

        response = self.client.post(reverse('task_list'),
                                    {'bulk-tasks': tasks.values_list('pk', flat=True),
                                     'bulk-status': [],
                                     'bulk-priority': [],
                                     'bulk-assignees_add': [self.operator.id],
                                     'bulk-assignees_remove': [self.operator.id],
                                     'bulk-tags_add': [tag_a.id],
                                     'bulk-tags_remove': [tag_a.id],
                                     'update': 'Apply'},
                                    follow=True)
        # Make sure the user sees what they're supposed to
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/tasks.html', 'tasks/task_list.html'], response.template_name)
        for task in tasks.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing)):
            self.assertContains(response, task.description)
            self.assertContains(response, f"value=\"{task.id}\"")
        self.assertContains(response, f"You cannot add and remove the same tags: {tag_a.name}")
        self.assertContains(response, f"You cannot add and remove the same assignees: {self.operator.username}")
        # Make sure each Task's record changed correctly in the DB
        for task in tasks:
            db_task = Task.objects.get(pk=task.pk)
            self.assertEqual(task.customer.id, db_task.customer.id)
            self.assertEqual(task.status, db_task.status)
            self.assertEqual(task.priority, db_task.priority)
            self.assertTrue(self.operator in db_task.assignees.all())
            self.assertFalse(user_a in db_task.assignees.all())
            self.assertEqual(1, db_task.assignees.count())
            self.assertFalse(tag_b in db_task.tags.all())
            self.assertTrue(tag_a in db_task.tags.all())
            self.assertEqual(1, db_task.tags.count())
        # Make sure a TaskUpdate object was not created (only created for status and priority changes)
        self.assertEqual(0, TaskUpdate.objects.count())

    def test_logged_in_bulk_sms_compose_button_redirects(self):
        tasks = Task.objects.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing))
        response = self.client.post(reverse('task_list'),
                                    {'bulk-sms': 'bulk-sms',
                                     'bulk-tasks': tasks.values_list('pk', flat=True)},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response.template_name)

    @activate_success_response
    def test_logged_in_bulk_sms_compose_send_redirects_to_tasks(self):
        tasks = Task.objects.filter(status__in=(Task.STATUS.new, Task.STATUS.progressing))
        customer_ids = list(set(tasks.values_list('customer_id', flat=True)))

        session = self.client.session
        session['bulk_customer'] = {
            'form_data': customer_ids,
            'count': len(customer_ids),
            'success_url': 'task_list'
        }
        session.save()

        response = self.client.post(reverse('core_management_customer_bulk_compose'),
                                    {'text': 'floobertygoo',
                                     'senders': 'iShamba'},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['tasks/tasks.html', 'tasks/task_list.html'], response.template_name)

    def test_logged_in_bulk_sms_force_at_network_doesnt_filter(self):
        tasks = [self.tasks[0].pk, self.tasks[1].pk]  # User selects check boxes next to the first two tasks
        response = self.client.post(reverse('task_list'),
                                    {'bulk-sms': 'bulk-sms',  # Trigger the bulk-sms form actions
                                     'bulk-tasks': tasks},      # Selected tasks
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_rendered)
        self.assertEqual(['sms/bulk_sms_compose_form.html'], response.template_name)
        self.assertEqual(2, response.context_data.get('count'))  # Both customers have AT numbers
        self.assertRedirects(response, '/management/bulk_sms/compose/')
        self.assertContains(response, 'Compose bulk SMS for 2 Customers')

    @activate_success_response
    @df_activate_success_response
    @override_settings(ENABLE_DIGIFARM_INTEGRATION=True)
    def test_logged_in_bulk_sms_closes_task(self):
        task_ids = [self.tasks[0].pk, self.tasks[1].pk]
        tasks = [self.tasks[0], self.tasks[1]]
        pre_outgoing_messages_count0 = tasks[0].outgoing_messages.count()
        pre_outgoing_messages_count1 = tasks[1].outgoing_messages.count()
        pre_outgoingsms_count = OutgoingSMS.objects.count()
        pre_smsrecipient_count = SMSRecipient.objects.count()

        response1 = self.client.post(reverse('task_list'),
                                     {'bulk-sms': 'bulk-sms',  # Trigger the bulk-sms form actions
                                      'bulk-tasks': task_ids,      # Selected tasks
                                      'bulk_close_tasks': 'on'},
                                     follow=True)

        self.assertEqual(response1.status_code, 200)

        # Then send an sms to those filtered customers. Use the client from the
        # first response to ensure that the session data is retained between posts
        response2 = response1.client.post(reverse('core_management_customer_bulk_compose'),
                                          {'text': 'gloobertyfoo',
                                           'senders': 'iShamba'},
                                          follow=True)
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(pre_outgoing_messages_count0 + 1, tasks[0].outgoing_messages.count())
        self.assertEqual(pre_outgoing_messages_count1 + 1, tasks[1].outgoing_messages.count())
        self.assertEqual(pre_outgoingsms_count + 1, OutgoingSMS.objects.count())

        self.assertEqual(pre_smsrecipient_count + 2, SMSRecipient.objects.count())  # one per task
        out = OutgoingSMS.objects.order_by('-pk').first()
        self.assertEqual(out, tasks[0].outgoing_messages.first())
        self.assertEqual(out, tasks[1].outgoing_messages.first())
        self.assertEqual('task', out.message_type)
        tasks[0].refresh_from_db()
        tasks[1].refresh_from_db()
        self.assertEqual('closed_resolved', tasks[0].status)
        self.assertEqual('closed_resolved', tasks[1].status)
        self.assertContains(response2, 'Bulk message sent to 2 customers, 2 tasks Closed:Resolved')


class TaskSMSReplyFormTests(TestCase):

    def setUp(self):
        super().setUp()
        user = get_user_model()
        self.operator = user.objects.create_user('foo', password='foo')

        # Set-up CallCenters (TODO: should use factories)
        self.call_center = CallCenter.objects.get(border=Border.objects.get(country='Kenya', level=0))
        self.call_center_operator = CallCenterOperator.objects.create(operator=self.operator, active=True, call_center=self.call_center)
        self.call_center_sender = CallCenterSender.objects.create(sender_id="iShamba", description="blah")
        self.call_center.senders.add(self.call_center_sender)

        self.client = Client(self.tenant)
        self.client.login(username='foo', password='foo')

        self.test_customer_1 = CustomerFactory()
        self.test_customer_2 = CustomerFactory()

        self.tasks = [
            TaskFactory(customer=self.test_customer_1, status=Task.STATUS.new, priority=Task.PRIORITY.low),
            TaskFactory(status=Task.STATUS.progressing),
            TaskFactory(priority='medium', status=Task.STATUS.progressing),
            TaskFactory(last_editor_id=self.operator.pk, status=Task.STATUS.closed_resolved),
            TaskFactory(status=Task.STATUS.closed_unresolved),
            TaskFactory(priority='low'),
            TaskFactory(priority='high', customer=self.test_customer_2),
            TaskFactory(priority='critical'),
        ]

    def test_setup(self):
        # Ensure the DB has our records stored
        self.assertEqual(len(self.tasks), Task.objects.count())
        self.assertEqual(0, TaskUpdate.objects.count())

    @activate_success_response
    def test_logged_in_get_creates_correct_helper_and_form_action(self):
        task = self.tasks[0]
        # r'^tasks/update/(?P<task_pk>\d+)/$'
        response = self.client.get(reverse('task_update', args=[task.id]),
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(['tasks/task_update.html'], response.template_name)
        url = reverse('task_reply', args=[task.customer.id, task.id])
        self.assertContains(response, f'<form  action="{url}" method="post" >')

    @activate_success_response
    def test_logged_in_post_sends_kenya_message(self):
        task = self.tasks[0]
        pre_outgoing_messages_count = task.outgoing_messages.count()
        pre_outgoingsms_count = OutgoingSMS.objects.count()
        pre_smsrecipient_count = SMSRecipient.objects.count()

        # r'^reply/(?P<pk>\d+)/(?P<task_pk>\d+)/$'
        response = self.client.post(reverse('task_reply', args=[task.customer.id, task.id]),
                                    {'text': 'gloobertyfoo',
                                     'senders': 'iShamba'},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(pre_outgoing_messages_count + 1, task.outgoing_messages.count())
        self.assertEqual(pre_outgoingsms_count + 1, OutgoingSMS.objects.count())
        self.assertEqual(pre_smsrecipient_count + 1, SMSRecipient.objects.count())
        out = OutgoingSMS.objects.order_by('-pk').first()
        self.assertEqual(out, task.outgoing_messages.first())
        self.assertEqual('task', out.message_type)

    @activate_success_response
    def test_logged_in_post_to_uganda_customer_sends_message(self):
        uganda = Border.objects.get(name='Uganda', level=0)
        uganda_customer = CustomerFactory(border0=uganda, has_no_phones=True)
        uganda_phone = CustomerPhoneFactory(number='+256414123456', is_main=True, customer=uganda_customer)

        self.call_center = CallCenter.objects.get(border=uganda)
        self.call_center_operator.delete() # clear our Kenya setting from setUp
        self.call_center_operator = CallCenterOperator.objects.create(operator=self.operator, active=True, call_center=self.call_center)
        self.call_center_sender = CallCenterSender.objects.create(sender_id="iShambaU", description="blah")
        self.call_center.senders.add(self.call_center_sender)

        task = TaskFactory(customer=uganda_customer)
        pre_outgoing_messages_count = task.outgoing_messages.count()
        pre_outgoingsms_count = OutgoingSMS.objects.count()
        pre_smsrecipient_count = SMSRecipient.objects.count()

        # r'^reply/(?P<pk>\d+)/(?P<task_pk>\d+)/$'
        response = self.client.post(reverse('task_reply', args=[task.customer.id, task.id]),
                                    {'text': 'gloobertyfoo',
                                     'senders': 'iShambaU'},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(pre_outgoing_messages_count + 1, task.outgoing_messages.count())
        self.assertEqual(pre_outgoingsms_count + 1, OutgoingSMS.objects.count())
        self.assertEqual(pre_smsrecipient_count + 1, SMSRecipient.objects.count())
        out = OutgoingSMS.objects.order_by('-pk').first()
        self.assertEqual(out, task.outgoing_messages.first())
        self.assertEqual('task', out.message_type)

    @activate_success_response
    def test_logged_in_post_to_kenya_customer_using_uganda_sender_fails(self):
        task = self.tasks[0]
        pre_outgoing_messages_count = task.outgoing_messages.count()
        pre_outgoingsms_count = OutgoingSMS.objects.count()
        pre_smsrecipient_count = SMSRecipient.objects.count()

        # r'^reply/(?P<pk>\d+)/(?P<task_pk>\d+)/$'
        response = self.client.post(reverse('task_reply', args=[task.customer.id, task.id]),
                                    {'text': 'gloobertyfoo',
                                     'senders': 'iShambaU'},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "error_1_id_senders") # The response should highlight an error on sender_Kenya
        self.assertEqual(pre_outgoing_messages_count + 0, task.outgoing_messages.count())
        self.assertEqual(pre_outgoingsms_count + 0, OutgoingSMS.objects.count())
        self.assertEqual(pre_smsrecipient_count + 0, SMSRecipient.objects.count())

    @activate_success_response
    def test_logged_in_duplicate_posts_sends_one_message(self):
        task = self.tasks[0]
        prior_msg_count = task.outgoing_messages.count()
        pre_outgoingsms_count = OutgoingSMS.objects.count()
        pre_smsrecipient_count = SMSRecipient.objects.count()

        # r'^reply/(?P<pk>\d+)/(?P<task_pk>\d+)/$'
        for i in range(3):
            response = self.client.post(reverse('task_reply', args=[task.customer.id, task.id]),
                                        {'text': 'gloobertyfoo',
                                         'senders': 'iShamba'},
                                        follow=True)
            self.assertEqual(response.status_code, 200)

        # Despite multiple submissions of the 'send sms' form, only one should have been sent
        self.assertEqual(prior_msg_count + 1, task.outgoing_messages.count())
        self.assertEqual(pre_outgoingsms_count + 1, OutgoingSMS.objects.count())
        self.assertEqual(pre_smsrecipient_count + 1, SMSRecipient.objects.count())
        out = OutgoingSMS.objects.order_by('-pk').first()
        self.assertEqual(out, task.outgoing_messages.first())
        self.assertEqual('task', out.message_type)

    @activate_success_response
    def test_separate_users_duplicate_posts_sends_two_messages(self):
        task = self.tasks[0]
        prior_msg_count = task.outgoing_messages.count()
        pre_outgoingsms_count = OutgoingSMS.objects.count()
        pre_smsrecipient_count = SMSRecipient.objects.count()

        # r'^reply/(?P<pk>\d+)/(?P<task_pk>\d+)/$'
        response = self.client.post(reverse('task_reply', args=[task.customer.id, task.id]),
                                    {'text': 'gloobertyfoo',
                                     'senders': 'iShamba'},
                                    follow=True)
        self.assertEqual(response.status_code, 200)

        user = get_user_model()
        self.operator = user.objects.create_user('bar', password='bar')
        self.client = Client(self.tenant)
        self.client.login(username='bar', password='bar')

        response = self.client.post(reverse('task_reply', args=[task.customer.id, task.id]),
                                    {'text': 'gloobertyfoo',
                                     'senders': 'iShamba'},
                                    follow=True)
        self.assertEqual(response.status_code, 200)

        # Despite identical task and text submissions of the 'send sms' form, since
        # they were sent by different users, both should send successfully
        self.assertEqual(prior_msg_count + 2, task.outgoing_messages.count())
        # Separate users should create two messages, one of each has a recipient
        self.assertEqual(pre_outgoingsms_count + 2, OutgoingSMS.objects.count())
        self.assertEqual(pre_smsrecipient_count + 2, SMSRecipient.objects.count())
        for out in OutgoingSMS.objects.order_by('-pk'):
            self.assertEqual('task', out.message_type)

    @activate_success_response
    def test_logged_in_post_redirects_to_task_update_and_toasts(self):
        task = self.tasks[0]

        # r'^reply/(?P<pk>\d+)/(?P<task_pk>\d+)/$'
        response = self.client.post(reverse('task_reply', args=[task.customer.id, task.id]),
                                    {'text': 'gloobertyfoo',
                                     'senders': 'iShamba'},
                                    follow=True)
        self.assertRedirects(response, expected_url=f"/tasks/update/{task.id}/")
        self.assertInHTML('<li class="alert alert-success">Message sent</li>', response.rendered_content, count=1)
        self.assertInHTML('<p>gloobertyfoo</p>', response.rendered_content, count=1)
