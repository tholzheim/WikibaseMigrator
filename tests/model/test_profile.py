import unittest
from pathlib import Path

from wikibasemigrator.model.profile import WikibaseMigrationProfile, load_profile


class TestWikibaseMigrationProfile(unittest.TestCase):
    def test_loading_of_migration_profile(self):
        path = Path(__file__).parent.joinpath("../../src/wikibasemigrator/profiles/FactGrid.yaml")
        config = load_profile(path)
        self.assertIsInstance(config, WikibaseMigrationProfile)


if __name__ == "__main__":
    unittest.main()
