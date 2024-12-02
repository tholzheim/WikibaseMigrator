import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from string import Template

from wikibasemigrator import config, wikibase
from wikibasemigrator.model.profile import WikibaseConfig, WikibaseMigrationProfile
from wikibasemigrator.wikibase import WbiDataTypes

logger = logging.getLogger(__name__)


class WikibaseItemMapper:
    """
    Maps items from one wikibase instance to another
    """

    def __init__(self, profile: WikibaseMigrationProfile):
        self.migration_profile = profile
        self._raw_mappings: set[tuple[str, str]] = set()
        self.mappings: dict[str, str | None] = dict()
        self.source_property_types: dict[str, WbiDataTypes] = dict()
        self.target_property_types: dict[str, WbiDataTypes] = dict()

    @property
    def wikibase_config(self) -> WikibaseConfig:
        """
        Get wikibase config of the wikibase instance that holds the mapping information
        """
        return self.migration_profile.get_wikibase_config_of_mapping_location()

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
            ("property", property_ids, self.migration_profile.mapping.property_mapping_query),
            ("item", item_ids, self.migration_profile.mapping.item_mapping_query),
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
                self._update_raw_cache(lod)
        self.update_property_type_map()
        self.update_cache()

    def update_property_type_map(self):
        """
        update the property type mappings for source and target properties
        """
        logger.debug("Updating property type mappings")
        with ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(self._update_source_property_types)
            executor.submit(self._update_target_property_types)

    def _update_source_property_types(self):
        """
        update the property type mappings for source properties
        :return:
        """
        logger.debug("Updating source property type mappings")
        used_props = {pid for pid, _ in self._raw_mappings if pid.startswith("P")}
        cached_types = set(self.source_property_types.keys())
        needed_props = used_props - cached_types
        prop_type_mappings = wikibase.Query.get_property_datatype(
            endpoint_url=self.migration_profile.source.sparql_url,
            property_ids=list(needed_props),
            item_prefix=self.migration_profile.source.item_prefix,
        )
        wbi_prop_type_mappings = {key: value.get_wbi_type() for key, value in prop_type_mappings.items()}
        self.source_property_types.update(wbi_prop_type_mappings)

    def _update_target_property_types(self):
        """
        update the property type mappings for target properties
        :return:
        """
        logger.debug("Updating target property type mappings")
        used_props = {pid for _, pid in self._raw_mappings if pid is not None and pid.startswith("P")}
        cached_types = set(self.target_property_types.keys())
        needed_props = used_props - cached_types
        prop_type_mappings = wikibase.Query.get_property_datatype(
            endpoint_url=self.migration_profile.target.sparql_url,
            property_ids=list(needed_props),
            item_prefix=self.migration_profile.target.item_prefix,
        )
        wbi_prop_type_mappings = {key: value.get_wbi_type() for key, value in prop_type_mappings.items()}
        self.target_property_types.update(wbi_prop_type_mappings)

    def query_mapping_for(self, item: str):
        """
        Query the mapping of the given item and update the cache
        """
        self.query_mappings_for(ids=[item])

    def _update_raw_cache(self, lod: list[dict]) -> None:
        """
        Update the cache
        :param lod: list of mappings to cache
        :return:
        """
        for record in lod:
            source = record.get(config.MAPPING_QUERY_SOURCE_VARIABLE, None)
            target = record.get(config.MAPPING_QUERY_TARGET_VARIABLE, None)
            if isinstance(source, str) and isinstance(target, str):
                self._raw_mappings.add((source, target))

    def update_cache(self):
        """
        update the mapping cache and ensure that
        if multiple mappings for the same property exist that the one with the correct type is chosen
        """
        d = {}
        for source, target in self._raw_mappings:
            d.setdefault(source, []).append(target)
        for source, target_ids in d.items():
            if len(target_ids) == 1:
                self.mappings[source] = target_ids[0]
            elif source.startswith("P"):
                source_type = self.source_property_types.get(source, None)
                matching_type = False
                for target_id in target_ids:
                    target_type = self.target_property_types.get(target_id, None)
                    if source_type == target_type:
                        logger.debug(
                            f"Source property {source} has multiple mappings → Choosing {target_id} from target as it has the same property datatype"  # noqa: E501
                        )
                        self.mappings[source] = target_id
                        matching_type = True
                        break
                if not matching_type:
                    logger.debug(
                        f"Property with multiple mappings for source {source} and targets {target_ids} → To Resolve this the first property of the list is chosen"  # noqa: E501
                    )
                    self.mappings[source] = target_ids[0]
            else:
                logger.debug(
                    f"Entity {source} has multiple mappings in target {target_ids} → To Resolve this the first property of the list is chosen"  # noqa: E501
                )
                self.mappings[source] = target_ids[0]

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
        """
        Check if the given entity id is cached
        :param item: entity id to check
        :return: True if it is cached, False otherwise
        """
        return item in self.mappings

    def get_existing_mappings(self) -> dict[str, str]:
        return {key: value for key, value in self.mappings.items() if value is not None}

    def get_missing_mappings(self) -> list[str]:
        return [key for key, value in self.mappings.items() if value is None]

    def get_missing_item_mapings(self) -> list[str]:
        return [value for value in self.get_missing_mappings() if value.startswith("Q")]

    def get_missing_property_mapings(self) -> list[str]:
        return [value for value in self.get_missing_mappings() if value.startswith("P")]
