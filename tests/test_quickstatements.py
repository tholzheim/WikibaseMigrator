import unittest

from wikibaseintegrator import WikibaseIntegrator

from wikibasemigrator.qsgenerator import QuickStatementsGenerator


class TestQuickStatementsGenerator(unittest.TestCase):
    def test_generation(self):
        """
        Q77966361
        :return:
        """
        wbi = WikibaseIntegrator()
        # Q77966361
        entity = wbi.item.get("Q80", mediawiki_api_url="https://www.wikidata.org/w/api.php")
        qs_generator = QuickStatementsGenerator()
        qs = qs_generator.generate_item(entity)
        print(qs)

    def test_generation_of_new_item(self):
        """
        test generation of new item
        """
        wbi = WikibaseIntegrator()
        new_item = wbi.item.new()
        new_item.labels.set("en", "New item")
        new_item.labels.set("fr", "Nouvel élément")
        qs_generator = QuickStatementsGenerator()
        qs = qs_generator.generate_item(new_item)
        expected_qs = """CREATE\nLAST|Len|"New item"\nLAST|Lfr|"Nouvel élément\""""
        self.assertEqual(qs, expected_qs)


if __name__ == "__main__":
    unittest.main()
