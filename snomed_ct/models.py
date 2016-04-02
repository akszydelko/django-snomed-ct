from __future__ import unicode_literals

from django.core.cache import caches
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from model_utils.choices import Choices

from .manager import SNOMEDCTModelManager

# Get the cache shortcut
cache = caches['snomed_ct']


###################
### Base models ###
###################

# @python_2_unicode_compatible
class BaseSNOMEDCTModel(models.Model):
    class Meta:
        abstract = True

    def get_active_display(self):
        return 'Active' if self.active else 'Inactive'


##########################
### Terminology models ###
##########################

@python_2_unicode_compatible
class Concept(BaseSNOMEDCTModel):
    DEFINITION_STATUS_CHOICES = Choices(
        (900000000000074008, 'primitive', 'Primitive'),
        (900000000000073002, 'defined', 'Defined')
    )

    id = models.BigIntegerField(primary_key=True)
    effective_time = models.DateField()
    active = models.BooleanField()
    module = models.ForeignKey('self', on_delete=models.PROTECT, related_name='+', db_index=False)
    definition_status = models.ForeignKey('self', on_delete=models.PROTECT, choices=DEFINITION_STATUS_CHOICES,
                                          related_name='+', db_index=False)

    objects = SNOMEDCTModelManager()

    class Meta:
        managed = False
        db_table = 'sct2_concept'
        unique_together = (('id', 'effective_time', 'active'),)

    def __str__(self):
        return "SCTID:%d (%s)" % (self.id, self.get_active_display())

    def __get_fully_specified_name(self, lang):
        return self.descriptions.get(
            type=Description.TYPE_CHOICES.fully_specified_name,
            lang_refset__acceptability=LangRefSet.ACCEPTABILITY_CHOICES.preferred,
            lang_refset__refset=getattr(LangRefSet.REFSET_CHOICES, lang)
        )

    def __get_preferred_term(self, lang):
        return self.descriptions.get(
            type=Description.TYPE_CHOICES.synonym,
            lang_refset__acceptability=LangRefSet.ACCEPTABILITY_CHOICES.preferred,
            lang_refset__refset=getattr(LangRefSet.REFSET_CHOICES, lang)
        )

    def get_fully_specified_name(self, lang="en_us"):
        return cache.get_or_set("fsn_%d" % self.id, lambda: self.__get_fully_specified_name(lang), None)

    def get_preferred_term(self, lang="en_us"):
        return cache.get_or_set("pt_%d" % self.id, lambda: self.__get_preferred_term(lang), None)


@python_2_unicode_compatible
class Description(BaseSNOMEDCTModel):
    TYPE_CHOICES = Choices(
        (900000000000003001, 'fully_specified_name', 'Fully specified name'),
        (900000000000013009, 'synonym', 'Synonym')
    )
    CASE_SIGNIFICANCE_CHOICES = Choices(
        (900000000000020002, 'initial_char_case_insensitive', 'Initial character case insensitive'),
        (900000000000017005, 'case_sensitive', 'Case sensitive')
    )

    id = models.BigIntegerField(primary_key=True)
    effective_time = models.DateField()
    active = models.BooleanField()
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='module_descriptions', db_index=False)
    concept = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='descriptions', db_index=False)
    language_code = models.CharField(max_length=2)
    type = models.ForeignKey(Concept, on_delete=models.PROTECT, choices=TYPE_CHOICES, related_name='type_descriptions',
                             db_index=False)
    term = models.CharField(max_length=255)
    case_significance = models.ForeignKey(Concept, on_delete=models.PROTECT, choices=CASE_SIGNIFICANCE_CHOICES,
                                          related_name='case_significance_descriptions', db_index=False)

    objects = SNOMEDCTModelManager()

    class Meta:
        managed = False
        db_table = 'sct2_description'
        unique_together = (('id', 'effective_time', 'active'),)

    def __str__(self):
        return "%s: %s (%s)" % (self.language_code.upper(), self.term, self.get_active_display())


# @python_2_unicode_compatible
class TextDefinition(BaseSNOMEDCTModel):
    id = models.BigIntegerField(primary_key=True)
    effective_time = models.DateField()
    active = models.BooleanField()
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    concept = models.ForeignKey(Concept, on_delete=models.PROTECT)
    language_code = models.CharField(max_length=2)
    type = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    term = models.CharField(max_length=1024)
    case_significance = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')

    objects = SNOMEDCTModelManager()

    class Meta:
        managed = False
        db_table = 'sct2_text_definition'
        unique_together = (('id', 'effective_time', 'active'),)


# @python_2_unicode_compatible
class Relationship(BaseSNOMEDCTModel):
    TYPE_CHOICES = Choices(
        # Attributes used to define clinical finding concepts
        (363698007, 'finding_site', 'Finding site'),
        (116676008, 'associated_morphology', 'Associated morphology'),
        (47429007, 'associated_with', 'Associated with'),
        (255234002, 'after', 'After'),
        (42752001, 'due_to', 'Due to'),
        (246075003, 'causative_agent', 'Causative agent'),
        (246112005, 'severity', 'Severity'),
        (263502005, 'clinical_course', 'Clinical course'),
        (246456000, 'episodicity', 'Episodicity'),
        (363714003, 'interprets', 'Interprets'),
        (363713009, 'has_interpretation', 'Has interpretation'),
        (370135005, 'pathological_process', 'Pathological process'),
        (363705008, 'has_definitional_manifestation', 'Has definitional manifestation'),
        (246454002, 'occurrence', 'Occurrence'),
        (418775008, 'finding_method', 'Finding method'),
        (419066007, 'finding_informer', 'Finding informer'),

        # Attributes used to define procedure concepts
        (363704007, 'procedure_site', 'Procedure site'),
        (405816004, 'procedure_morphology', 'Procedure morphology'),
        (260686004, 'method', 'Method'),
        (405815000, 'procedure_device', 'Procedure device'),
        (260507000, 'access', 'Access'),
        (363701004, 'direct_substance', 'Direct substance'),
        (260870009, 'priority', 'Priority'),
        (363702006, 'has_focus', 'Has focus'),
        (363703001, 'has_intent', 'Has intent'),
        (370131001, 'recipient_category', 'Recipient category'),
        (246513007, 'revision_status', 'Revision status'),
        (410675002, 'route_of_administration', 'Route of administration'),
        (424876005, 'surgical_approach', 'Surgical approach'),
        (424361007, 'using_substance', 'Using substance'),
        (424244007, 'using_energy', 'Using energy'),

        # Attributes used to define evaluation procedure concepts
        (116686009, 'has_specimen', 'Has specimen'),
        (246093002, 'component', 'Component'),
        (370134009, 'time_aspect', 'Time aspect'),
        (370130000, 'property', 'Property'),
        (370132008, 'scale_type', 'Scale type'),
        (370129005, 'measurement_method', 'Measurement method'),

        # Attributes used to define specimen concepts
        (118171006, 'specimen_procedure', 'Specimen procedure'),
        (118169006, 'specimen_source_topography', 'Specimen source topography'),
        (118168003, 'specimen_source_morphology', 'Specimen source morphology'),
        (370133003, 'specimen_substance', 'Specimen substance'),
        (118170007, 'specimen_source_identity', 'Specimen source identity'),

        # Attributes used to define body structure concepts
        (272741003, 'laterality', 'Laterality'),

        # Attributes used to define pharmaceutical/biologic product concepts
        (127489000, 'has_active_ingredient', 'Has active ingredient'),
        (411116001, 'has_dose_form', 'Has dose form'),

        # Attributes used to define situation with explicit context concepts
        (246090004, 'associated_finding', 'Associated finding'),
        (408729009, 'finding_context', 'Finding context'),
        (363589002, 'associated_procedure', 'Associated procedure'),
        (408730004, 'procedure_context', 'Procedure context'),
        (408731000, 'temporal_context', 'Temporal context'),
        (408732007, 'subject_relationship_context', 'Subject relationship context'),

        # Attributes used to define event concepts
        # - Associated with (defined above)
        # - Occurrence (defined above)

        # Others
        (116680003, 'is_a', 'Is a'),
        (261583007, 'using', 'Using'),
        (258214002, 'stage', 'Stage'),
        (246100006, 'onset', 'Onset'),
        (260908002, 'course', 'Course'),
        (260858005, 'extent', 'Extent'),
        (123005000, 'part_of', 'Part of'),
        (367346004, 'measures', 'Measures'),
        (246267002, 'location', 'Location'),
        (260669005, 'approach', 'Approach'),
        (424226004, 'using_device', 'Using device'),
        (363699004, 'direct_device', 'Direct device'),
        (309824003, 'instrumentation', 'Instrumentation'),
        (363710007, 'indirect_device', 'Indirect device'),
        (370127007, 'access_instrument', 'Access instrument'),
        (363700003, 'direct_morphology', 'Direct morphology'),
        (363708005, 'temporally_follows', 'Temporally follows'),
        (363709002, 'indirect_morphology', 'Indirect morphology'),
        (425391005, 'using_access_device', 'Using access device'),
        (116683001, 'associated_function', 'Associated function'),
        (308489006, 'pathological_process', 'Pathological process'),
        (405813007, 'procedure_site_direct', 'Procedure site direct'),
        (116678009, 'has_measured_component', 'Has measured component'),
        (131195008, 'subject_of_information', 'Subject of information'),
        (405814001, 'procedure_site_indirect', 'Procedure site indirect'),
        (263535000, 'communication_with_wound', 'Communication with wound'),
        (363715002, 'associated_etiologic_finding', 'Associated etiologic finding'),
    )
    CHARACTERISTIC_TYPE_CHOICES = Choices(
        (900000000000011006, 'inferred', 'Inferred relationship'),
        (900000000000227009, 'additional', 'Additional relationship')
    )

    id = models.BigIntegerField(primary_key=True)
    effective_time = models.DateField()
    active = models.BooleanField()
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    source = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='source_relationships')
    destination = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='destination_relationships')
    relationship_group = models.SmallIntegerField()
    type = models.ForeignKey(Concept, on_delete=models.PROTECT, choices=TYPE_CHOICES, related_name='+')
    characteristic_type = models.ForeignKey(Concept, on_delete=models.PROTECT, choices=CHARACTERISTIC_TYPE_CHOICES,
                                            related_name='+')
    modifier = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')

    objects = SNOMEDCTModelManager()

    class Meta:
        managed = False
        db_table = 'sct2_relationship'
        unique_together = (('id', 'effective_time', 'active'),)


# @python_2_unicode_compatible
class StatedRelationship(BaseSNOMEDCTModel):
    id = models.BigIntegerField(primary_key=True)
    effective_time = models.DateField()
    active = models.BooleanField()
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    source = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='source_stated_relationships')
    destination = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='destination_stated_relationships')
    relationship_group = models.SmallIntegerField()
    type = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    characteristic_type = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    modifier = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')

    objects = SNOMEDCTModelManager()

    class Meta:
        managed = False
        db_table = 'sct2_stated_relationship'
        unique_together = (('id', 'effective_time', 'active'),)


############################
### Reference set models ###
############################

### Language reference sets

# @python_2_unicode_compatible
class LangRefSet(BaseSNOMEDCTModel):
    REFSET_CHOICES = Choices(
        # Just the most common ones
        (900000000000509007, 'en_us', 'US English'),
        (900000000000508004, 'en_gb', 'GB English'),

        # possible many other
    )
    ACCEPTABILITY_CHOICES = Choices(
        (900000000000548007, 'preferred', 'Preferred'),
        (900000000000549004, 'acceptable', 'Acceptable')
    )

    id = models.TextField(primary_key=True)
    effective_time = models.DateField()
    active = models.BooleanField()
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    refset = models.ForeignKey(Concept, on_delete=models.PROTECT, choices=REFSET_CHOICES, related_name='+')
    referenced_component = models.ForeignKey(Description, on_delete=models.PROTECT, related_name='lang_refset')
    acceptability = models.ForeignKey(Concept, on_delete=models.PROTECT, choices=ACCEPTABILITY_CHOICES,
                                      related_name='+')

    objects = SNOMEDCTModelManager()

    class Meta:
        managed = False
        db_table = 'sct2_lang_refset'


### Content reference sets

# @python_2_unicode_compatible
class AssociationRefSet(BaseSNOMEDCTModel):
    id = models.TextField(primary_key=True)
    effective_time = models.DateField()
    active = models.BooleanField()
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    refset = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    referenced_component = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    target_component = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')

    objects = SNOMEDCTModelManager()

    class Meta:
        managed = False
        db_table = 'sct2_association_refset'


# @python_2_unicode_compatible
class AttributeValueRefSet(BaseSNOMEDCTModel):
    id = models.TextField(primary_key=True)
    effective_time = models.DateField()
    active = models.BooleanField()
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    refset = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    referenced_component = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    value = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')

    objects = SNOMEDCTModelManager()

    class Meta:
        managed = False
        db_table = 'sct2_attribute_value_refset'


# @python_2_unicode_compatible
class SimpleRefSet(BaseSNOMEDCTModel):
    id = models.TextField(primary_key=True)
    effective_time = models.DateField()
    active = models.BooleanField()
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    refset = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    referenced_component = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')

    objects = SNOMEDCTModelManager()

    class Meta:
        managed = False
        db_table = 'sct2_simple_refset'


### Map reference sets

# @python_2_unicode_compatible
class ComplexMapRefSet(BaseSNOMEDCTModel):
    id = models.TextField(primary_key=True)
    effective_time = models.DateField()
    active = models.BooleanField()
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
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
        managed = False
        db_table = 'sct2_complex_map_refset'


# @python_2_unicode_compatible
class ExtendedMapRefSet(BaseSNOMEDCTModel):
    id = models.TextField(primary_key=True)
    effective_time = models.DateField()
    active = models.BooleanField()
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    refset = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    referenced_component = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    map_group = models.SmallIntegerField()
    map_priority = models.SmallIntegerField()
    map_rule = models.TextField(blank=True, null=True)
    map_advice = models.TextField(blank=True, null=True)
    map_target = models.TextField(blank=True, null=True)
    correlation = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+', blank=True, null=True)
    map_category = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+', blank=True, null=True)

    objects = SNOMEDCTModelManager()

    class Meta:
        managed = False
        db_table = 'sct2_extended_map_refset'


# @python_2_unicode_compatible
class SimpleMapRefSet(BaseSNOMEDCTModel):
    id = models.TextField(primary_key=True)
    effective_time = models.DateField()
    active = models.BooleanField()
    module = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    refset = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    referenced_component = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='+')
    map_target = models.TextField()

    objects = SNOMEDCTModelManager()

    class Meta:
        managed = False
        db_table = 'sct2_simple_map_refset'
