import logging
from datetime import datetime
from string import Template

from wikibasemigrator import config, wikibase
from wikibasemigrator.model.profile import WikibaseConfig, WikibaseMigrationProfile

logger = logging.getLogger(__name__)


class WikibaseItemMapper:
    """
    Maps items from one wikibase instance to another
    """

    def __init__(self, config: WikibaseMigrationProfile):
        self.migration_config = config
        self.wikibase_config = self._get_wikibase_config_containing_mapping()
        self.mappings: dict[str, str | None] = dict()

    def _get_wikibase_config_containing_mapping(self) -> WikibaseConfig:
        config = self.migration_config.get_wikibase_config_of_mapping_location()
        return config

    def query_mappings_for(self, ids: list[str]):
        """
        query for the mappings of the given ids.
        The list of ids can be a mixture of Qids and Pids as they will be seperated and queried separately.
        :param ids: list of ids
        :return:
        """
        property_ids = [item for item in ids if item.startswith("P")]
        item_ids = [item for item in ids if item.startswith("Q")]
        self._init_cache_for(ids)
        ids_queries = [
            ("property", property_ids, self.migration_config.mapping.property_mapping_query),
            ("item", item_ids, self.migration_config.mapping.item_mapping_query),
        ]
        for id_type, id_values, query_raw in ids_queries:
            if id_values:
                query_template = Template(query_raw)
                source_items = [f'"{item}"' for item in id_values]
                logger.debug(f"Querying {id_type} mappings for {len(id_values)} IDs")
                lod = wikibase.Query.execute_values_query_in_chunks(
                    query_template=query_template,
                    param_name=config.MAPPING_QUERY_VALUES_INPUT_VARIABLE,
                    values=source_items,
                    endpoint_url=self.wikibase_config.sparql_url,
                )
                self._update_cache(lod)

    def query_mapping_for(self, item: str):
        """
        Query the mapping of the given item and update the cache
        """
        self.query_mappings_for(ids=[item])

    def _update_cache(self, lod: list[dict]) -> None:
        """
        Update the cache
        :param lod: list of mappings to cache
        :return:
        """
        for record in lod:
            source = record.get(config.MAPPING_QUERY_SOURCE_VARIABLE, None)
            target = record.get(config.MAPPING_QUERY_TARGET_VARIABLE, None)
            if isinstance(source, str) and isinstance(target, str):
                self.mappings[source] = target

    def _init_cache_for(self, ids: list[str]) -> None:
        """
        Set cache to None for the given ids if not already cached
        :param ids:
        :return:
        """
        for id_value in ids:
            if id_value not in self.mappings:
                self.mappings[id_value] = None

    def prepare_cache_for(self, items: list[str]):
        """
        prepare the cache for a given list of items
        :param items: items  to cache the mapping for
        :return:
        """
        items_to_query = [item for item in items if item not in self.mappings]
        if items_to_query:
            logger.debug(
                f"Prepare cache for {len(items_to_query)} items. ({len(items) - len(items_to_query)} were already cached)"  # noqa: E501
            )
            start_time = datetime.now()
            self.query_mappings_for(items_to_query)
            logger.debug(f"Cache preparation took {datetime.now() - start_time}")

    def get_mapping_for(self, item: str) -> str | None:
        """
        Get the mapping for the given item in the target wikibase instance
        :param item: item id either a Qid or Pid
        :return: id of the corresponding item in the target wikibase instance
        """
        if not self.is_cached(item):
            self.query_mapping_for(item)
        return self.mappings.get(item, None)

    def is_cached(self, item: str) -> bool:
        return item in self.mappings

    def get_existing_mappings(self) -> dict[str, str]:
        return {key: value for key, value in self.mappings.items() if value is not None}

    def get_missing_mappings(self) -> list[str]:
        return [key for key, value in self.mappings.items() if value is None]

    def get_missing_item_mapings(self) -> list[str]:
        return [value for value in self.get_missing_mappings() if value.startswith("Q")]

    def get_missing_property_mapings(self) -> list[str]:
        return [value for value in self.get_missing_mappings() if value.startswith("P")]
