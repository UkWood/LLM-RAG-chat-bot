"""Regression checks for the offline project registry checker."""
import copy
import json
from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]
validate = runpy.run_path(str(ROOT / 'scripts/check_project.py'))['validate_registry']


class RegistryChecks(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT / 'config/knowledge/public-sources.json').read_text())

    def test_current_registry_passes(self):
        self.assertEqual(validate(self.registry), [])

    def test_pending_cloud_permission_is_rejected(self):
        self.registry['entries'][0].update(cloud_allowed=True, allowed_usage=['cloud_generate'])
        self.assertTrue(validate(self.registry))

    def test_duplicate_id_is_rejected(self):
        self.registry['entries'].append(copy.deepcopy(self.registry['entries'][0]))
        self.assertTrue(validate(self.registry))

    def test_approval_without_hash_is_rejected(self):
        self.registry['entries'][0].update(approval_state='approved', visibility='PUBLIC', publication_verified=True)
        self.assertTrue(validate(self.registry))

    def test_path_traversal_is_rejected(self):
        self.registry['entries'][0]['path'] = 'src/content/../../private.md'
        self.assertTrue(validate(self.registry))


if __name__ == '__main__':
    unittest.main()
