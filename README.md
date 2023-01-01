django-snomed-ct
====================

A general-purpose [Python/Django](https://www.djangoproject.com/) framework for quering the [SNOMED Clinical Terms (SNOMED CT)](https://www.snomed.org/snomed-ct/Use-SNOMED-CT) system, an international, medical terminology system and standard.

## Loading data ##
You can use the **load_snomed_ct_data** custom django-admin command to load a release into a configured database.  
Below is an example that also loads the ICD10 mapping release, both from the _SNOMED_CT_to_ICD-10-CM_Resources_20220901_ and _SnomedCT_USEditionRF2_PRODUCTION_20220901T120000Z_ directories:  

```bash
$ python manage.py load_snomed_ct_data --icd10_map_location=SNOMED_CT_to_ICD-10-CM_Resources_20220901/SNOMED_CT_to_ICD-10-CM_Resources_20220901/ \
  SnomedCT_USEditionRF2_PRODUCTION_20220901T120000Z/Full/
```

The --icd10_map_location option can be excluded if you don't want to load the ICD10 SNOMED-CT mappings

The --international option should be specified if working with an international distribution (otherwise, it defaults
to assuming it is a US distribution).  The --snapshot option should be used with a snapshot distribution 
(otherwise, it defaults to _Full_)

## Simple functionality ##
```python
from snomed_ct.models import Concept, ICD10_Mapping, TextDefinition, Description, ISA
```

You can fetch Concept instances via REGEX matching their fully specified names using the **by_fully_specified_name** 
Class function.  They can also be fetched via full or partial string matching using the **term**="..string.." or 
**term__icontains**=".. substring .." arguments.  The method also takes other fields of the **Description** model 
(**active**, **language_code**, **type**, etc), passed as query arguments for filtering the Descriptions whose corresponding
concepts are returned

```python
concepts = Concept.by_fully_specified_name(term__iregex='aort.+stenosis')
```

Similarly, concepts can be fetched via matching definitions (the **TextDefinition** model) made about them by the 
**by_definition** class function 

```python
for c in Concept.by_definition(term__iregex='aort.+stenosis'):
..  print(c)
```

A single Concept can be fetched by the **by_id** Class method and you can get direct access to the fully specified name 
(via the **fully_specified_name** property) and the name without the parenthesized type suffix (**fully_specified_name_no_type** property) 

```python
concept = Concept.by_id(194733006)
concept.fully_specified_name_no_type
concept.fully_specified_name
```
Relationships about a given concept (concept definitions relating another concept to 
the one given) can be returned as an iterable of Relationship instances using the **outbound_relationships()** method and 
the same can be done in the other direction via the **inbound_relationships()** method on Concept model instances.

```python
for rel in snomed_concept.outbound_relationships():
..  print("\t- {} -> {}".format(rel.type, rel.destination))
```

## Working with Concepts ##

You can navigate the ISA relationships of a given concept (General Concept Inclusion) via the
**isa** Concept property, which returns an iterator of Concept instances related to the starting concept via 
ISA:

```python
for general_concept in c.isa:
..  print("\t", general_concept)    
```

Conversely, there is also a **specialization** property that returns an iterator over other Concept instances that have an ISA relationship with the 
given concept:

```python
for specialized_concept in c.specializations:
..  print("\t", specialized_concept)    
```

Similarly, you can iterate over the finding site concepts (via the **finding_site** property) as well as the associated 
morphologies (of disorders via the **morphologies** property) and everything a given concept is 'part of' using the 
**part_of** property, which returns an iterator of concepts related in this way.  The **has_part** property returns 
everything that is 'part of' a given concept (the opposite relationship).


All the definitions for a concept object can also be returned as an iterator of TextDefinition model instances using the 
**definitions()** method.

```python
for defn in c.definitions().values_list('term', flat=True):
..  print("\t", defn)    
```        
All the descriptions for a concept object can be returned with the **descriptions** relation name:

```python
for description in c.descriptions().values_list('term', flat=True):
..  print("\t", description)    
```

There are a few convenience properties available on QuerySets of Description and TextDefinition instances.  In particular, 
the terms property will return a list of the term vales for each instance in the query set, the **synonyms** property
will filter the query set to only include Description or TextDefinition instances that are synonyms:

```python
description_text = list(c.descriptions().terms)
definition_text = list(c.definitions())
synonyms_text = list(c.definitions().synonyms)
```

## ICD 10 mapping ##
Once you have loaded ICD 10 <-> SNOMED-CT mappings via the --icd10_map_location option of the load_snomed_ct_data 
manage command (see the section below about loading SNOMED-CT release data into django-snomed-ct), you can start finding mappings by ICD10 codes, iterating over just those SNOMED-CT concepts with
ICD 10 mappings, etc.

The example below uses the very useful [icd10-cm](https://pypi.org/project/icd10-cm/) 
python library to iterate just over the subset of SNOMED CT concepts mapped to the ICD10 _I10_ code (Essential (primary) hypertension)) and that have
textual definitions, printed along with their definitions.

```python
import icd10
icd_code = icd10.find('I10')
for t in TextDefinition.objects.filter(concept__in=ICD10_Mapping.objects
                                                     .filter(map_target__icontains=str(icd_code.code),map_rule='TRUE')
                                                     .concepts()):
    print(t.concept, t.term)    
712832005|Supine hypertension (disorder) A systolic blood pressure ≥150 mm Hg or diastolic blood pressure ≥90 mm Hg while lying down.
720568003|Brachydactyly and arterial hypertension syndrome (disorder) A rare genetic brachydactyly syndrome with the association of brachydactyly type E and hypertension (due to vascular or neurovascular anomalies) as well as the additional features of short stature and low birth weight (compared to non-affected family members), stocky build and a round face. The onset of hypertension is often in childhood and if untreated, most patients will have had a stroke by the age of 50.
717824007|Progressive arterial occlusive disease, hypertension, heart defect, bone fragility, brachysyndactyly syndrome (disorder) Grange syndrome has characteristics of stenosis or occlusion of multiple arteries (including the renal, cerebral and abdominal vessels), hypertension, brachysyndactyly, syndactyly, increased bone fragility, and learning difficulties or borderline intellectual deficit. So far, the syndrome has been reported in six patients from three families. Congenital heart defects were also reported in some cases. The mode of transmission remains unclear, both autosomal recessive and autosomal dominant inheritance with decreased penetrance and parental gonadal mosaicism have been proposed.
```
You can also iterate over all SNOMED-CT concepts mapped to an ICD-10 code substring: 

```python
for map in ICD10_Mapping.objects.filter(map_target__icontains=icd_code, map_rule='TRUE'):
..  snomed_ct_concept = map.referenced_component
```

## ISA Transitive Closure ##

The transitive closure of the ISA relationship can be calculated from a SNOMED-CT relationship release file using the 
[SNOMED CT Database Scripts](https://github.com/IHTSDO/snomed-database-loader).  In particular, the snomed_g_TC_tools.py
script can be run this way:

```bash
$ python snomed_g_TC_tools.py TC_from_RF2 <relationshipsfilename> <TCfilename>
```

Where __relationshipsfilename__ is a relationships file from a release and __TCfilename__ is the name of the 
transitive closure file to write out.  Once this file is written, the load_snomed_ct_data command can be run with the 
--transitive_closure_location option which should be the resulting transitive closure file

Once the transitive closure file has been loaded, you can return all the concepts related to a given concept via the
**transitive_isa** method which returns a TransitiveClosureQuerySet.

TransitiveClosure is the transitive closure of the 'subsumption' relationship (the inverse of ISA) materialized 
by **snomed-database-loader**.

Each TransitiveClosureQuerySet instance, has a **general_concepts** method that
returns a ConceptQuerySet of _all_ the general concepts (those that generalise the given concept) and a **specific_concepts**
method which returns _all_ the specific concepts from the transitive closure.  So the following will return all 
the more general SNOMED-CT concepts that a given concept is derived from that also have ICD mappings:

```python
icd_mapped_concepts = c.transitive_isa.general_concepts.has_icd10_mappings()
```

Once you have loade the transitive closure and ICD mappings, given a concept instance, you can use the mehcanism for both
to find all the ICD-10 codes mapped to concepts in the transitive closure of its ISA relation (i.e., all more general 
SNOMED-CT concepts)

This is a very useful way to *discover* ICD-10 codes relevant to a problem identified (possibly from its name or 
definition) by leveraging the logical expressiveness of the mathematics used to capture the meaning of SNOMED-CT 
terminology

```python
mappings = concept.icd10_mappings.all()
if mappings.exists():
..  logical_synonyms_ids = concept.transitive_isa.general_concepts.ids
..  icd_mappings = c.transitive_isa.general_concepts.has_icd10_mappings().icd10_mappings()
..  for code in set(icd_mappings.values_list('map_target', flat=True)):
..      icd_code = icd10.find(code)
..      if code.strip() and icd_code is not None:
..          print(str(code))
```
