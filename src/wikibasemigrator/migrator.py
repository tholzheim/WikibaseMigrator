import json
import logging
import tempfile
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from wikibaseintegrator import WikibaseIntegrator, datatypes, wbi_login
from wikibaseintegrator.datatypes import BaseDataType
from wikibaseintegrator.entities import ItemEntity, LexemeEntity, MediaInfoEntity, PropertyEntity
from wikibaseintegrator.models import Claim, Qualifiers, Reference, References, Snak
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.wbi_enums import ActionIfExists, WikibaseSnakType
from wikibaseintegrator.wbi_exceptions import MissingEntityException, MWApiError, NonExistentEntityError
from wikibaseintegrator.wbi_helpers import mediawiki_api_call_helper

from wikibasemigrator import WbEntity
from wikibasemigrator.exceptions import UnknownEntityTypeException, UserLoginRequiredException
from wikibasemigrator.mapper import WikibaseItemMapper
from wikibasemigrator.merger import EntityMerger
from wikibasemigrator.model.profile import EntityBackReferenceType, WikibaseConfig, WikibaseMigrationProfile
from wikibasemigrator.model.translations import EntitySetTranslationResult, EntityTranslationResult
from wikibasemigrator.wikibase import Query, WbiDataTypes, WikibaseEntityTypes, get_default_user_agent

logger = logging.getLogger(__name__)

wbi_config["USER_AGENT"] = "WikibaseMigrator/1.0 (https://www.wikidata.org/wiki/User:tholzheim)"


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
                future = executor.submit(
                    self.get_entity_batch, entity_ids=chunk, wbi=wbi, wikibase_config=wikibase_config
                )
                futures.append(future)
            for future in as_completed(futures):
                entity_chunk = future.result()
                result.extend(entity_chunk)
        logger.debug(f"Retrieved {len(result)} entity records")
        return result

    @staticmethod
    def get_entity_batch(
        entity_ids: list[str], wikibase_config: WikibaseConfig, wbi: WikibaseIntegrator, **kwargs
    ) -> list[WbEntity]:
        """
        Get entities in batches from the wikibase
        :param entity_ids:
        :return:
        """
        entity_ids_param = "|".join(entity_ids)
        params = {"action": "wbgetentities", "ids": entity_ids_param, "format": "json"}

        login = wbi.login
        allow_anonymous = login is None
        is_bot = wbi.is_bot
        start = datetime.now()
        lod = mediawiki_api_call_helper(
            mediawiki_api_url=wikibase_config.mediawiki_api_url,
            data=params,
            login=login,
            allow_anonymous=allow_anonymous,
            is_bot=is_bot,
            **kwargs,
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
                mediawiki_api_url=wikibase_config.mediawiki_api_url.unicode_string(),
                user_agent=get_default_user_agent(),
            )
        elif wikibase_config.consumer_key:
            logger.debug(f"Using OAuth1 as authentication for {wikibase_config.name}")
            access_token = None
            access_secret = None
            if wikibase_config.user_token is not None:
                access_token = wikibase_config.user_token.oauth_token
                access_secret = wikibase_config.user_token.oauth_token_secret
            if access_token is None or access_secret is None:
                raise UserLoginRequiredException()
            login = wbi_login.OAuth1(
                consumer_token=wikibase_config.consumer_key,
                consumer_secret=wikibase_config.consumer_secret,
                access_token=access_token,
                access_secret=access_secret,
                mediawiki_api_url=wikibase_config.mediawiki_api_url.unicode_string(),
                user_agent=get_default_user_agent(),
            )
        elif wikibase_config.password:
            logger.debug(f"Using ClientLogin as authentication for {wikibase_config.name}")
            login = wbi_login.Clientlogin(
                user=wikibase_config.user,
                password=wikibase_config.password,
                mediawiki_api_url=wikibase_config.mediawiki_api_url.unicode_string(),
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

    @classmethod
    def get_all_entity_ids(cls, entity: WbEntity) -> list[str]:
        """
        Get all main entity IDs that are used in the given item either properties, property values, references.
        This does not include statement ids only proper Q and P ids
        :param entity: item to extract the ids from
        :return: List of used ids
        """
        ids = set()
        ids.add(entity.id)
        for claim in entity.claims:
            ids.add(claim.mainsnak.property_number)
            unit = cls.get_unit_id(claim.mainsnak)
            if unit is not None:
                ids.add(unit)
            if cls._is_item_and_known_value(claim.mainsnak):
                ids.add(claim.mainsnak.datavalue["value"]["id"])
            ids_used_in_qualifiers = cls.get_all_entity_ids_from_qualifiers(claim.qualifiers)
            ids.update(ids_used_in_qualifiers)
            ids_used_in_references = cls.get_all_entity_ids_from_references(claim.references)
            ids.update(ids_used_in_references)
        return list(ids)

    @classmethod
    def get_all_entity_ids_from_qualifiers(cls, qualifiers: Qualifiers) -> list[str]:
        """
        Get all entity ids used in the given qualifiers
        :param qualifiers:
        :return:
        """
        ids = set()
        for qualifier in qualifiers:
            ids.add(qualifier.property_number)
            unit = cls.get_unit_id(qualifier)
            if unit is not None:
                ids.add(unit)
            if cls._is_item_and_known_value(qualifier):
                ids.add(qualifier.datavalue["value"]["id"])
        return list(ids)

    @classmethod
    def get_unit_id(cls, snak: Snak) -> str | None:
        """
        if given snak is of type quantity return the ID of the unit if the unit is defined by an entity
        :param snak:
        :return:
        """
        if snak.datatype == "quantity":
            unit = snak.datavalue.get("value", {}).get("unit")
            if unit is not None and isinstance(unit, str):
                unit_id = unit.split("/")[-1]
                if unit_id.startswith(("Q", "P", "L")):
                    return unit_id
        return None

    @classmethod
    def get_all_entity_ids_from_references(cls, references: References) -> list[str]:
        """
        Get all entity ids used in the given references
        :param references:
        :return:
        """
        ids = set()
        for reference_block in references:
            for reference in reference_block.snaks:
                ids.add(reference.property_number)
                unit = cls.get_unit_id(reference)
                if unit is not None:
                    ids.add(unit)
                if cls._is_item_and_known_value(reference):
                    ids.add(reference.datavalue["value"]["id"])
        return list(ids)

    @classmethod
    def _is_item_and_known_value(cls, snak: Snak) -> bool:
        """
        Checks if the snak is a wikibase-item and is a known value
        :param snak: snak to check
        :return: bool
        """
        return snak.datatype == "wikibase-item" and snak.snaktype is WikibaseSnakType.KNOWN_VALUE

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
        used_ids = self.get_all_entity_ids(item)
        self.prepare_mapper_cache_by_ids(used_ids)

    def prepare_mapper_cache_by_ids(self, item_ids: list[str]):
        """
        prepare the mapper cache with the mappings for the given item
        :param item:
        :return:
        """
        self.mapper.prepare_cache_for(item_ids)

    def add_translation_result_mappings(self, translation_result: EntityTranslationResult):
        """
        add translation mappings that are used by the item to the translation result
        :param item:
        :param translation_result:
        :return:
        """
        used_ids = self.get_all_entity_ids(translation_result.original_entity)
        mappings = {source_id: self.mapper.get_mapping_for(source_id) for source_id in used_ids}
        translation_result.add_entity_mappings(mappings)

    def translate_entities_by_id(
        self,
        item_ids: list[str],
        merge_existing_entities: bool = True,
        progress_callback: Callable[[str], None] | None = None,
    ) -> EntitySetTranslationResult:
        """
        Translate the items corresponding to the given item_ids
        :param progress_callback:
        :param item_ids: entity ids to translate
        :param merge_existing_entities If True existing entities are merged. Otherwise, existing entities are ignored
        :return:
        """
        if progress_callback is None:

            def progress_callback(x: str):
                logger.debug(x)
                return None

        progress_callback(f"Fetching {len(item_ids)} items records from {self.profile.source.name}")
        entities = self.get_items_from_source(item_ids)
        used_ids = set()
        for item in entities:
            used_ids.update(self.get_all_entity_ids(item))
        progress_callback("Preparing entity ID translation mappings")
        self.prepare_mapper_cache_by_ids(list(used_ids))
        if not merge_existing_entities:
            progress_callback("Excluding existing entities")
            entities = [entity for entity in entities if self.mapper.get_mapping_for(entity.id) is None]
        progress_callback("Translating entities")
        translated_entities = [self.translate_entity(entity) for entity in entities]
        translation_results = EntitySetTranslationResult.from_list(translated_entities)
        if merge_existing_entities:
            progress_callback("Merging existing entities")
            self.merge_existing_entities(translation_results)
        return translation_results

    def merge_existing_entities(self, translated_entities: EntitySetTranslationResult):
        """
        Merge existing entities with the translated entity
        :param translated_entities:
        :return:
        """
        entities_to_merge = [
            entity
            for entity in translated_entities
            if self.mapper.get_mapping_for(entity.original_entity.id) is not None
        ]

        source_existing_entity_ids = [entity.original_entity.id for entity in entities_to_merge]
        merge_mapping = {
            source: target
            for source, target in self.mapper.get_existing_mappings().items()
            if source in source_existing_entity_ids
        }
        target_entities = self.get_items_from_target(list(merge_mapping.values()))
        target_entities_by_id = {entity.id: entity for entity in target_entities}
        merger = EntityMerger()
        for translated_entity in entities_to_merge:
            target_entity_id = merge_mapping.get(translated_entity.original_entity.id)
            target_entity = target_entities_by_id.get(target_entity_id)
            if target_entity is None:
                logger.error(
                    f"Entity {translated_entity.original_entity.id} expected to be merged with {target_entity_id} but the entity was not found"  # noqa: E501
                )
                continue

            logger.debug(f"Merging {translated_entity.original_entity.id} into {target_entity_id}")
            try:
                merged_item = merger.merge(translated_entity.entity, target_entity)
            except Exception as e:
                translated_entity.errors.append(str(e))
                logger.exception(e)
            if merged_item is not None:
                translated_entity.entity = merged_item

    def translate_entity(
        self,
        entity: WbEntity,
        allowed_languages: list[str] | None = None,
        allowed_sitelinks: list[str] | None = None,
        with_back_reference: bool = True,
    ) -> EntityTranslationResult:
        """
        translates given entity from source to target wikibase instance
        ToDo: refactor to reduce complexity
        :param with_back_reference:
        :param allowed_sitelinks:
        :param allowed_languages:
        :param entity: wikibase item to translate from the source wikibase instance
        :return:
        """
        if allowed_languages is None:
            allowed_languages = self.profile.get_allowed_languages()
        if allowed_sitelinks is None:
            allowed_sitelinks = self.profile.get_allowed_sitelinks()
        self.prepare_mapper_cache(entity)
        match entity.ETYPE:
            case WikibaseEntityTypes.ITEM:
                new_entity = self.target_wbi.item.new()
            case WikibaseEntityTypes.PROPERTY:
                new_entity = self.target_wbi.property.new()
                new_entity.datatype = entity.datatype
            case WikibaseEntityTypes.MEDIAINFO:
                new_entity = self.target_wbi.mediainfo.new()
            case WikibaseEntityTypes.LEXEME:
                new_entity = self.target_wbi.lexeme.new()
                # ToDo: Translate lemmas
                # ToDo: Translate forms
                # ToDo: Translate senses
            case _:
                raise ValueError(f"Unsupported item type: {type(entity)}")
        result = EntityTranslationResult(
            entity=new_entity, original_entity=entity, missing_properties=[], missing_items=[]
        )
        self.add_translation_result_mappings(result)
        # add label
        self.translate_labels(entity, new_entity, allowed_languages)
        self.translate_descriptions(entity, new_entity, allowed_languages)
        self.translate_aliases(entity, new_entity, allowed_languages)
        self.translate_sitelinks(entity, new_entity, allowed_sitelinks)
        self.translate_claims(entity, new_entity, result)
        if with_back_reference:
            self.add_back_reference(new_entity, entity.id)
        return result

    def translate_labels(self, source: WbEntity, target: WbEntity, allowed_languages: list[str]) -> None:
        """
        translate the labels from the source entity to the target entity
        :return:
        """
        for label in source.labels:
            if label.language not in allowed_languages:
                continue
            target.labels.set(label.language, label.value)

    def translate_descriptions(self, source: WbEntity, target: WbEntity, allowed_languages: list[str]):
        """
        translate the descriptions from the source entity to the target entity
        :param source:
        :param target:
        :param allowed_languages:
        :return:
        """
        for description in source.descriptions:
            if description.language not in allowed_languages:
                continue
            desc_value = description.value
            if desc_value == source.labels.get(description.language):
                # Workaround for label=description validation error → https://github.com/wikimedia/mediawiki-extensions-Wikibase/blob/ae95f990c447a6470667fd16d5b1513003e74cee/repo/i18n/en.json#L190C50-L190C121
                # ToDo: Decide how to handle this
                continue
            target.descriptions.set(description.language, description.value)

    def translate_aliases(self, source: WbEntity, target: WbEntity, allowed_languages: list[str]):
        """
        translate the aliases from the source entity to the target entity
        :param source:
        :param target:
        :param allowed_languages:
        :return:
        """
        for language, aliases in source.aliases.aliases.items():
            if language not in allowed_languages:
                continue
            alias_values = [alias.value for alias in aliases]
            target.aliases.set(language, alias_values)

    def translate_sitelinks(self, source: WbEntity, target: WbEntity, allowed_sitelinks: list[str]):
        """
        translate the sitelinks from the source entity to the target entity
        :param source:
        :param target:
        :param allowed_sitelinks:
        :return:
        """

        if source.ETYPE in WikibaseEntityTypes.support_sitelinks():
            for sitelink in source.sitelinks.sitelinks.values():
                if sitelink.site not in allowed_sitelinks:
                    continue
                # ToDo: badges also require a mapping → currently not queried
                target.sitelinks.set(site=sitelink.site, title=sitelink.title)

    def translate_claims(self, source: WbEntity, target: WbEntity, result: EntityTranslationResult) -> None:
        """
        translate the claims from the source entity to the target entity
        :param source:
        :param target:
        :return:
        """
        for claim in source.claims:
            new_qualifiers = self.translate_qualifiers(claim, result)
            new_references = self.translate_references(claim, result)
            new_claim = self._translate_snak(
                claim.mainsnak, translation_result=result, qualifiers=new_qualifiers, references=new_references
            )
            if new_claim is not None:
                target.claims.add(new_claim, action_if_exists=ActionIfExists.MERGE_REFS_OR_APPEND)
            else:
                # ToDo: Handle missing property in target
                pass

    def translate_qualifiers(self, claim: Claim, result: EntityTranslationResult) -> Qualifiers:
        """
        translate the qualifiers from the claim to a new set of qualifiers for the target claim
        :param claim:
        :param result:
        :return:
        """
        new_qualifiers = Qualifiers()
        for qualifier in claim.qualifiers:
            new_qualifier = self._translate_snak(qualifier, translation_result=result)
            if new_qualifier is not None:
                # ToDo: Add action_if_exists once implemented
                new_qualifiers.add(new_qualifier)
            else:
                # ToDo: Handle missing property in target
                pass
        return new_qualifiers

    def translate_references(self, claim: Claim, result: EntityTranslationResult) -> References:
        """
        translate the references from the claim to a new set of references for the target claim
        :param claim:
        :param result:
        :return:
        """
        new_references = References()
        for reference in claim.references:
            new_reference = Reference()
            for snak in reference.snaks:
                new_snak = self._translate_snak(snak, translation_result=result)
                if new_snak is not None:
                    # ToDo: Add action_if_exists once implemented
                    new_reference.add(new_snak)
                else:
                    # ToDo: Handle missing property in target
                    pass
            if len(new_reference.snaks) > 0:
                # ToDo: Add action_if_exists once implemented
                new_references.add(new_reference)
        return new_references

    def _translate_snak(
        self, snak: Snak, translation_result: EntityTranslationResult, **kwargs
    ) -> datatypes.BaseDataType | None:
        """

        :param snak: snak to translate
        :param translation_result: translation result to store missing property and item information
        :param kwargs: additional arguments to pass to the translated snak for example references and qualifiers
        :return: Translated snak
        """
        if self.profile.mapping.ignore_unknown_values and snak.snaktype is WikibaseSnakType.UNKNOWN_VALUE:
            return None
        if self.profile.mapping.ignore_no_values and snak.snaktype is WikibaseSnakType.NO_VALUE:
            return None
        new_property_number = self.mapper.get_mapping_for(snak.property_number)
        if new_property_number is None:
            translation_result.add_missing_property(snak.property_number)
            return None
        new_snak = None
        if snak.snaktype is not WikibaseSnakType.KNOWN_VALUE:
            return BaseDataType(prop_nr=new_property_number, snaktype=snak.snaktype, **kwargs)
        if self.has_type_mismatch(snak.property_number, new_property_number):
            logger.debug(
                f"Property {snak.property_number} and target property {new_property_number} have a type mismatched"
            )
            if not self.profile.type_casts.enabled:
                logger.debug("Ignoring type mismatch as type casting is disabled in migration profile")
                translation_result.errors.append(
                    f"Ignoring Property {snak.property_number} due to type mismatch and disabled auto type casting"
                )
                return new_snak
            new_snak = self._translate_snak_with_type_mismatch(snak, translation_result=translation_result, **kwargs)
            return new_snak
        match snak.datatype:
            case WbiDataTypes.STRING:
                new_snak = datatypes.String(
                    prop_nr=new_property_number, value=snak.datavalue["value"], snaktype=snak.snaktype, **kwargs
                )
            case WbiDataTypes.EXTERNAL_ID:
                new_snak = datatypes.ExternalID(
                    prop_nr=new_property_number, value=snak.datavalue["value"], snaktype=snak.snaktype, **kwargs
                )
            case WbiDataTypes.WIKIBASE_ITEM:
                source_id = snak.datavalue.get("value", {}).get("id", None)
                mapped_id = self.mapper.get_mapping_for(source_id) if source_id else None
                if mapped_id:
                    new_snak = datatypes.Item(
                        prop_nr=new_property_number, value=mapped_id, snaktype=snak.snaktype, **kwargs
                    )
                else:
                    translation_result.add_missing_item(snak.datavalue["value"]["id"])
                    new_snak = None
            case WbiDataTypes.TIME:
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
            case WbiDataTypes.COMMONS_MEDIA:
                new_snak = datatypes.CommonsMedia(
                    prop_nr=new_property_number, value=snak.datavalue["value"], snaktype=snak.snaktype, **kwargs
                )
            case WbiDataTypes.QUANTITY:
                unit_id = self.get_unit_id(snak)
                mapped_unit_id = self.mapper.get_mapping_for(unit_id) if unit_id else None
                mapped_unit_url = f"{self.profile.target.item_prefix}{mapped_unit_id}" if mapped_unit_id else None
                new_snak = datatypes.Quantity(
                    prop_nr=new_property_number,
                    amount=snak.datavalue["value"]["amount"],
                    unit=mapped_unit_url,
                    upper_bound=snak.datavalue["value"].get("upper_bound", None),
                    lower_bound=snak.datavalue["value"].get("lower_bound", None),
                    snaktype=snak.snaktype,
                    **kwargs,
                )
            case WbiDataTypes.MONOLINGUALTEXT:
                new_snak = datatypes.MonolingualText(
                    prop_nr=new_property_number,
                    text=snak.datavalue["value"].get("text", None),
                    language=snak.datavalue["value"].get("language", None),
                    snaktype=snak.snaktype,
                    **kwargs,
                )
            case WbiDataTypes.GLOBE_COORDINATE:
                new_snak = datatypes.GlobeCoordinate(
                    prop_nr=new_property_number,
                    latitude=snak.datavalue["value"].get("latitude", None),
                    longitude=snak.datavalue["value"].get("longitude", None),
                    altitude=snak.datavalue["value"].get("altitude", None),
                    precision=snak.datavalue["value"].get("precision", None),
                    snaktype=snak.snaktype,
                    # globe does not need to be mapped
                    globe=snak.datavalue["value"].get("globe", None),
                    **kwargs,
                )
            case WbiDataTypes.ENTITY_SCHEMA:
                new_snak = datatypes.EntitySchema(
                    prop_nr=new_property_number, value=snak.datavalue["value"], snaktype=snak.snaktype, **kwargs
                )
            case WbiDataTypes.URL:
                new_snak = datatypes.URL(
                    prop_nr=new_property_number, value=snak.datavalue["value"], snaktype=snak.snaktype, **kwargs
                )
            case WbiDataTypes.PROPERTY:
                new_snak = datatypes.Property(
                    prop_nr=new_property_number, value=snak.datavalue["value"], snaktype=snak.snaktype, **kwargs
                )
            case WbiDataTypes.GEO_SHAPE:
                # ToDo: links to a file in mediawiki commons → how to translate map to same file or also copy file
                new_snak = datatypes.GeoShape(
                    prop_nr=new_property_number, value=snak.datavalue["value"], snaktype=snak.snaktype, **kwargs
                )
            case WbiDataTypes.TABUlAR_DATA:
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
            case EntityBackReferenceType.SITELINK:
                if entity.ETYPE in WikibaseEntityTypes.support_sitelinks():
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
        translations: EntitySetTranslationResult,
        summary: str | None,
        entity_done_callback: Callable[[Future], None] | None = None,
    ) -> list[ItemEntity | PropertyEntity]:
        """
        migrate given entities to the target wikibase instance
        :param translations:
        :param summary: summary of the changes
        :param entity_done_callback: callback function to call for each migrated entity e.g. for progress tracking
        :return: list of migrated entities containing the new ID in case of creation
        """
        logger.info(f"Migrating {len(translations.entities)} entities to target {self.profile.target.name}: {summary}")
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
        entity: EntityTranslationResult,
        mediawiki_api_url: str,
        summary: str | None = None,
        tags: list[str] | None = None,
        login: wbi_login.Login | wbi_login.Clientlogin | wbi_login.OAuth1 | wbi_login.OAuth2 | None = None,
    ) -> EntityTranslationResult:
        """
        migrates given entity to the given wikibase instance (url)
        :param entity: entity to migrate
        :param mediawiki_api_url: wikibase api url of the wikibase to store
        :param summary: summary of the changes
        :param tags: tags to add to the revision
        :return: entity with the ID
        """
        try:
            entity_json = entity.entity.get_json()
            if logger.level <= logging.DEBUG:
                path = Path(tempfile.gettempdir()).joinpath(
                    f"WikibaseMigrator/migrations/{datetime.now()}_{entity.original_entity.id}.json"
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "w") as f:
                    json.dump(entity_json, f)
            res = entity.entity.write(mediawiki_api_url=mediawiki_api_url, summary=summary, tags=tags, login=login)
            entity.created_entity = res
        except MWApiError as e:
            logger.info(f"Failed to migrate entity {entity.original_entity.id}")
            error = f"Error: {str(e)}, details: {e.messages}"
            entity.errors.append(error)
            logger.exception(e)
        except Exception as e:
            logger.info(f"Failed to migrate entity {entity.original_entity.id}")
            entity.errors.append(str(e))
            logger.exception(e)
        return entity

    def has_type_mismatch(self, source_pid, target_pid) -> bool:
        """
        Checks if source and target property have a type mismatch
        :param source_pid: pid of the source proeprty
        :param target_pid: pid of the target property
        :return: True if source and target property have a type mismatch. False otherwise
        """
        source_type = self.mapper.source_property_types.get(source_pid)
        target_type = self.mapper.target_property_types.get(target_pid)
        return source_type != target_type

    def _translate_snak_with_type_mismatch(self, snak: Snak, translation_result: EntityTranslationResult, **kwargs):
        """
        translate given snak if possible by casting the datatype pf the property
        :param snak:
        :param translation_result:
        :param kwargs:
        :return:
        """
        new_snak = None
        source_pid = snak.property_number
        target_pid = self.mapper.get_mapping_for(source_pid)
        if target_pid is None:
            logger.error(f"Mapping for {source_pid} is unknown")
            return new_snak
        source_type = self.mapper.source_property_types.get(source_pid)
        target_type = self.mapper.target_property_types.get(target_pid)
        error_msg = None
        match (source_type, target_type):
            case (WbiDataTypes.STRING, WbiDataTypes.QUANTITY):
                try:
                    value = snak.datavalue.get("value")
                    amount = int(value)
                    error_msg = f"Resolved type missmatch by casting '{value}' to {amount}"
                    new_snak = datatypes.Quantity(
                        prop_nr=target_pid,
                        amount=amount,
                        snaktype=snak.snaktype,
                        **kwargs,
                    )
                except ValueError:
                    error_msg = f"Unable to resolve type mismatch. Can not convert {snak.datavalue.get('value')} to type Quantity"  # noqa: E501
            case (WbiDataTypes.STRING, WbiDataTypes.WIKIBASE_ITEM):
                error_msg = f"Unsolvable type mismatch {source_type}→{target_type}. Excluding this snak"
            case (WbiDataTypes.STRING, WbiDataTypes.MONOLINGUALTEXT):
                value = snak.datavalue.get("value")
                new_snak = datatypes.MonolingualText(
                    prop_nr=target_pid,
                    text=value,
                    language=self.profile.type_casts.fallback_language,
                    snaktype=snak.snaktype,
                    **kwargs,
                )
                error_msg = f"Resolved type mismatch by casting '{value}' to '{value}'@{self.profile.type_casts.fallback_language}"  # noqa: E501
            case (WbiDataTypes.STRING, WbiDataTypes.EXTERNAL_ID):
                new_snak = datatypes.ExternalID(
                    prop_nr=target_pid, value=snak.datavalue.get("value"), snaktype=snak.snaktype, **kwargs
                )
            case (WbiDataTypes.MONOLINGUALTEXT, WbiDataTypes.STRING):
                value = snak.datavalue["value"].get("text", None)
                language = snak.datavalue["value"].get("language", None)
                new_snak = datatypes.String(prop_nr=target_pid, value=value, snaktype=snak.snaktype, **kwargs)
                error_msg = f"Resolved type mismatch by casting '{value}'@{language} to '{value}'"
            case (WbiDataTypes.QUANTITY, WbiDataTypes.WIKIBASE_ITEM):
                error_msg = (
                    f"Unable to resolve type mismatch. Can not convert {snak.datavalue.get('value')} to type Item"
                )
            case (WbiDataTypes.MONOLINGUALTEXT, WbiDataTypes.WIKIBASE_ITEM):
                error_msg = (
                    f"Unable to resolve type mismatch. Can not convert {snak.datavalue.get('value')} to type Item"
                )
            case _:
                error_msg = f"Unable to resolve type mismatch. Can not convert {snak.datavalue.get('value')}"
        if error_msg:
            logger.debug(error_msg)
            translation_result.errors.append(error_msg)
        return new_snak
