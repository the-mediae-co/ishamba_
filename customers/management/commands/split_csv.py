import os
from optparse import make_option

from django.core.management.base import BaseCommand, CommandError

import tablib


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('-n', '--num_rows', action='store', type='int',
                    dest='num_rows',
                    help='The number of rows per individual file'),
    )

    help = ("Given a csv file and a number of rows (n), splits that csv file "
            "into separate files of n rows maintaining the headers.")

    def handle(self, infile=None, **options):
        # verify presence of infile
        if infile is None:
            raise CommandError(
                'Please specify the path to the directory containing the '
                'imports.')
        if not os.path.exists(infile):
            raise CommandError('The path specified cannot be located.')
        if os.path.isdir(infile):
            raise CommandError('The path specified is a directory.')

        try:
            f = open(infile)
        except IOError:
            raise CommandError('Unable to read file. Please try again.')

        num_lines = options.get('num_lines', 10000)

        imported = tablib.import_set(
            f.read().decode('cp1252').encode('utf-8'))

        filename, ext = os.path.splitext(os.path.basename(infile))

        n = 1
        while imported.height:
            dataset = tablib.Dataset()
            dataset.headers = imported.headers

            for __ in range(min(num_lines, imported.height)):
                dataset.append(imported.lpop())

            outpath = '{filename}.{n}{ext}'.format(filename=filename,
                                                   n=n,
                                                   ext=ext)
            # write output to file
            with open(outpath, 'wb') as f:
                f.write(dataset.csv)

            n += 1
