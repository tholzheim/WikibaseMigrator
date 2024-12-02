import unittest
from pathlib import Path

from wikibasemigrator.mapper import WikibaseItemMapper
from wikibasemigrator.model.profile import load_profile
from wikibasemigrator.wikibase import WbiDataTypes


class TestWikibaseItemMapper(unittest.TestCase):
    """
    Test WikibaseItemMapper
    """

    def setUp(self):
        self.profile_path = Path(__file__).parent.joinpath("../src/wikibasemigrator/profiles/FactGrid.yaml")
        self.profile = load_profile(self.profile_path)

    def test_querying_mapping(self):
        mapper = WikibaseItemMapper(self.profile)
        mapping = mapper.get_mapping_for("Q183")
        self.assertEqual("Q140530", mapping)
        self.assertEqual("P2", mapper.get_mapping_for("P31"))

    def test_caching_of_property_types(self):
        """ "
        test caching of property types
        """
        mapper = WikibaseItemMapper(self.profile)
        mapper.query_mappings_for(["P31", "P580", "Q5", "Q80"])
        self.assertIn("P31", mapper.source_property_types)
        self.assertIn("P580", mapper.source_property_types)
        self.assertIn("P2", mapper.target_property_types)
        self.assertEqual(WbiDataTypes.WIKIBASE_ITEM, mapper.source_property_types.get("P31"))
        self.assertEqual(WbiDataTypes.WIKIBASE_ITEM, mapper.target_property_types.get("P2"))
