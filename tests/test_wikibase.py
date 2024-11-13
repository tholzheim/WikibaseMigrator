import unittest

from wikibasemigrator.wikibase import WikibaseEntityTypes


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
