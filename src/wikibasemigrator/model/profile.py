import logging
from enum import Enum
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from wikibasemigrator.wikibase import MediaWikiEndpoint

logger = logging.getLogger(__name__)


class UserToken(BaseModel):
    """
    Wikibase user access token
    """

    oauth_token: str
    oauth_token_secret: str
    oauth_callback_confirmed: bool


class WikibaseConfig(BaseModel):
    """
    configuration for a wikibase api
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str
    sparql_url: HttpUrl
    mediawiki_api_url: HttpUrl
    mediawiki_rest_url: HttpUrl
    website: HttpUrl
    item_prefix: HttpUrl
    quickstatement_url: HttpUrl | None = None
    user: str | None = None
    password: str | None = None
    bot_password: str | None = None
    consumer_key: str | None = None
    consumer_secret: str | None = None
    requires_login: bool = True
    user_token: UserToken | None = None
    tag: str | None = None

    def __post_init__(self):
        if isinstance(self.user, str) and self.user.strip() == "":
            self.user = None
        if isinstance(self.password, str) and self.password.strip() == "":
            self.password = None

    def get_tags(self) -> list[str]:
        """
        Get tags that should be added to the edits of the WikibaseMigrator
        :return:
        """
        tags = []
        if self.tag is not None:
            tags.append(self.tag)
        return tags

    def requires_user_login(self):
        """
        Returns True if the a user login is required, False otherwise
        """
        return


class MigrationWikibaseLocation(str, Enum):
    """
    location of where to look for the mapping
    """

    SOURCE = "source"
    TARGET = "target"


class TypeCastConfig(BaseModel):
    """
    configuration for a type cast in case of a property type mismatch
    """

    enabled: Annotated[
        bool,
        Field(description="If True property type casting is applied if there is a mismatch between source and target"),
    ] = True
    fallback_language: Annotated[
        str, Field(description="Language to use when casting from a value without to a value with langauge")
    ] = "mul"


class EntityMappingConfig(BaseModel):
    """
    configuration for extracting the item mapping between source and target
    """

    location_of_mapping: MigrationWikibaseLocation = MigrationWikibaseLocation.TARGET
    item_mapping_query: str
    property_mapping_query: str
    languages: list[str] | None = None
    sitelinks: list[str] | None = None
    ignore_no_values: bool = False
    ignore_unknown_values: bool = False


class EntityBackReferenceType(str, Enum):
    SITELINK = "Sitelink"
    PROPERTY = "Property"


class EntityBackReference(BaseModel):
    """
    defines how to store the backreference e.g with a property or sitelink
    """

    reference_type: EntityBackReferenceType = Field(..., alias="type")
    property_id: str = Field(..., alias="id")


class BackReference(BaseModel):
    """
    defines the back reference for items and properties
    """

    item: EntityBackReference
    property: EntityBackReference


class WikibaseMigrationProfile(BaseModel):
    """
    Wikibase migration profile configuration
    """

    name: str
    description: str
    source: WikibaseConfig
    target: WikibaseConfig
    mapping: EntityMappingConfig
    back_reference: BackReference | None = None
    type_casts: TypeCastConfig = TypeCastConfig()

    def get_wikibase_config_by_name(self, name: str) -> WikibaseConfig | None:
        """
        Get wikibase config by name
        :param name: name of the wikibase config
        :return: WikibaseConfig
        """
        config = None
        if self.source.name == name:
            config = self.source
        elif self.target.name == name:
            config = self.target
        return config

    def get_allowed_languages(self) -> list[str]:
        if self.mapping.languages is None:
            supported_languages = MediaWikiEndpoint.get_supported_languages(self.target.mediawiki_api_url)
            allowed_languages = [value for value in supported_languages]
            self.mapping.languages = allowed_languages
        return self.mapping.languages

    def get_allowed_sitelinks(self) -> list[str]:
        if self.mapping.sitelinks is None:
            self.mapping.sitelinks = []
        return self.mapping.sitelinks

    def get_wikibase_config_of_mapping_location(self) -> WikibaseConfig:
        """
        Get the wikibase config of the wikibase that stores the mappings
        """
        match self.mapping.location_of_mapping:
            case MigrationWikibaseLocation.SOURCE:
                return self.source
            case MigrationWikibaseLocation.TARGET:
                return self.target
            case _:
                raise ValueError("Unknown mapping location")


def load_profile(path: Path) -> WikibaseMigrationProfile:
    """
    load Wikibase migration profile

    :param path: path to config file
    :return: Wikibase migration profile
    """
    with open(path) as stream:
        try:
            config_raw = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            logger.debug("Failed to parse config file")
            logger.error(exc)
            raise exc
    config = WikibaseMigrationProfile.model_validate(config_raw)
    return config
