from enum import Enum


class WbiDataTypes(str, Enum):
    """
    WikibaseIntegrator data types
    """

    STRING = "string"
    EXTERNAL_ID = "external-id"
    WIKIBASE_ITEM = "wikibase-item"
    TIME = "time"
    COMMONS_MEDIA = "commonsMedia"
    QUANTITY = "quantity"
    MONOLINGUALTEXT = "monolingualtext"
    GLOBE_COORDINATE = "globe-coordinate"
    ENTITY_SCHEMA = "entity-schema"
    URL = "url"
    PROPERTY = "property"
    GEO_SHAPE = "geo-shape"
    TABUlAR_DATA = "tabulated-data"
    MATH = "math"
    SENSE = "wikibase-sense"
    MUSICAL_NOTATION = "musical-notation"
    LEXEME = "wikibase-lexeme"
    FORM = "wikibase-form"
    BASE_DATATYPE = "base-data-type"
    LOCAL_MEDIA = "localMedia"
    EDTF = "edtf"


class WikidataDataTypes(str, Enum):
    """
    wikidata data types
    """

    STRING = "String"
    EXTERNAL_ID = "ExternalId"
    WIKIBASE_ITEM = "WikibaseItem"
    TIME = "Time"
    COMMONS_MEDIA = "CommonsMedia"
    QUANTITY = "Quantity"
    MONOLINGUALTEXT = "Monolingualtext"
    GLOBE_COORDINATE = "GlobeCoordinate"
    ENTITY_SCHEMA = "EntitySchema"
    URL = "Url"
    PROPERTY = "WikibaseProperty"
    GEO_SHAPE = "GeoShape"
    TABUlAR_DATA = "TabularData"
    MATH = "Math"
    SENSE = "WikibaseSense"
    MUSICAL_NOTATION = "MusicalNotation"
    LEXEME = "WikibaseLexeme"
    FORM = "WikibaseForm"

    def get_wbi_type(self) -> WbiDataTypes:
        return WbiDataTypes[self.name]
