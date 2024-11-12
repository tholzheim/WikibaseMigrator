import base64
import hashlib
import logging
import os
import re
from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from wikibasemigrator.wikibase import MediaWikiEndpoint

logger = logging.getLogger(__name__)


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
    tag: str | None = None

    def __post_init__(self):
        if isinstance(self.user, str) and self.user.strip() == "":
            self.user = None
        if isinstance(self.password, str) and self.password.strip() == "":
            self.password = None

    def get_tags(self) -> list[str]:
        tags = []
        if self.tag is not None:
            tags.append(self.tag)
        return tags

    def get_oauth_url(self) -> str:
        code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8")
        code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)
        code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
        code_challenge = code_challenge.replace("=", "")
        params = {
            "response_type": "code",
            "client_id": self.consumer_key,
            # "scope": "openid",
            "redirect_uri": "http://localhost:8009/oauth_callback",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.mediawiki_rest_url}/oauth2/authorize?{query}"


class EntityMappingConfig(BaseModel):
    """
    configuration for extracting the item mapping between source and target
    """

    location_of_mapping: str
    item_mapping_query: str
    property_mapping_query: str
    languages: list[str] | None = None
    sidelinks: list[str] | None = None


class EntityBackReferenceType(str, Enum):
    SIDELINK = "Sidelink"
    PROPERTY = "Property"


class EntityBackReference(BaseModel):
    """
    defines how to store the backreference e.g with a property or sitelink
    """

    reference_type: EntityBackReferenceType = Field(..., alias="type")
    property_id: str = Field(..., alias="id")


class BackReference(BaseModel):
    """
    defines the back reference for items and proeprties
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
    back_reference: BackReference

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

    def get_allowed_sidelinks(self) -> list[str]:
        if self.mapping.sidelinks is None:
            self.mapping.sidelinks = ["enwiki", "dewiki", "wikidatawiki"]
        return self.mapping.sidelinks


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
