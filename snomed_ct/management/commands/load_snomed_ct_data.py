import os
import re
import csv
import itertools
import io

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(item):
        return item
from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from glob import glob

from snomed_ct.models import Concept, Description, TextDefinition, Relationship, ICD10_Mapping

INTERNATIONAL_FILENAME_COMPONENT = '_INT_'
US_FILENAME_COMPONENT = '_US'

CONCEPT_FILENAME_TEMPLATE = 'sct2_Concept_{}{}*.txt'
DESCRIPTION_FILENAME_TEMPLATE = 'sct2_Description_{}-en{}*.txt'
TEXTDEFINITION_FILENAME_TEMPLATE = 'sct2_TextDefinition_{}-en{}*.txt'
RELATIONSHIP_FILENAME_TEMPLATE = 'sct2_Relationship_{}{}*.txt'
STATED_RELATIONSHIP_FILENAME_TEMPLATE = 'sct2_StatedRelationship_{}{}*.txt'
LANGUAGE_FILENAME_TEMPLATE = 'der2_cRefset_Language{}-en{}*.txt'
ASSOCIATION_FILENAME_TEMPLATE = 'der2_cRefset_AssociationReference{}{}*.txt'
SIMPLE_FILENAME_TEMPLATE = 'der2_Refset_Simple{}{}*.txt'
ATTRIBUTEVALUE_FILENAME_TEMPLATE = 'der2_cRefset_AttributeValue{}{}*.txt'
SIMPLEMAP_FILENAME_TEMPLATE = 'der2_sRefset_SimpleMap{}{}*.txt'
COMPLEXMAP_FILENAME_TEMPLATE = 'der2_iissscRefset_ComplexMap{}{}*.txt'
EXTENDEDMAP_FILENAME_TEMPLATE = 'der2_iisssccRefset_ExtendedMap{}{}*.txt'
ICD_MAP_FILENAME = 'tls_Icd10cmHumanReadableMap_US*.tsv'

def normalize_delimited_value(val):
    return val.strftime("%Y-%m-%d") if isinstance(val,
                                                  date) else ("1" if val else "0") if isinstance(val, bool) else val

class Command(BaseCommand):
    help = 'Load SNOMED CT Release into the database.'
    release_date = None

    def __init__(self):
        super().__init__()
        self.today = datetime.now().date()

    def add_arguments(self, parser):
        parser.add_argument('snomed_ct_location', type=str)
        parser.add_argument('--icd10_map_location', default=False)
        parser.add_argument('--international', action='store_true', default=False)
        parser.add_argument('--snapshot', action='store_true', default=False)

    def handle(self, *args, **options):
        with transaction.atomic():
            dist_type = 'Snapshot' if options['snapshot'] else 'Full'
            region_type = INTERNATIONAL_FILENAME_COMPONENT if options['international'] else US_FILENAME_COMPONENT
            cursor = connection.cursor()
            filename = os.path.join(options['snomed_ct_location'], 'Terminology',
                                    CONCEPT_FILENAME_TEMPLATE.format(dist_type, region_type))

            resolved_file_name = os.path.abspath(glob(filename)[0])
            self.stdout.write('Loading concept file {}'.format(resolved_file_name))

            records = []
            metaconcept_ids = set()
            with open(resolved_file_name, newline='') as csvfile:
                row_dicts = list(csv.DictReader(csvfile, delimiter='\t'))
                for row_dict in row_dicts:
                    metaconcept_ids.update([row_dict['moduleId'], row_dict['definitionStatusId']])
                self.stdout.write("Creating metaconcepts (definition status & module)")
                for row_dict in tqdm([row_dict for row_dict in row_dicts
                                      if row_dict['id'] in metaconcept_ids]):
                    effectiveTime = datetime.strptime(row_dict['effectiveTime'], '%Y%m%d').date()
                    records.append((row_dict['id'], effectiveTime, row_dict['active'] == '1', row_dict['moduleId'],
                                    row_dict['definitionStatusId']))

                self.stdout.write("Prepping bulk creation of other concepts")
                records.extend(self.id_deprecations([rd for rd in row_dicts if rd['id'] not in metaconcept_ids],
                                                    remaining_columns=['moduleId', 'definitionStatusId']))

            self.stdout.write("Loading ..")
            self.copy_from(cursor, records, Concept.objects.model._meta.db_table,
                           columns=['id', 'effectiveTime', 'active', 'moduleId', 'definitionStatusId'])
            self.stdout.write("Loaded remaining {:,} concepts, collecting descriptions".format(len(records)))

            records = []
            filename = os.path.join(options['snomed_ct_location'], 'Terminology',
                                DESCRIPTION_FILENAME_TEMPLATE.format(dist_type, region_type))
            resolved_file_name = os.path.abspath(glob(filename)[0])

            with open(resolved_file_name, newline='') as csvfile:
                records.extend(self.id_deprecations(csv.DictReader(csvfile, delimiter='\t'),
                                                    remaining_columns=['moduleId', 'conceptId', 'languageCode',
                                                                       'typeId', 'term', 'caseSignificanceId']))
            self.stdout.write('Loading description file {} ({:,} records)'.format(resolved_file_name,
                                                                                  len(records)))
            self.copy_from(cursor, records, Description.objects.model._meta.db_table,
                           columns=['id', 'effectiveTime', 'active', 'moduleId', 'conceptId', 'languageCode', 'typeId',
                                    'term', 'caseSignificanceId'])

            records = []
            filename = os.path.join(options['snomed_ct_location'], 'Terminology',
                                TEXTDEFINITION_FILENAME_TEMPLATE.format(dist_type, region_type))
            resolved_file_name = os.path.abspath(glob(filename)[0])
            self.stdout.write('Loading text definition file {}'.format(resolved_file_name))

            with open(resolved_file_name, newline='') as csvfile:
                records.extend(self.id_deprecations(csv.DictReader(csvfile, delimiter='\t'),
                                                    remaining_columns=['moduleId', 'conceptId', 'languageCode',
                                                                       'typeId', 'term', 'caseSignificanceId']))
            self.copy_from(cursor, records, TextDefinition.objects.model._meta.db_table,
                           columns=['id', 'effectiveTime', 'active', 'moduleId', 'conceptId', 'languageCode', 'typeId',
                                    'term', 'caseSignificanceId'])
            self.stdout.write("Done")

            records = []
            filename = os.path.join(options['snomed_ct_location'], 'Terminology',
                                RELATIONSHIP_FILENAME_TEMPLATE.format(dist_type, region_type))
            resolved_file_name = os.path.abspath(glob(filename)[0])

            self.stdout.write('Loading relationship file {}'.format(resolved_file_name))

            with open(resolved_file_name, newline='') as csvfile:
                records.extend(self.id_deprecations(csv.DictReader(csvfile, delimiter='\t'),
                                                    remaining_columns=['moduleId', 'sourceId', 'destinationId',
                                                                       'relationshipGroup', 'typeId',
                                                                       'characteristicTypeId', 'modifierId']))
            self.copy_from(cursor, records, Relationship.objects.model._meta.db_table,
                           columns=['id', 'effectiveTime', 'active', 'moduleId', 'sourceId', 'destinationId',
                                    'relationshipGroup', 'typeId', 'characteristicTypeId', 'modifierId'])
            self.stdout.write("Done")

        self.stdout.write(self.style.SUCCESS('Successfully loaded SNOMED CT release.'))

        if options['icd10_map_location']:
            records = []
            filename = os.path.join(options['icd10_map_location'], ICD_MAP_FILENAME)
            resolved_file_name = os.path.abspath(glob(filename)[0])
            self.stdout.write('Loading ICD 10 mapping file {}'.format(resolved_file_name))

            with open(resolved_file_name, newline='') as csvfile:
                records.extend(self.id_deprecations(csv.DictReader(csvfile, delimiter='\t'),
                                                    remaining_columns=['moduleId', 'refsetId', 'referencedComponentId',
                                                                       'referencedComponentName', 'mapGroup',
                                                                       'mapPriority', 'mapRule', 'mapAdvice',
                                                                       'mapTarget', 'mapTargetName', 'correlationId',
                                                                       'mapCategoryId', 'mapCategoryName']))
            self.copy_from(cursor, records, ICD10_Mapping.objects.model._meta.db_table,
                           columns=['id', 'effectiveTime', 'active', 'moduleId', 'refsetId', 'referencedComponentId',
                                    'referencedComponentName', 'mapGroup', 'mapPriority', 'mapRule', 'mapAdvice',
                                    'mapTarget', 'mapTargetName', 'correlationId', 'mapCategoryId', 'mapCategoryName'])
            self.stdout.write("Done")

    def copy_from(self, cursor, records, table_name, sep='\t', columns=None):
        csv_file_like_object = io.StringIO()
        for items in tqdm(records):
            if not any([val for val in items if not isinstance(val, (bool, date)) and '\t' in val]):
                csv_file_like_object.write(sep.join(map(normalize_delimited_value, items)) + '\r')
            else:
                self.stdout.write(self.style.WARNING('Skipping {}'.format(items)))
        csv_file_like_object.seek(0)
        cursor.copy_from(csv_file_like_object, table_name, sep=sep, columns=columns)

    def id_deprecations(self, row_dicts, remaining_columns):
        """

        SNOMED CT Release File Specifications
        Only one [..] record with the same id field is current at any point in time. The current record
        will be the one with the most recent effectiveTime before or equal to the date under consideration.
        If the active field of this record is false ('0'), then the concept is inactive at that point in time.
        """
        records = {}
        seen = {}
        for row_dict in row_dicts:
            snomed_id = row_dict['id']
            active_val = row_dict['active'] == '1'
            effectiveTime = datetime.strptime(row_dict['effectiveTime'], '%Y%m%d').date()

            if snomed_id in seen:
                if effectiveTime < datetime.strptime(seen[snomed_id]['effectiveTime'],
                                                     '%Y%m%d').date() <= self.today:
                    continue
            else:
                seen[snomed_id] = row_dict
            record = (snomed_id, effectiveTime, active_val) + tuple([row_dict[field] for field in remaining_columns])
            records.setdefault(snomed_id, []).append(record)

        for snomed_id, items in list(records.items()):
            if len(items) > 1:
                most_recent = sorted(items, key=lambda i: i[1], reverse=True)[0]
                yield most_recent
            else:
                yield items[0]

    def __raise_date_mismatch_error(self):
        raise CommandError("Release files date mismatch. "
                           "Some of the release files are from different release then the others.")

    def __get_location_file_list(self, location):
        return [os.path.join(location, file_name) for file_name in os.listdir(location)]

    def __discover_release_date(self, location):
        release_file_list = []
        release_file_list.extend(self.__get_location_file_list(os.path.join(location, 'Terminology')))
        release_file_list.extend(self.__get_location_file_list(os.path.join(location, 'Refset', 'Language')))
        release_file_list.extend(self.__get_location_file_list(os.path.join(location, 'Refset', 'Content')))
        release_file_list.extend(self.__get_location_file_list(os.path.join(location, 'Refset', 'Map')))

        for file_path in release_file_list:
            file_name = os.path.basename(file_path)
            match = re.match(r'(sct2|der2)_[\w\-_]+(?P<date>\d{8})\.txt', file_name)

            if not self.release_date:
                self.release_date = match.group('date')
            elif self.release_date != match.group('date'):
                self.__raise_date_mismatch_error()
