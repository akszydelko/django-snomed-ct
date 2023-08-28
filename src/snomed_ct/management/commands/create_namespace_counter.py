from __future__ import unicode_literals

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection


class Command(BaseCommand):
    help = 'Creates three database based counters to assign unique concept number in given namespace.'
    release_date = None

    def add_arguments(self, parser):
        parser.add_argument('snomed_ct_namespace', type=int)

    def handle(self, *args, **options):
        # namespace id has to consists of 7 digits
        if options['snomed_ct_namespace'] < 1000000 or options['snomed_ct_namespace'] > 9999999:
            raise CommandError("Invalid namespace id.")

        with transaction.atomic():
            cursor = connection.cursor()

            self.stdout.write("Creating concept counter...")
            cursor.execute("""CREATE SEQUENCE extension_concept_%s;""", [options['snomed_ct_namespace']])

            self.stdout.write("Creating description counter...")
            cursor.execute("""CREATE SEQUENCE extension_description_%s;""", [options['snomed_ct_namespace']])

            self.stdout.write("Creating relationship counter...")
            cursor.execute("""CREATE SEQUENCE extension_relationship_%s;""", [options['snomed_ct_namespace']])

        self.stdout.write(
            self.style.SUCCESS("Counters for namespace %d successfully created." % options['snomed_ct_namespace']))
