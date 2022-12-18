import uuid
import re
from django.core.cache import caches
from django.db import models

from django.contrib.postgres.search import SearchVectorField

from pgsearch.fields import TSVectorField
from pgsearch.managers import ReadOnlySearchManager


from .manager import SNOMEDCTModelManager

# Get the cache shortcut
cache = caches['snomed_ct']


def pretty_print_list(my_list, sep=", ", and_char=", & "):
    return and_char.join([sep.join(my_list[:-1]), my_list[-1]] if len(my_list) > 2 else my_list)

###################
### Base models ###
###################

class BaseSNOMEDCTModel(models.Model):
    class Meta:
        abstract = True

    def get_active_display(self):
        return 'Active' if self.active else 'Inactive'

class CommonSNOMEDQuerySet(models.query.QuerySet):
    @property
    def active(self):
        return self.filter(active=True)

class CommonSNOMEDModel(BaseSNOMEDCTModel):
    id = models.BigIntegerField(primary_key=True)
    effective_time = models.DateField(db_column='effectiveTime')
    active = models.BooleanField()

    class Meta:
        abstract = True
        unique_together = (('id', 'effective_time', 'active'),)

##########################
### Terminology models ###
##########################

class ConceptQuerySet(CommonSNOMEDQuerySet):
    def by_fully_specified_names(self, **kwargs):
        return Concept.objects.filter(id__in=Description
                                      .fully_specified_names()
                                      .filter(**kwargs).values_list('concept__id', flat=True))

class ConceptManager(SNOMEDCTModelManager):
    use_for_related_fields = True

    def by_full_specified_name(self, **kwargs):
        return self.get_queryset().filter(
            id__in=Description.fully_specified_names().filter(**kwargs).values_list('concept__id',
                                                                                    flat=True))

    def get_queryset(self):
        return ConceptQuerySet(self.model)

PRIMITIVE_CONCEPT = 900000000000074008
DEFINED_CONCEPT = 900000000000073002

DEFINITION_STATUS_MAPPING = {
    'Primitive': PRIMITIVE_CONCEPT,
    'Defined' : DEFINED_CONCEPT
}

SNOMED_NAME_PATTERN = re.compile(r'(?P<name>[^\(]+)\s+\((?P<type>[^\(]+)\)')

class Concept(CommonSNOMEDModel):
    DEFINITION_STATUS_CHOICES = (
        (900000000000074008, 'Primitive'),
        (900000000000073002, 'Defined')
    )
    module = models.ForeignKey('self', on_delete=models.PROTECT, related_name='+',
                               db_index=False, db_column='moduleId')
    definition_status = models.ForeignKey('self', on_delete=models.PROTECT,
                                          choices=DEFINITION_STATUS_CHOICES,
                                          related_name='+', db_index=False,
                                          db_column='definitionStatusId')

    objects = ConceptManager()

    class Meta:
        db_table = 'sct2_concept'

    def __str__(self):
        return f"{self.id}|{self.get_fully_specified_name().term}"# [{self.get_active_display()}]"

    def expository_text(self):
        is_primitive = self.definition_status == DEFINITION_STATUS_MAPPING['Primitive']
        classification_names_w_article = ["a/an '{}'".format(c.fully_specified_name_no_type) for c in self.isa]
        non_isa_relationships = self.outbound_relationships().exclude(type_id=ISA)
        roleGroupTextParts = ["{} '{}'".format(
                                         ATTRIBUTE_HUMAN_READABLE_NAMES.get(rel.type.id,
                                                                            rel.type.fully_specified_name_no_type),
                                         rel.destination.fully_specified_name_no_type)
                              for rel in non_isa_relationships]
        if is_primitive:
            definition_head = ", and is ".join(classification_names_w_article)
            definition_text = ", and ".join([definition_head] + roleGroupTextParts)
        else:
            definition_head = pretty_print_list(classification_names_w_article, and_char=", and ")
            definition_text = "({}) that {}".format(definition_head,
                                                    pretty_print_list(roleGroupTextParts, and_char=", and "))
        return "Every '{}' is {}".format(self.fully_specified_name_no_type, definition_text)

    @property
    def fully_specified_name_no_type(self):
        return SNOMED_NAME_PATTERN.search(self.get_fully_specified_name().term).group('name')

    @classmethod
    def by_id(cls, _id, **kwargs):
        return cls.objects.filter(id=_id, **kwargs)

    @classmethod
    def by_full_specified_name(cls, **kwargs):
        return cls.objects.filter(id__in=Description
                                  .fully_specified_names()
                                  .filter(**kwargs).values_list('concept__id', flat=True))

    @classmethod
    def by_definition(cls, **kwargs):
        return cls.objects.filter(id__in=TextDefinition.objects.all()
                                  .filter(**kwargs).values_list('concept__id', flat=True))


    def __get_fully_specified_name(self, lang):
        return self.descriptions.get(
            type_id=DESCRIPTION_TYPES['Fully specified name'],
            active=True
        )

    def __get_preferred_term(self, lang):
        return self.descriptions.get(
            type_id=DESCRIPTION_TYPES['Synonym'],
            active=True)

    def get_fully_specified_name(self, lang="en_us"):
        return cache.get_or_set("fsn_%d" % self.id, lambda: self.__get_fully_specified_name(lang), None)

    def get_preferred_term(self, lang="en_us"):
        return cache.get_or_set("pt_%d" % self.id, lambda: self.__get_preferred_term(lang), None)

    def inbound_relationships(self):
        return Relationship.objects.filter(destination=self)

    def outbound_relationships(self):
        return Relationship.objects.filter(source=self)

    def related_concepts(self, **kwargs):
        return Concept.objects.filter(id__in=self.outbound_relationships()
                                                 .filter(**kwargs).values_list('destination', flat=True))

    @property
    def isa(self):
        return self.related_concepts(type_id=ISA)

    @property
    def finding_site(self):
        return self.related_concepts(type_id=FINDING_SITE)

    @property
    def morphology(self):
        return self.related_concepts(type_id=ASSOCIATED_MORPHOLOGY)

    def definitions(self, values=False, **kwargs):
        rt = TextDefinition.objects.filter(concept=self,  **kwargs)
        return rt.values_list('term', flat=True) if values else rt

DESCRIPTION_TYPES = {
    'Fully specified name': 900000000000003001,
    'Synonym': 900000000000013009
}


class DescriptionQuerySet(CommonSNOMEDQuerySet):
    @property
    def fully_specified_names(self):
        return self.filter(type_id=DESCRIPTION_TYPES['Fully specified name'])

class DescriptionManager(SNOMEDCTModelManager):
    use_for_related_fields = True

    def get_queryset(self):
        return DescriptionQuerySet(self.model)

    @property
    def fully_specified_names(self):
        return self.get_queryset().fully_specified_names

class Description(CommonSNOMEDModel):
    TYPE_CHOICES = (
        (code, label) for label, code in DESCRIPTION_TYPES.items()
    )
    CASE_SIGNIFICANCE_CHOICES = (
        (900000000000020002, 'Initial character case insensitive'),
        (900000000000017005, 'Case sensitive')
    )
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='module_descriptions', db_index=False,
                               db_column='moduleId')
    concept = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='descriptions', db_index=False,
                                db_column='conceptId')
    language_code = models.CharField(max_length=2, db_column='languageCode')
    type = models.ForeignKey(Concept, on_delete=models.PROTECT, choices=TYPE_CHOICES,
                             db_index=False, db_column='typeId', related_name='type_descriptions')
    term = models.TextField(db_index = True)
    case_significance = models.ForeignKey(Concept, on_delete=models.PROTECT, choices=CASE_SIGNIFICANCE_CHOICES,
                                          db_index=False, db_column='caseSignificanceId')

    objects = DescriptionManager()
    
    @classmethod
    def fully_specified_names(cls):
        return cls.objects.fully_specified_names

    class Meta:
        db_table = 'sct2_description'

    def __str__(self):
        return "%s: %s (%s)" % (self.language_code.upper(), self.term, self.get_active_display())


class TextDefinitionQuerySet(CommonSNOMEDQuerySet):
    pass

class TextDefinitionManager(SNOMEDCTModelManager):
    use_for_related_fields = True

    def get_queryset(self):
        return TextDefinitionQuerySet(self.model)

class TextDefinition(CommonSNOMEDModel):
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+',
                               db_index=False, db_column='moduleId')
    concept = models.ForeignKey(Concept, on_delete=models.PROTECT, db_column='conceptId')
    language_code = models.CharField(max_length=3, db_column='languageCode')
    type = models.ForeignKey(Concept, on_delete=models.PROTECT, choices=Description.TYPE_CHOICES,
                             db_index=False, db_column='typeId', related_name='+')
    term = models.TextField(db_index=True)
    case_significance = models.ForeignKey(Concept, on_delete=models.PROTECT,
                                          choices=Description.CASE_SIGNIFICANCE_CHOICES,
                                          db_index=False, db_column='caseSignificanceId',
                                          related_name='+')
    objects = TextDefinitionManager()

    class Meta:
        db_table = 'sct2_text_definition'

ISA = 116680003
FINDING_SITE = 363698007
ASSOCIATED_MORPHOLOGY = 116676008

class RelationshipQuerySet(CommonSNOMEDQuerySet):
    pass

class RelationshipManager(SNOMEDCTModelManager):
    use_for_related_fields = True

    def get_queryset(self):
        return RelationshipQuerySet(self.model)

ATTRIBUTE_HUMAN_READABLE_NAMES = {
    363698007: 'is located in some',
    116676008: 'has morphology',
    # 0: '',
}

class Relationship(CommonSNOMEDModel):
    TYPE_CHOICES = (
        # Attributes used to define clinical finding concepts
        (FINDING_SITE, 'Finding site'),
        (ASSOCIATED_MORPHOLOGY, 'Associated morphology'),
        (47429007, 'Associated with'),
        (255234002, 'After'),
        (42752001, 'Due to'),
        (246075003, 'Causative agent'),
        (246112005, 'Severity'),
        (263502005, 'Clinical course'),
        (246456000, 'Episodicity'),
        (363714003, 'Interprets'),
        (363713009, 'Has interpretation'),
        (370135005, 'Pathological process'),
        (363705008, 'Has definitional manifestation'),
        (246454002, 'Occurrence'),
        (418775008, 'Finding method'),
        (419066007, 'Finding informer'),

        # Attributes used to define procedure concepts
        (363704007, 'Procedure site'),
        (405816004, 'Procedure morphology'),
        (260686004, 'Method'),
        (405815000, 'Procedure device'),
        (260507000, 'Access'),
        (363701004, 'Direct substance'),
        (260870009, 'Priority'),
        (363702006, 'Has focus'),
        (363703001, 'Has intent'),
        (370131001, 'Recipient category'),
        (246513007, 'Revision status'),
        (410675002, 'Route of administration'),
        (424876005, 'Surgical approach'),
        (424361007, 'Using substance'),
        (424244007, 'Using energy'),

        # Attributes used to define evaluation procedure concepts
        (116686009, 'Has specimen'),
        (246093002, 'Component'),
        (370134009, 'Time aspect'),
        (370130000, 'Property'),
        (370132008, 'Scale type'),
        (370129005, 'Measurement method'),

        # Attributes used to define specimen concepts
        (118171006, 'Specimen procedure'),
        (118169006, 'Specimen source topography'),
        (118168003, 'Specimen source morphology'),
        (370133003, 'Specimen substance'),
        (118170007, 'Specimen source identity'),

        # Attributes used to define body structure concepts
        (272741003, 'Laterality'),

        # Attributes used to define pharmaceutical/biologic product concepts
        (127489000, 'Has active ingredient'),
        (411116001, 'Has dose form'),

        # Attributes used to define situation with explicit context concepts
        (246090004, 'Associated finding'),
        (408729009, 'Finding context'),
        (363589002, 'Associated procedure'),
        (408730004, 'Procedure context'),
        (408731000, 'Temporal context'),
        (408732007, 'Subject relationship context'),

        # Attributes used to define event concepts
        # - Associated with (defined above)
        # - Occurrence (defined above)

        # Others
        (ISA, 'Is a'),
        (261583007, 'Using'),
        (258214002, 'Stage'),
        (246100006, 'Onset'),
        (260908002, 'Course'),
        (260858005, 'Extent'),
        (123005000, 'Part of'),
        (367346004, 'Measures'),
        (246267002, 'Location'),
        (260669005, 'Approach'),
        (424226004, 'Using device'),
        (363699004, 'Direct device'),
        (309824003, 'Instrumentation'),
        (363710007, 'Indirect device'),
        (370127007, 'Access instrument'),
        (363700003, 'Direct morphology'),
        (363708005, 'Temporally follows'),
        (363709002, 'Indirect morphology'),
        (425391005, 'Using access device'),
        (116683001, 'Associated function'),
        (308489006, 'Pathological process'),
        (405813007, 'Procedure site direct'),
        (116678009, 'Has measured component'),
        (131195008, 'Subject of information'),
        (405814001, 'Procedure site indirect'),
        (263535000, 'Communication with wound'),
        (363715002, 'Associated etiologic finding'),
    )
    CHARACTERISTIC_TYPE_CHOICES = (
        (900000000000011006, 'Inferred relationship'),
        (900000000000227009, 'Additional relationship')
    )
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+',
                               db_index=False, db_column='moduleId')
    source = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='source_relationships',
                               db_column='sourceId')
    destination = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='destination_relationships',
                                    db_column='destinationId')
    relationship_group = models.SmallIntegerField(db_column='relationshipGroup')
    type = models.ForeignKey(Concept, on_delete=models.PROTECT, choices=Description.TYPE_CHOICES,
                             related_name='+',
                             db_index=False, db_column='typeId')
    characteristic_type = models.ForeignKey(Concept,on_delete=models.PROTECT, 
                                            choices=CHARACTERISTIC_TYPE_CHOICES,
                                            related_name='+',
                                            db_column='characteristicTypeId')
    modifier = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+', db_column='modifierId')

    objects = RelationshipManager()

    class Meta:
        db_table = 'sct2_relationship'

    def __str__(self):
        return f"{self.source} - {self.type} -> {self.destination}"

# class Relationship(BaseSNOMEDCTModel):
#     objects = SNOMEDCTModelManager()
#
#     class Meta:
#         managed = False
#         db_table = 'sct2_stated_relationship'
#         unique_together = (('id', 'effective_time', 'active'),)


############################
### Reference set models ###
############################

### Language reference sets

class LangRefSet(CommonSNOMEDModel):
    REFSET_CHOICES = (
        # Just the most common ones
        (900000000000509007, 'US English'),
        (900000000000508004, 'GB English'),

        # possible many other
    )
    ACCEPTABILITY_CHOICES = (
        (900000000000548007, 'Preferred'),
        (900000000000549004, 'Acceptable')
    )
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+',
                               db_index=False, db_column='moduleId')
    refset = models.ForeignKey(Concept, on_delete=models.PROTECT, choices=REFSET_CHOICES, related_name='+')
    referenced_component = models.ForeignKey(Description, on_delete=models.PROTECT, related_name='lang_refset')
    acceptability = models.ForeignKey(Concept, on_delete=models.PROTECT, choices=ACCEPTABILITY_CHOICES,
                                      related_name='+')

    objects = SNOMEDCTModelManager()

    class Meta:
        db_table = 'sct2_lang_refset'


### Content reference sets

class AssociationRefSet(CommonSNOMEDModel):
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+',
                               db_index=False, db_column='moduleId')
    refset = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    referenced_component = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    target_component = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')

    objects = SNOMEDCTModelManager()

    class Meta:
        db_table = 'sct2_association_refset'


class AttributeValueRefSet(CommonSNOMEDModel):
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+',
                               db_index=False, db_column='moduleId')
    refset = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    referenced_component = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    value = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')

    objects = SNOMEDCTModelManager()

    class Meta:
        db_table = 'sct2_attribute_value_refset'


class SimpleRefSet(CommonSNOMEDModel):
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+',
                               db_index=False, db_column='moduleId')
    refset = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    referenced_component = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')

    objects = SNOMEDCTModelManager()

    class Meta:
        db_table = 'sct2_simple_refset'


### Map reference sets

class ComplexMapRefSet(CommonSNOMEDModel):
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+',
                               db_index=False, db_column='moduleId')
    refset = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    referenced_component = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    map_group = models.SmallIntegerField()
    map_priority = models.SmallIntegerField()
    map_rule = models.TextField(blank=True, null=True)
    map_advice = models.TextField(blank=True, null=True)
    map_target = models.TextField(blank=True, null=True)
    correlation = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')

    objects = SNOMEDCTModelManager()

    class Meta:
        db_table = 'sct2_complex_map_refset'


class ExtendedMapRefSet(CommonSNOMEDModel):
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+',
                               db_index=False, db_column='moduleId')
    refset = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+',
                               db_column='refsetId')
    referenced_component = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+',
                                             db_column='referencedComponentId')
    map_group = models.SmallIntegerField(db_column='mapGroup')
    map_priority = models.SmallIntegerField(db_column='mapPriority')
    map_rule = models.TextField(blank=True, null=True, db_column='mapRule')
    map_advice = models.TextField(blank=True, null=True, db_column='mapAdvice')
    map_target = models.TextField(blank=True, null=True, db_column='mapTarget')
    correlation = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+', blank=True,
                                    db_column='correlationId', null=True)
    map_category = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+', blank=True, null=True,
                                     db_column='mapCategoryId')

    objects = SNOMEDCTModelManager()

    class Meta:
        abstract = True
        db_table = 'sct2_extended_map_refset'

class ICD10_Mapping(ExtendedMapRefSet):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referenced_component_name = models.TextField(blank=True, null=True, db_column='referencedComponentName')
    map_target_name = models.TextField(blank=True, null=True, db_column='mapTargetName')
    map_category_name = models.TextField(blank=True, null=True, db_column='mapCategoryName')

    class Meta:
        db_table = 'icd10_snomed_ct'

    def __str__(self):
        return "{} -> {}".format(self.map_target, self.referenced_component)

class SimpleMapRefSet(CommonSNOMEDModel):
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+',
                               db_index=False, db_column='moduleId')
    refset = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    referenced_component = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    map_target = models.TextField()

    objects = SNOMEDCTModelManager()

    class Meta:
        db_table = 'sct2_simple_map_refset'


#############################
### Database views models ###
#############################


class TermBasedView(BaseSNOMEDCTModel):
    lang_refset_refset = models.ForeignKey(Concept, on_delete=models.PROTECT, choices=LangRefSet.REFSET_CHOICES, related_name='+', primary_key=True)
    lang_refset_acceptability = models.ForeignKey(Concept, on_delete=models.PROTECT, choices=LangRefSet.ACCEPTABILITY_CHOICES, related_name='+')
    description = models.ForeignKey(Description, on_delete=models.PROTECT, related_name='+')
    description_language_code = models.CharField(max_length=2)
    description_type = models.ForeignKey(Concept, on_delete=models.PROTECT, choices=Description.TYPE_CHOICES, related_name='+')
    description_case_significance = models.ForeignKey(Concept, on_delete=models.PROTECT, choices=Description.CASE_SIGNIFICANCE_CHOICES, related_name='+')
    description_term = models.CharField(max_length=255)
    concept = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    concpet_active = models.BooleanField()
    concpet_definition_status = models.ForeignKey(Concept, on_delete=models.PROTECT, choices=Concept.DEFINITION_STATUS_CHOICES, related_name='+')
    search_term = TSVectorField()

    objects = ReadOnlySearchManager(
        search_field='search_term'
    )

    class Meta:
        db_table = 'terms_based_view'

    def __str__(self):
        return "%s: %s" % (self.description_language_code.upper(), self.description_term)

    def save(self, *args, **kwargs):
        raise NotImplementedError

    def delete(self, *args, **kwargs):
        raise NotImplementedError

