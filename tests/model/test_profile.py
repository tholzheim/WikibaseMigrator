import unittest
from pathlib import Path

from wikibasemigrator.model.profile import WikibaseMigrationProfile, load_profile


class TestWikibaseMigrationProfile(unittest.TestCase):
    """
    test WikibaseMigrationProfile
    """

    def setUp(self):
        """
        setup test case
        """
        self.profile_dir = Path(__file__).parent.joinpath("../../src/wikibasemigrator/profiles")
        self.profile = load_profile(self.profile_dir / "WikibaseMigrationTest.yaml")

    def test_loading_of_migration_profile(self):
        """
        test loading of migration profile
        """
        path = self.profile_dir / "FactGrid.yaml"
        config = load_profile(path)
        self.assertIsInstance(config, WikibaseMigrationProfile)

    def test_get_tags(self):
        """
        test get_tags
        """
        path = self.profile_dir / "WikibaseMigrationTest.yaml"
        profile = load_profile(path)
        tags = profile.target.get_tags()
        self.assertIsInstance(tags, list)
        self.assertEqual(len(tags), 1)

    def test_get_wikibase_config_by_name(self):
        """
        test get_wikibase_config_by_name
        """
        path = self.profile_dir / "WikibaseMigrationTest.yaml"
        profile = load_profile(path)
        expected_configs = [profile.source, profile.target]
        for expected_config in expected_configs:
            actual_config = profile.get_wikibase_config_by_name(expected_config.name)
            self.assertEqual(actual_config, expected_config)

    def test_get_allowed_sitelinks(self):
        """
        test get_allowed_sitelinks
        """
        allowed_sidelinks = self.profile.get_allowed_sitelinks()
        self.assertIsInstance(allowed_sidelinks, list)
        self.assertGreaterEqual(len(allowed_sidelinks), 1)

    def test_get_allowed_languages(self):
        """
        test get_allowed_languages
        """
        allowed_languages = self.profile.get_allowed_languages()
        self.assertIsInstance(allowed_languages, list)
        self.assertGreaterEqual(len(allowed_languages), 1)


if __name__ == "__main__":
    unittest.main()
