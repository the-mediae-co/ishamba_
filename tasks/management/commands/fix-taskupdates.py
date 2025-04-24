import argparse
import csv
import time

from django.core.management.base import BaseCommand
from django.db import connection

from django_tenants.management.commands import InteractiveTenantOption

from tasks.models import Task, TaskUpdate


class Command(BaseCommand, InteractiveTenantOption):
    help = 'Send PlantVillage weather forecast SMS messages'

    # Usage: ./manage.py -t -v1 -s ishamba -d 2

    def add_arguments(self, parser: argparse.ArgumentParser):

        parser.add_argument("-s", "--schema", dest="schema_name", help="tenant schema", default="ishamba")
        parser.add_argument("-t", "--test", dest="test_run", action='store_true',
                            help="test run: no sms messages are sent")
        # parser.add_argument("-v", "--verbose", action="count", default=0,
        #                     help="increase output verbosity")

    def handle(self, *args, **options):

        # Track performance for summary report
        tic = time.perf_counter()

        tenant = self.get_tenant_from_options_or_interactive(**options)
        connection.set_tenant(tenant)

        test_run = options['test_run']

        tasks = Task.objects.all()

        with open('broken_task_history.csv', 'w', newline='') as task_file:
            task_writer = csv.writer(task_file, delimiter=',',
                                     quotechar='"', quoting=csv.QUOTE_MINIMAL)
            task_writer.writerow(['task_id', 'task_status', 'tu_status'])
            task_counter = 0
            creation_counter = 0
            for task in tasks:
                task_counter += 1
                if task_counter % 1000 == 0:
                    print(task_counter)
                # Build our next csv output row buffer
                output = [task.id, task.status]
                updates = task.taskupdate_set.order_by('-created')
                if updates.count() == 0:
                    continue

                # If the task.status does not match the latest TaskUpdate.status,
                # then a gap exists that needs to be filled
                gap_exists = updates.first().status != task.status

                # Add the existing TaskUpdate transitions to the csv buffer
                for tu in updates:
                    output.append(tu.status)
                    if tu.status_changed:
                        output.append(tu.status_changed)

                if gap_exists:
                    if not test_run:
                        # Need to create a TaskUpdate to represent the transition to the
                        # current task.status. We assume that the task.last_editor_id is
                        # the user to made the corresponding change.
                        new_tu = TaskUpdate.objects.create(
                            task=task,
                            status=task.status,
                            creator_id=task.last_editor_id,
                            last_editor_id=task.last_editor_id,
                        )

                        # To bypass the auto setting of the created and last_updated fields,
                        # we have to use a Queryset.update() method
                        TaskUpdate.objects.filter(pk=new_tu.pk).update(last_updated=task.last_updated,
                                                                       created=task.last_updated)

                        # For sanity, make sure the changes stuck the way we expect
                        new_tu.refresh_from_db()
                        assert(new_tu.creator_id == task.last_editor_id)
                        assert(new_tu.last_editor_id == task.last_editor_id)
                        assert(new_tu.status == task.status)
                        assert(new_tu.last_updated == task.last_updated)
                        assert(new_tu.created == task.last_updated)

                        creation_counter += 1
                        output.append(f"FIXED: {new_tu.status_changed}")
                    task_writer.writerow(output)

        toc = time.perf_counter()

        minutes, seconds = divmod(toc - tic, 60)
        print(f"{task_counter} Tasks processed in {minutes} minutes, {seconds:0.1f} seconds")
        print(f"Created {creation_counter} TaskUpdates")
