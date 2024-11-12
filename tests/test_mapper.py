import unittest
from pathlib import Path

from wikibasemigrator.mapper import WikibaseItemMapper
from wikibasemigrator.model.profile import load_profile


class TestWikibaseItemMapper(unittest.TestCase):
    def test_querying_mapping(self):
        path = Path(__file__).parent.joinpath("../src/wikibasemigrator/profiles/FactGrid.yaml")
        config = load_profile(path)
        mapper = WikibaseItemMapper(config)
        mapping = mapper.get_mapping_for("Q183")
        self.assertEqual("Q140530", mapping)
        self.assertEqual("P2", mapper.get_mapping_for("P31"))


if __name__ == "__main__":
    unittest.main()
