django-snomed-ct
====================

Django app/model/utilities for quering SNOMED CT database.

## Simple functionality ##
```python
from snomed_ct.models import Concept, ICD10_Mapping, TextDefinition, Description, ISA
```

Via the Django model, you can fetch concepts by REGEX matching their fully specified names (related via the **Description** model).  The method also 
takes other model querying arguments (**active**, **language_code**, **type** (a **Concept**) - fully specified name or synonym, etc) for the Description model, passed as query arguments  

```python
concepts = Concept.by_full_specified_name(term__iregex='aort.+stenosis')
```

A single Concept can be fetched by the Class method **by_id** and you can get direct access to the fully specified name 
(**get_fully_specified_name** method and **fully_specified_name** property) and the name without the parenthesized type suffix (**fully_specified_name_no_type** property) 

```python
concept = Concept.by_id(194733006)
concept.fully_specified_name_no_type
concept.fully_specified_name
```
Relationships about a given concept (concept definitions relating another concept to 
the one given) can be returned as an iterable of the Relationship model and the same can be done in the other direction 
via the **inbound_relationships()** method on Concept model instances.

```python

for rel in snomed_concept.outbound_relationships():
..  print("\t- {} -> {}".format(rel.type, rel.destination))
```

Concepts can be fetched via matching definitions (the **TextDefinition** model) made about them by the _term_ field 
(the textual definition), as well as to other fields by query filter argument 

```python
for c in Concept.by_definition(term__iregex='aort.+stenosis'):
..  print(c)
```

All the definitions for a concept object can be returned as an iterator of TextDefinition model instances

```python
..  for defn in c.definitions().values_list('term', flat=True):
..      print("\t", defn)    
```        

You can also iterate over the ISA relationships of a given concept (General Concept Inclusion):

```python
..  for defn in c.isa().values_list('term', flat=True):
..      print("\t", defn)    
```

Similarly, you can iterate over the finding site concepts (via the **finding_site** property) as well as the associated 
morphologies (of disorders via the **morphologies** property)

## ICD 10 mapping ##
Once you have loaded ICD 10 <-> SNOMED-CT mappings (via the --icd10_map_location option of the load_snomed_ct_data 
manage command), you can start finding mappings by ICD10 codes, iterating over just those SNOMED-CT concepts with
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