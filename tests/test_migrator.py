import json
import unittest
from pathlib import Path

from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.datatypes import String
from wikibaseintegrator.entities import ItemEntity
from wikibaseintegrator.models import Snak

from wikibasemigrator.migrator import WikibaseMigrator
from wikibasemigrator.model.profile import load_profile
from wikibasemigrator.model.translations import EntityTranslationResult
from wikibasemigrator.qsgenerator import QuickStatementsGenerator
from wikibasemigrator.wikibase import WbiDataTypes


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
        self.assertIsInstance(qs, str)

    def test_translation_of_unit_entity_ids(self):
        """
        Check if the entity ids of the units of quantity values are correctly translated
        """
        expected_maps = {"Q11573": "Q102132"}
        entity_json = json.loads(self.resource_dir.joinpath("unit_ids.json").read_text())
        item = ItemEntity().from_json(entity_json)
        translation_result = self.migrator.translate_entity(item)
        translation_json = translation_result.entity.get_json()
        for source, target in expected_maps.items():
            self.assertEqual(self.migrator.mapper.get_mapping_for(source), target)
            self.assertIn(f'"unit": "{self.config.target.item_prefix}{target}"', json.dumps(translation_json))

    def test_get_all_items_ids(self):
        """
        Test retrieving all ids from an ItemEntity
        """
        item = self.get_Q80()
        ids = self.migrator.get_all_entity_ids(item)
        self.assertGreaterEqual(len(ids), 390)

    def test_get_all_items_ids_unit_extracted(self):
        """
        Test retrieving all ids from an ItemEntity focus is in this test case the extraction of the unit ids
        """
        entity_json = json.loads(self.resource_dir.joinpath("unit_ids.json").read_text())
        item = ItemEntity().from_json(entity_json)
        ids = self.migrator.get_all_entity_ids(item)
        self.assertIn("Q11573", ids)
        self.assertIn("Q174789", ids)
        self.assertGreaterEqual(len(ids), 8)

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

    def get_blank_item(self) -> ItemEntity:
        return ItemEntity()

    def test_mismatch_translation_string_to_quantity(self):
        """
        tests the translation for the case string to quantity
        """
        source_series_ordinal = "P1545"
        self.migrator.prepare_mapper_cache_by_ids([source_series_ordinal])
        string = String(value="1", prop_nr=source_series_ordinal)
        translation_result = EntityTranslationResult(
            entity=self.get_blank_item(),
            original_entity=self.get_blank_item(),
        )
        string_snak = Snak().from_json(string.mainsnak.get_json())
        new_snak = self.migrator._translate_snak_with_type_mismatch(string_snak, translation_result)
        self.assertEqual(new_snak.mainsnak.datatype, WbiDataTypes.QUANTITY.value)
        self.assertEqual(new_snak.mainsnak.datavalue.get("value").get("amount"), "+1")


if __name__ == "__main__":
    unittest.main()
