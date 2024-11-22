import json
import logging
from collections.abc import Callable, Generator
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from wikibaseintegrator import WikibaseIntegrator, datatypes, wbi_login
from wikibaseintegrator.entities import ItemEntity, LexemeEntity, MediaInfoEntity, PropertyEntity
from wikibaseintegrator.models import Qualifiers, Reference, References, Snak
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_enums import WikibaseSnakType
from wikibaseintegrator.wbi_exceptions import MissingEntityException, NonExistentEntityError
from wikibaseintegrator.wbi_helpers import mediawiki_api_call_helper

from wikibasemigrator import WbEntity
from wikibasemigrator.exceptions import UnknownEntityTypeException
from wikibasemigrator.mapper import WikibaseItemMapper
from wikibasemigrator.model.profile import EntityBackReferenceType, WikibaseConfig, WikibaseMigrationProfile
from wikibasemigrator.wikibase import Query, WikibaseEntityTypes, get_default_user_agent

logger = logging.getLogger(__name__)

wbi_config["USER_AGENT"] = "WikibaseMigrator/1.0 (https://www.wikidata.org/wiki/User:tholzheim)"


class ItemTranslationResult(BaseModel):
    """
    wikibase migration translation result of an item
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    item: WbEntity
    original_item: WbEntity
    missing_properties: list[str] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)
    item_mapping: dict[str, str | None] = Field(default_factory=dict)
    created_entity: WbEntity | None = None
    errors: list[str] = Field(default_factory=list)

    def add_missing_property(self, property_id: str):
        """
        add missing property
        :param property_id:
        :return:
        """

        self.missing_properties.append(property_id)

    def add_missing_item(self, item_id: str):
        """
        add missing item
        :param item_id:
        :return:
        """
        self.missing_items.append(item_id)

    def add_item_mapping(self, source_id: str, target_id: str | None):
        """
        add given mapping to mappings
        :param source_id:
        :param target_id:
        :return:
        """
        self.item_mapping[source_id] = target_id

    def add_item_mappings(self, mappings: dict[str, str | None]):
        """
        Update mappings with given mappings
        :param mappings:
        :return:
        """
        self.item_mapping.update(mappings)


class ItemSetTranslationResult(BaseModel):
    # ToDo: refactor to entitities
    items: dict[str, ItemTranslationResult] = Field(default_factory=dict)

    @classmethod
    def from_list(cls, items: list[ItemTranslationResult]) -> "ItemSetTranslationResult":
        res = ItemSetTranslationResult()
        for item in items:
            res.items[item.original_item.id] = item
        return res

    def get_created_entities(self) -> list[WbEntity]:
        return [entity.created_entity for entity in self.items.values()]

    def get_missing_properties(self) -> list[str]:
        """
        Get missing properties
        :return: list of missing properties
        """
        missing = set()
        for item in self.items.values():
            missing.update(item.missing_properties)
        return list(missing)

    def get_missing_items(self) -> list[str]:
        missing = set()
        for item in self.items.values():
            missing.update(item.missing_items)
        return list(missing)

    def get_mapping(self) -> dict[str, str | None]:
        """
        Get all mappings that are used
        :return:
        """
        mapping = dict()
        for item in self.items.values():
            mapping.update(item.item_mapping)
        return mapping

    def get_existing_mappings(self) -> dict[str, str]:
        """
        Get all existing mappings
        :return:
        """
        return {key: value for key, value in self.get_mapping().items() if value is not None}

    def get_missing_mappings(self) -> list[str]:
        """
        Get all missing mappings
        :return:
        """
        return [key for key, value in self.get_mapping().items() if value is None]

    def get_missing_item_mapings(self) -> list[str]:
        """
        Get all missing item mappings
        :return:
        """
        return [value for value in self.get_missing_mappings() if value.startswith("Q")]

    def get_missing_property_mapings(self) -> list[str]:
        """
        Get all missing property mappings
        :return:
        """
        return [value for value in self.get_missing_mappings() if value.startswith("P")]

    def get_translation_source_item_ids(self):
        """
        Get IDs of all main source items
        :return:
        """
        return [item.original_item.id for item in self.items.values()]

    def get_target_entities(self) -> list[WbEntity]:
        """
        Get all target items
        """
        return [translation_result.item for translation_result in self.items.values()]

    def get_source_entities(self) -> list[WbEntity]:
        """
        Get all source items
        """
        return [translation_result.original_item for translation_result in self.items.values()]

    def get_source_entity_ids(self) -> list[str]:
        """
        Get IDs of all source entities that are used
        """
        return [entity_id for entity_id in self.get_mapping()]

    def get_target_entity_ids(self) -> list[str]:
        """
        Get IDs of all target entities that are used
        """
        return [entity_id for entity_id in self.get_mapping().values()]

    def get_source_root_entity_ids(self):
        """
        Get IDs of all source items to migrate.
        Only the "subject" ids no ids used in any statement, qualifier or reference
        """
        return [item.id for item in self.get_source_entities() if item.id]

    def get_translation_result_by_source_id(self, source_id: str) -> ItemTranslationResult | None:
        """
        Get TranslationResult by source id
        :param source_id:
        :return:
        """
        for item in self.items.values():
            if item.original_item.id == source_id:
                return item
        return None

    def __iter__(self) -> Generator[ItemTranslationResult, None, None]:
        yield from self.items.values()


class WikibaseMigrator:
    """
    migrates wikibase objects from one instance to another
    """

    def __init__(self, profile: WikibaseMigrationProfile):
        self._source_wbi = None
        self._target_wbi = None
        self.profile = profile
        self.mapper = WikibaseItemMapper(self.profile)

    @property
    def target_wbi(self) -> WikibaseIntegrator:
        if self._target_wbi is None:
            self._target_wbi = self.get_wikibase_integrator(self.profile.target)
        return self._target_wbi

    @property
    def source_wbi(self) -> WikibaseIntegrator:
        if self._source_wbi is None:
            self._source_wbi = self.get_wikibase_integrator(self.profile.source)
        return self._source_wbi

    def get_items_from_source(self, item_ids: list[str]) -> list[WbEntity]:
        return self.get_items(item_ids, self.profile.source, self.source_wbi)

    def get_items_from_target(self, item_ids: list[str]) -> list[WbEntity]:
        return self.get_items(item_ids, self.profile.target, self.target_wbi)

    def get_items(
        self, item_ids: list[str], wikibase_config: WikibaseConfig, wbi: WikibaseIntegrator, max_workers: int = 10
    ) -> list[WbEntity]:
        # ToDo: WARNING:urllib3.connectionpool:Connection pool is full, [...] Connection pool size: 10  # noqa: E501
        result: list[WbEntity] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for chunk in Query.chunks(item_ids, 50):
                future = executor.submit(self.get_entity_batch, entity_ids=chunk, wbi=wbi)
                futures.append(future)
            for future in as_completed(futures):
                entity_chunk = future.result()
                result.extend(entity_chunk)
        logger.debug(len(result))
        return result

    @staticmethod
    def get_entity_batch(
        entity_ids: list[str], wbi: WikibaseIntegrator, allow_anonymous: bool = True, **kwargs
    ) -> list[WbEntity]:
        """
        Get entities in batches from the wikibase
        :param entity_ids:
        :return:
        """
        entity_ids_param = "|".join(entity_ids)
        params = {"action": "wbgetentities", "ids": entity_ids_param, "format": "json"}

        login = wbi.login
        is_bot = wbi.is_bot
        start = datetime.now()
        lod = mediawiki_api_call_helper(
            data=params, login=login, allow_anonymous=allow_anonymous, is_bot=is_bot, **kwargs
        )
        logger.debug(f"Querying entity batch of {len(entity_ids)} entities took {datetime.now() - start}")
        if lod.get("success", False):
            entities = []
            for entity_id, record in lod.get("entities", {}).items():
                if entity_id.startswith("Q"):
                    entity = ItemEntity(api=wbi).from_json(record)
                elif entity_id.startswith("P"):
                    entity = PropertyEntity(api=wbi).from_json(record)
                elif entity_id.startswith("L"):
                    entity = LexemeEntity(api=wbi).from_json(record)
                elif entity_id.startswith("M"):
                    entity = MediaInfoEntity(api=wbi).from_json(record)
                else:
                    raise UnknownEntityTypeException(entity_id)
                entities.append(entity)
            return entities
        else:
            logger.error(f"Querying entity batches from Wikibase failed! {lod.get('warnings', '')}")
            return []

    def get_item_from_source(self, qid: str) -> WbEntity | None:
        """
        Get item from source wikibase
        :param qid: id of the item to retrieve
        :return: WbEntity or None if not existent
        """
        return self.get_item(entity_id=qid, wikibase_config=self.profile.source, wbi=self.source_wbi)

    def get_item_from_target(self, qid: str) -> WbEntity | None:
        """
        Get item from target wikibase
        :param qid: id of the item to retrieve
        :return: WbEntity or None if not existent
        """
        return self.get_item(entity_id=qid, wikibase_config=self.profile.target, wbi=self.target_wbi)

    @staticmethod
    def get_wikibase_integrator(wikibase_config: WikibaseConfig) -> WikibaseIntegrator:
        """
        Get the WikibaseIntegrator with proper login if defined
        :param wikibase_config:
        :return:
        """
        login = WikibaseMigrator.get_wikibase_login(wikibase_config)
        return WikibaseIntegrator(login=login)

    @staticmethod
    def get_wikibase_login(
        wikibase_config: WikibaseConfig,
    ) -> wbi_login.Login | wbi_login.Clientlogin | wbi_login.OAuth1 | wbi_login.OAuth2 | None:
        """
        Get a login instance for the given wikibase configuration
        :param wikibase_config:
        :return:
        """
        if wikibase_config.bot_password:
            logger.debug(f"Using Bot password as authentication for {wikibase_config.name}")
            login = wbi_login.Login(
                user=wikibase_config.user,
                password=wikibase_config.bot_password,
                mediawiki_api_url=wikibase_config.mediawiki_api_url,
                user_agent=get_default_user_agent(),
            )
        elif wikibase_config.consumer_key:
            logger.debug(f"Using OAuth2 as authentication for {wikibase_config.name}")
            login = wbi_login.OAuth2(
                consumer_token=wikibase_config.consumer_key,
                mediawiki_api_url=wikibase_config.mediawiki_api_url,
                mediawiki_rest_url=wikibase_config.mediawiki_rest_url,
                user_agent=get_default_user_agent(),
            )
        elif wikibase_config.password:
            logger.debug(f"Using ClientLogin as authentication for {wikibase_config.name}")
            login = wbi_login.Clientlogin(
                user=wikibase_config.user,
                password=wikibase_config.password,
                mediawiki_api_url=wikibase_config.mediawiki_api_url,
                user_agent=get_default_user_agent(),
            )
        else:
            login = None
        return login

    @classmethod
    def get_item(cls, entity_id: str, wikibase_config: WikibaseConfig, wbi: WikibaseIntegrator) -> WbEntity | None:
        """
        Get item from given wikibase
        :param entity_id: id of the item to retrieve
        :param wikibase_config:
        :return: WbEntity or None if not existent
        """
        try:
            mediawiki_api_url = wikibase_config.mediawiki_api_url
            logger.debug(f"Retrieving item {entity_id} from {wikibase_config.name}")
            start_time = datetime.now()
            user_agent = get_default_user_agent()
            if entity_id.startswith("Q"):
                item = wbi.item.get(entity_id, mediawiki_api_url=mediawiki_api_url, user_agent=user_agent)
            elif entity_id.startswith("P"):
                item = wbi.property.get(entity_id, mediawiki_api_url=mediawiki_api_url, user_agent=user_agent)
            elif entity_id.startswith("L"):
                item = wbi.lexeme.get(entity_id, mediawiki_api_url=mediawiki_api_url, user_agent=user_agent)
            elif entity_id.startswith("M"):
                item = wbi.mediainfo.get(entity_id, mediawiki_api_url=mediawiki_api_url, user_agent=user_agent)
            else:
                raise UnknownEntityTypeException(entity_id)
            logger.debug(f"Entity {entity_id} retrival took {(datetime.now() - start_time).total_seconds()}s")
        except NonExistentEntityError as e:
            item = None
            logger.exception(e)
        except MissingEntityException as e:
            item = None
            logger.debug(f"Item {entity_id} not found in {wikibase_config.name}")
            logger.exception(e)
        except UnknownEntityTypeException as e:
            item = None
            logger.warning(f"Unknown entity id {entity_id} type")
            logger.exception(e)
        return item

    @staticmethod
    def get_all_items_ids(item: WbEntity) -> list[str]:
        """
        Get all main items that are used in the given item either properties, property values, references.
        This does not include statement ids only proper Q and P ids
        :param item: item to extract the ids from
        :return: List of used ids
        """
        ids = set()
        ids.add(item.id)
        for claim in item.claims:
            ids.add(claim.mainsnak.property_number)
            if claim.mainsnak.datatype == "wikibase-item" and claim.mainsnak.snaktype is WikibaseSnakType.KNOWN_VALUE:
                ids.add(claim.mainsnak.datavalue["value"]["id"])
            for qualifier in claim.qualifiers:
                ids.add(qualifier.property_number)
                if qualifier.datatype == "wikibase-item" and qualifier.snaktype is WikibaseSnakType.KNOWN_VALUE:
                    ids.add(qualifier.datavalue["value"]["id"])
            for reference_block in claim.references:
                for reference in reference_block.snaks:
                    ids.add(reference.property_number)
                    if reference.datatype == "wikibase-item":
                        ids.add(reference.datavalue["value"]["id"])
        return list(ids)

    def update_item(self, item: WbEntity) -> None:
        """
        Add missing statements from source to target
        """
        raise NotImplementedError

    def prepare_mapper_cache(self, item: WbEntity):
        """
        prepare the mapper cache with the mappings for the given item
        :param item:
        :return:
        """
        used_ids = self.get_all_items_ids(item)
        self.prepare_mapper_cache_by_ids(used_ids)

    def prepare_mapper_cache_by_ids(self, item_ids: list[str]):
        """
        prepare the mapper cache with the mappings for the given item
        :param item:
        :return:
        """
        self.mapper.prepare_cache_for(item_ids)

    def add_translation_result_mappings(self, translation_result: ItemTranslationResult):
        """
        add translation mappings that are used by the item to the translation result
        :param item:
        :param translation_result:
        :return:
        """
        used_ids = self.get_all_items_ids(translation_result.original_item)
        mappings = {source_id: self.mapper.get_mapping_for(source_id) for source_id in used_ids}
        translation_result.add_item_mappings(mappings)

    def translate_items_by_id(self, item_ids: list[str]) -> ItemSetTranslationResult:
        """
        Translate the items corresponding to the given item_ids
        :param item_ids:
        :return:
        """
        items = self.get_items_from_source(item_ids)
        used_ids = set()
        for item in items:
            used_ids.update(self.get_all_items_ids(item))
        self.prepare_mapper_cache_by_ids(list(used_ids))
        # ToDo: Handle already exisitng entites in target wiki properly
        items = [item for item in items if self.mapper.get_mapping_for(item.id) is None]

        translated_items = [self.translate_item(item) for item in items]
        return ItemSetTranslationResult.from_list(translated_items)

    def translate_item(
        self,
        item: WbEntity,
        allowed_languages: list[str] | None = None,
        allowed_sitelinks: list[str] | None = None,
        with_back_reference: bool = True,
    ) -> ItemTranslationResult:
        """
        translates given item from source to target wikibase instance
        :param with_back_reference:
        :param allowed_sitelinks:
        :param allowed_languages:
        :param item: wikibase item to translate from the source wikibase instance
        :return:
        """
        if allowed_languages is None:
            allowed_languages = self.profile.get_allowed_languages()
        if allowed_sitelinks is None:
            allowed_sitelinks = self.profile.get_allowed_sidelinks()
        self.prepare_mapper_cache(item)
        match item.ETYPE:
            case WikibaseEntityTypes.ITEM:
                new_item = self.target_wbi.item.new()
            case WikibaseEntityTypes.PROPERTY:
                new_item = self.target_wbi.property.new()
                new_item.datatype = item.datatype
            case WikibaseEntityTypes.MEDIAINFO:
                new_item = self.target_wbi.mediainfo.new()
            case WikibaseEntityTypes.LEXEME:
                new_item = self.target_wbi.lexeme.new()
                # ToDo: Translate lemmas
                # ToDo: Translate forms
                # ToDo: Translate senses
            case _:
                raise ValueError(f"Unsupported item type: {type(item)}")
        result = ItemTranslationResult(item=new_item, original_item=item, missing_properties=[], missing_items=[])
        self.add_translation_result_mappings(result)
        # add label
        for label in item.labels:
            if label.language not in allowed_languages:
                continue
            new_item.labels.set(label.language, label.value)
        for description in item.descriptions:
            if description.language not in allowed_languages:
                continue
            desc_value = description.value
            if desc_value == item.labels.get(description.language):
                # Workaround for label=description validation error → https://github.com/wikimedia/mediawiki-extensions-Wikibase/blob/ae95f990c447a6470667fd16d5b1513003e74cee/repo/i18n/en.json#L190C50-L190C121
                # ToDo: Decide how to handle this
                continue
            new_item.descriptions.set(description.language, description.value)
        for language, aliases in item.aliases.aliases.items():
            if language not in allowed_languages:
                continue
            alias_values = [alias.value for alias in aliases]
            new_item.aliases.set(language, alias_values)
        if item.ETYPE in WikibaseEntityTypes.support_sidelinks():
            for sitelink in item.sitelinks.sitelinks.values():
                if sitelink.site not in allowed_sitelinks:
                    continue
                # ToDo: badges also require a mapping → currently not queried
                new_item.sitelinks.set(site=sitelink.site, title=sitelink.title)
        for claim in item.claims:
            new_qualifiers = Qualifiers()
            for qualifier in claim.qualifiers:
                new_qualifier = self._translate_snak(qualifier, translation_result=result)
                if new_qualifier is not None:
                    new_qualifiers.add(new_qualifier)
                else:
                    # ToDo: Handle missing property in target
                    pass
            new_references = References()
            for reference in claim.references:
                new_reference = Reference()
                for snak in reference.snaks:
                    new_snak = self._translate_snak(snak, translation_result=result)
                    if new_snak is not None:
                        new_reference.add(new_snak)
                    else:
                        # ToDo: Handle missing property in target
                        pass
                if len(new_reference.snaks) > 0:
                    new_references.add(new_reference)
            new_claim = self._translate_snak(
                claim.mainsnak, translation_result=result, qualifiers=new_qualifiers, references=new_references
            )
            if new_claim is not None:
                new_item.claims.add(new_claim)
            else:
                # ToDo: Handle missing property in target
                pass
        if with_back_reference:
            self.add_back_reference(new_item, item.id)
        return result

    def _translate_snak(
        self, snak: Snak, translation_result: ItemTranslationResult, **kwargs
    ) -> datatypes.BaseDataType | None:
        """

        :param snak: snak to translate
        :param translation_result: translation result to store missing property and item information
        :param kwargs: additional arguments to pass to the translated snak for example references and qualifiers
        :return: Translated snak
        """
        if self.profile.mapping.ignore_unknown_values and snak.snaktype is WikibaseSnakType.UNKNOWN_VALUE:
            return None
        if self.profile.mapping.ignore_no_value and snak.snaktype is WikibaseSnakType.NO_VALUE:
            return None
        new_property_number = self.mapper.get_mapping_for(snak.property_number)
        if new_property_number is None:
            translation_result.add_missing_property(snak.property_number)
            return None
        new_snak = None
        match snak.datatype:
            case "string":
                new_snak = datatypes.String(
                    prop_nr=new_property_number, value=snak.datavalue["value"], snaktype=snak.snaktype, **kwargs
                )
            case "external-id":
                new_snak = datatypes.ExternalID(
                    prop_nr=new_property_number, value=snak.datavalue["value"], snaktype=snak.snaktype, **kwargs
                )
            case "wikibase-item":
                source_id = snak.datavalue.get("value", {}).get("id", None)
                mapped_id = self.mapper.get_mapping_for(source_id) if source_id else None
                if mapped_id or snak.snaktype != WikibaseSnakType.KNOWN_VALUE:
                    new_snak = datatypes.Item(
                        prop_nr=new_property_number, value=mapped_id, snaktype=snak.snaktype, **kwargs
                    )
                else:
                    translation_result.add_missing_item(snak.datavalue["value"]["id"])
                    new_snak = None
            case "time":
                match snak.snaktype:
                    case WikibaseSnakType.KNOWN_VALUE:
                        new_snak = datatypes.Time(
                            prop_nr=new_property_number,
                            time=snak.datavalue["value"]["time"],
                            before=snak.datavalue["value"]["before"],
                            after=snak.datavalue["value"]["after"],
                            precision=snak.datavalue["value"]["precision"],
                            # calendar does not need to be mapped
                            calendarmodel=snak.datavalue["value"]["calendarmodel"],
                            timezone=snak.datavalue["value"]["timezone"],
                            snaktype=snak.snaktype,
                            **kwargs,
                        )
                    case _:
                        new_snak = datatypes.Time(
                            snaktype=snak.snaktype,
                            **kwargs,
                        )

            case "commonsMedia":
                new_snak = datatypes.CommonsMedia(
                    prop_nr=new_property_number, value=snak.datavalue["value"], snaktype=snak.snaktype, **kwargs
                )
            case "quantity":
                new_snak = datatypes.Quantity(
                    prop_nr=new_property_number,
                    amount=snak.datavalue["value"]["amount"],
                    # unit=snak.datavalue["value"]["unit"],
                    # ToDo: Needs to look up unit item mapping but is currently not mapped
                    upper_bound=snak.datavalue["value"].get("upper_bound", None),
                    lower_bound=snak.datavalue["value"].get("lower_bound", None),
                    snaktype=snak.snaktype,
                    **kwargs,
                )
            case "monolingualtext":
                new_snak = datatypes.MonolingualText(
                    prop_nr=new_property_number,
                    text=snak.datavalue["value"].get("text", None),
                    language=snak.datavalue["value"].get("language", None),
                    snaktype=snak.snaktype,
                    **kwargs,
                )
            case "globecoordinate":
                new_snak = datatypes.GlobeCoordinate(
                    prop_nr=new_property_number,
                    latitude=snak.datavalue["value"].get("latitude", None),
                    longitude=snak.datavalue["value"].get("longitude", None),
                    altitude=snak.datavalue["value"].get("altitude", None),
                    precision=snak.datavalue["value"].get("precision", None),
                    snaktype=snak.snaktype,
                    # globe=snak.datavalue["value"].get("globe", None),
                    # ToDo: Needs to look up globe item mapping but is currently not mapped
                    **kwargs,
                )
            case "entity-schema":
                new_snak = datatypes.EntitySchema(
                    prop_nr=new_property_number, value=snak.datavalue["value"], snaktype=snak.snaktype, **kwargs
                )
            case "url":
                new_snak = datatypes.URL(
                    prop_nr=new_property_number, value=snak.datavalue["value"], snaktype=snak.snaktype, **kwargs
                )
            case "property":
                new_snak = datatypes.Property(
                    prop_nr=new_property_number, value=snak.datavalue["value"], snaktype=snak.snaktype, **kwargs
                )
            case "geo-shape":
                # ToDo: links to a file in mediawiki commons → how to translate map to same file or also copy file
                new_snak = datatypes.GeoShape(
                    prop_nr=new_property_number, value=snak.datavalue["value"], snaktype=snak.snaktype, **kwargs
                )
            case "tabular-data":
                # ToDo: links to a file in mediawiki commons → how to translate map to same file or also copy file
                new_snak = datatypes.TabularData(
                    prop_nr=new_property_number, value=snak.datavalue["value"], snaktype=snak.snaktype, **kwargs
                )
        return new_snak

    def add_back_reference(self, entity: ItemEntity, source_id: str) -> None:
        """
        Add back reference to the given entity. The kind of backreference is read from the profile config.
        :param entity:
        :param source_id:
        :return:
        """
        if self.profile.back_reference is None:
            logger.debug(f"No backreference defined: adding no back reference to {entity.id}")
            return
        match entity.ETYPE:
            case WikibaseEntityTypes.ITEM:
                back_reference = self.profile.back_reference.item
            case WikibaseEntityTypes.PROPERTY:
                back_reference = self.profile.back_reference.property
            case _:
                # ToDo: add support for other types
                logger.warning(f"Back reference not defined for type {type(entity)}")
                return
        match back_reference.reference_type:
            case EntityBackReferenceType.SIDELINK:
                if entity.ETYPE in WikibaseEntityTypes.support_sidelinks():
                    entity.sitelinks.set(site=back_reference.property_id, title=source_id)
                else:
                    logger.warning(f"Type {entity.ETYPE} does not support sidelinks define a different back reference")
                    raise ValueError("Unsupported back reference type and property combination")
            case EntityBackReferenceType.PROPERTY:
                claim = datatypes.ExternalID(
                    prop_nr=back_reference.property_id,
                    value=source_id,
                )
                entity.add_claims(claim)

    def migrate_entities_to_target(
        self,
        translations: ItemSetTranslationResult,
        summary: str,
        entity_done_callback: Callable[[Future], None] | None = None,
    ) -> list[ItemEntity | PropertyEntity]:
        """
        migrate given entities to the target wikibase instance
        :param translations:
        :param summary: summary of the changes
        :param entity_done_callback: callback function to call for each migrated entity e.g. for progress tracking
        :return: list of migrated entities containing the new ID in case of creation
        """
        logger.info(f"Migrating {len(translations.items)} entities to target {self.profile.target.name}: {summary}")
        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            login = self.get_wikibase_login(self.profile.target)
            for entity in translations:
                future = executor.submit(
                    self._migrate_entity,
                    entity=entity,
                    summary=summary,
                    mediawiki_api_url=self.profile.target.mediawiki_api_url,
                    tags=self.profile.target.get_tags(),
                    login=login,
                )
                futures.append(future)
                if entity_done_callback:
                    future.add_done_callback(entity_done_callback)
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
            return results

    @staticmethod
    def _migrate_entity(
        entity: ItemTranslationResult,
        mediawiki_api_url: str,
        summary: str | None = None,
        tags: list[str] | None = None,
        login: wbi_login.Login | wbi_login.Clientlogin | wbi_login.OAuth1 | wbi_login.OAuth2 | None = None,
    ) -> ItemTranslationResult:
        """
        migrates given entity to the given wikibase instance (url)
        :param entity: entity to migrate
        :param mediawiki_api_url: wikibase api url of the wikibase to store
        :param summary: summary of the changes
        :param tags: tags to add to the revision
        :return: entity with the ID
        """
        try:
            entity_json = entity.item.get_json()
            if logger.level <= logging.DEBUG:
                path = Path(f"/tmp/WikibaseMigrator/migrations/{datetime.now()}_{entity.original_item.id}.json")
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "w") as f:
                    json.dump(entity_json, f)
            res = entity.item.write(mediawiki_api_url=mediawiki_api_url, summary=summary, tags=tags, login=login)
            entity.created_entity = res
        except Exception as e:
            logger.info(f"Failed to migrate entity {entity.original_item.id}")
            entity.errors.append(str(e))
            logger.exception(e)
        return entity
