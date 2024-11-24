import logging
from collections.abc import Generator

from pydantic import BaseModel, ConfigDict, Field

from wikibasemigrator import WbEntity

logger = logging.getLogger(__name__)


class EntityTranslationResult(BaseModel):
    """
    wikibase migration translation result of an entity
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    entity: WbEntity
    original_entity: WbEntity
    missing_properties: list[str] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)
    entity_mapping: dict[str, str | None] = Field(default_factory=dict)
    created_entity: WbEntity | None = None
    errors: list[str] = Field(default_factory=list)

    def add_missing_property(self, property_id: str):
        """
        add missing property
        :param property_id:
        :return:
        """

        self.missing_properties.append(property_id)

    def add_missing_item(self, entity_id: str):
        """
        add missing item
        :param entity_id:
        :return:
        """
        self.missing_items.append(entity_id)

    def add_entity_mapping(self, source_id: str, target_id: str | None):
        """
        add given mapping to mappings
        :param source_id:
        :param target_id:
        :return:
        """
        self.entity_mapping[source_id] = target_id

    def add_entity_mappings(self, mappings: dict[str, str | None]):
        """
        Update mappings with given mappings
        :param mappings:
        :return:
        """
        self.entity_mapping.update(mappings)


class EntitySetTranslationResult(BaseModel):
    entities: dict[str, EntityTranslationResult] = Field(default_factory=dict)

    @classmethod
    def from_list(cls, entities: list[EntityTranslationResult]) -> "EntitySetTranslationResult":
        res = EntitySetTranslationResult()
        for entity in entities:
            res.entities[entity.original_entity.id] = entity
        return res

    def get_created_entities(self) -> list[WbEntity]:
        return [entity.created_entity for entity in self.entities.values()]

    def get_missing_properties(self) -> list[str]:
        """
        Get IDs of missing properties
        :return: list of missing properties
        """
        missing = set()
        for entity in self.entities.values():
            missing.update(entity.missing_properties)
        return list(missing)

    def get_missing_items(self) -> list[str]:
        """
        Get IDs of missing item
        """
        missing = set()
        for entity in self.entities.values():
            missing.update(entity.missing_items)
        return list(missing)

    def get_mapping(self) -> dict[str, str | None]:
        """
        Get all mappings that are used
        :return:
        """
        mapping = dict()
        for entity in self.entities.values():
            mapping.update(entity.entity_mapping)
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
        return [item.original_entity.id for item in self.entities.values()]

    def get_target_entities(self) -> list[WbEntity]:
        """
        Get all target items
        """
        return [translation_result.entity for translation_result in self.entities.values()]

    def get_source_entities(self) -> list[WbEntity]:
        """
        Get all source items
        """
        return [translation_result.original_entity for translation_result in self.entities.values()]

    def get_source_entity_ids(self) -> list[str]:
        """
        Get IDs of all source entities that are used
        """
        return [entity_id for entity_id in self.get_mapping()]

    def get_target_entity_ids(self) -> list[str]:
        """
        Get IDs of all target entities that are used
        """
        return [entity_id for entity_id in self.get_mapping().values() if entity_id is not None]

    def get_source_root_entity_ids(self):
        """
        Get IDs of all source items to migrate.
        Only the "subject" ids no ids used in any statement, qualifier or reference
        """
        return [item.id for item in self.get_source_entities() if item.id]

    def get_translation_result_by_source_id(self, source_id: str) -> EntityTranslationResult | None:
        """
        Get TranslationResult by source id
        :param source_id:
        :return:
        """
        for item in self.entities.values():
            if item.original_entity.id == source_id:
                return item
        return None

    def __iter__(self) -> Generator[EntityTranslationResult, None, None]:
        yield from self.entities.values()
