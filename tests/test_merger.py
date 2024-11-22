import json
from pathlib import Path
from unittest import TestCase

from deepdiff import DeepDiff
from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.entities import ItemEntity

from wikibasemigrator.merger import EntityMerger


class TestEntityMerger(TestCase):
    """
    Test EntityMerger
    """

    def test_merge(self):
        """
        test merging entities
        """
        self.maxDiff = None
        resource_dir = Path(__file__).parent / "resources/merger"
        source_json = json.loads(resource_dir.joinpath("Q80_source.json").read_text())["entities"]["Q80"]
        target_json = json.loads(resource_dir.joinpath("Q80_target.json").read_text())["entities"]["Q80"]
        expected_full_json = json.loads(resource_dir.joinpath("Q80_expected.json").read_text())["entities"]["Q80"]
        wbi = WikibaseIntegrator()
        source_entity = ItemEntity(api=wbi).from_json(source_json)
        target_entity = ItemEntity(api=wbi).from_json(target_json)
        expected_entity = ItemEntity(api=wbi).from_json(expected_full_json)
        merged_entity = EntityMerger().merge(source_entity, target_entity)
        actual_json = merged_entity.get_json()
        expected_json = expected_entity.get_json()
        result = DeepDiff(actual_json, expected_json, ignore_order=True)
        self.assertEqual(result, {})
