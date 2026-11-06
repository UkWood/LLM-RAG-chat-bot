"""Schema/provenance checks with custom in-memory cases, never actual blind contents."""
from copy import deepcopy
import json
import unittest
from unit.test_evidence_gate import prepared
from saturn_ai.evaluation.blind_dataset import validate_blind,GROUPS


class BlindSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.snapshot=prepared()

    def data(self):
        cases=[]
        for group,count in GROUPS.items():
            for i in range(count):
                status='refused' if group=='mandatory_refusal' else ('clarification' if i<4 else 'refused') if group=='ambiguous_invalid' else 'answered'
                need=dict(entity_id='products/edu-410',predicate='power',selector='',document_kind='any',representation='any',reference=None,
                    evidence=[dict(source_id='synthetic:products/edu-410',field_path='power',page=None,text='24 В')])
                cases.append(dict(id=f'custom-{len(cases)}',group=group,question=f'Custom schema-only case {len(cases)}',
                    expected_status=status,requirements=[need] if status=='answered' else []))
        return dict(schema_version=1,profile='planner_v2_blind',snapshot_id=self.snapshot.snapshot_id,
                    registry_revision=self.snapshot.registry.revision,authoring='custom schema fixture, not benchmark',cases=cases)

    def test_counts_and_canonical_support(self):
        self.assertEqual(len(validate_blind(json.dumps(self.data()).encode(),self.snapshot)),40)
        data=self.data();data['cases'][0]['requirements'][0]['evidence'][0]['page']=999
        with self.assertRaises(ValueError):validate_blind(json.dumps(data).encode(),self.snapshot)
        data=self.data();data['cases'][0]['requirements'][0]['evidence'][0]['text']='Invented unsupported value'
        with self.assertRaises(ValueError):validate_blind(json.dumps(data).encode(),self.snapshot)

    def test_malformed_schema_and_reference_kind_do_not_validate(self):
        data=self.data();data['schema_version']=True
        with self.assertRaises(ValueError):validate_blind(json.dumps(data).encode(),self.snapshot)
        data=self.data();data['cases'][0]['requirements'][0]['reference']=dict(kind='entity_type',source_id='synthetic:products/edu-410',value='Device')
        with self.assertRaises(ValueError):validate_blind(json.dumps(data).encode(),self.snapshot)
        data=self.data();data['cases'][1]['question']=data['cases'][0]['question']
        with self.assertRaises(ValueError):validate_blind(json.dumps(data).encode(),self.snapshot)
