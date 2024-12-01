import unittest

from pydantic import HttpUrl

from wikibasemigrator.wikibase import MediaWikiEndpoint, Query, WikibaseEntityTypes


class TestWikibaseEntityTypes(unittest.TestCase):
    """
    Test WikibaseEntityTypes
    """

    def test_wikibase_entity_types(self):
        """
        Test matching of enum values
        :return:
        """

        def match_case_test(value: str):
            """
            test python match case clause on string enums
            :param value:
            :return:
            """
            match value:
                case WikibaseEntityTypes.BASE_ENTITY:
                    return WikibaseEntityTypes.BASE_ENTITY
                case WikibaseEntityTypes.ITEM:
                    return WikibaseEntityTypes.ITEM
                case WikibaseEntityTypes.PROPERTY:
                    return WikibaseEntityTypes.PROPERTY
                case WikibaseEntityTypes.MEDIAINFO:
                    return WikibaseEntityTypes.MEDIAINFO
                case WikibaseEntityTypes.LEXEME:
                    return WikibaseEntityTypes.LEXEME

        for entity_type in WikibaseEntityTypes:
            value = match_case_test(entity_type.value)
            self.assertEqual(value, entity_type)

    def test_chunking(self):
        """
        test chunking
        """
        expected = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        for i, chunk in enumerate(Query.chunks([i for i in range(1, 10)], 3)):
            self.assertEqual(chunk, expected[i])

    def test_check_availability_of_sparql_endpoint(self):
        """
        Test check_availability_of_sparql_endpoint
        """
        url = HttpUrl("https://query.wikidata.org/sparql")
        self.assertTrue(Query.check_availability_of_sparql_endpoint(url))


class TestMediaWikiEndpoint(unittest.TestCase):
    """
    Test MediaWikiEndpoint
    """

    def test_check_availability(self):
        """
        Test check_availability
        """
        url = HttpUrl("https://database.factgrid.de/w/api.php")
        self.assertTrue(MediaWikiEndpoint.check_availability(url))
