import unittest
from pathlib import Path

from wikibaseintegrator import WikibaseIntegrator

from wikibasemigrator.migrator import WikibaseMigrator
from wikibasemigrator.model.profile import load_profile
from wikibasemigrator.qsgenerator import QuickStatementsGenerator


class TestWikibaseMigrator(unittest.TestCase):
    def setUp(self):
        self.path = Path(__file__).parent.joinpath("../src/wikibasemigrator/profiles/FactGrid.yaml")
        self.config = load_profile(self.path)
        self.migrator = WikibaseMigrator(self.config)

    def test_translation(self):
        wbi = WikibaseIntegrator()
        item = wbi.item.get("Q2072238", mediawiki_api_url="https://www.wikidata.org/w/api.php")
        translation_result = self.migrator.translate_item(item)
        self.assertGreaterEqual(len(translation_result.missing_properties), 5)
        self.assertGreaterEqual(len(translation_result.missing_items), 2)
        qs_generator = QuickStatementsGenerator()
        qs = qs_generator.generate_item(translation_result.item)
        print(qs)

    def test_get_all_items_ids(self):
        """
        Test retrieving all ids from an ItemEntity
        """
        wbi = WikibaseIntegrator()
        item = wbi.item.get("Q80", mediawiki_api_url="https://www.wikidata.org/w/api.php")
        ids = self.migrator.get_all_items_ids(item)
        self.assertGreaterEqual(len(ids), 390)

    def test_migration_of_unknown_values(self):
        """
        Test migration of the wikibase special type unkown value
        """
        wbi = WikibaseIntegrator()
        item = wbi.item.get("Q1")
        claims = item.claims.get("P1419")
        # ToDo: Discuss how to handle this case
        print(claims)

    def test_migration_of_proerties(self):
        """
        Test migration of the wikibase special type proerties
        :return:
        """
        wbi = WikibaseIntegrator()
        p = wbi.property.get("P31", mediawiki_api_url="https://www.wikidata.org/w/api.php")
        print(p)


if __name__ == "__main__":
    unittest.main()
