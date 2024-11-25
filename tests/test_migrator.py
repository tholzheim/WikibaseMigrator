import json
import unittest
from pathlib import Path

from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.entities import ItemEntity

from wikibasemigrator.migrator import WikibaseMigrator
from wikibasemigrator.model.profile import load_profile
from wikibasemigrator.qsgenerator import QuickStatementsGenerator


class TestWikibaseMigrator(unittest.TestCase):
    def setUp(self):
        self.path = Path(__file__).parent.joinpath("../src/wikibasemigrator/profiles/FactGrid.yaml")
        self.config = load_profile(self.path)
        self.migrator = WikibaseMigrator(self.config)
        self.resource_dir = Path(__file__).parent / "resources/migrator"

    def get_Q80(self):
        """
        Get Q80 from test resources
        """
        entity_json = json.loads(self.resource_dir.joinpath("Q80.json").read_text())
        return ItemEntity().from_json(entity_json)

    def test_translation(self):
        item = self.get_Q80()
        translation_result = self.migrator.translate_entity(item)
        self.assertGreaterEqual(len(translation_result.missing_properties), 5)
        self.assertGreaterEqual(len(translation_result.missing_items), 2)
        qs_generator = QuickStatementsGenerator()
        qs = qs_generator.generate_item(translation_result.entity)
        print(qs)

    def test_get_all_items_ids(self):
        """
        Test retrieving all ids from an ItemEntity
        """
        item = self.get_Q80()
        ids = self.migrator.get_all_entity_ids(item)
        self.assertGreaterEqual(len(ids), 390)

    def test_migration_of_unknown_values(self):
        """
        Test migration of the wikibase special type unkown value
        """
        wbi = WikibaseIntegrator()
        item = wbi.item.get("Q1")
        claims = item.claims.get("P1419")
        print(claims)

    def test_migration_of_properties(self):
        """
        Test migration of the wikibase special type proerties
        :return:
        """
        wbi = WikibaseIntegrator()
        p = wbi.property.get("P31", mediawiki_api_url="https://www.wikidata.org/w/api.php")
        print(p)


if __name__ == "__main__":
    unittest.main()
