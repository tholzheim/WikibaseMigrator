import hashlib
import json
import logging
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from enum import Enum
from functools import partial
from pathlib import Path
from string import Template

import requests
from pydantic import HttpUrl
from SPARQLWrapper import JSON, POST, SPARQLWrapper
from wikibaseintegrator import __version__

logger = logging.getLogger(__name__)


WIKIBASE_PREFIX = "http://wikiba.se/ontology#"


def get_default_user_agent() -> str:
    """
    Get default user agent
    """
    return f"WikibaseMigrator/{__version__}"


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


class Query:
    """
    Holds basic functions to query a wikibase
    """

    @classmethod
    def get_entity_label(
        cls,
        endpoint_url: HttpUrl,
        entity_ids: list[str],
        item_prefix: HttpUrl,
        language: str | None = None,
    ) -> list[dict]:
        """
        Get the labels for the given entities
        :param endpoint_url:
        :param entity_ids:
        :param language: if None english will be used
        :param item_prefix:
        :return:
        """
        query_raw = Template("""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?qid ?label
        WHERE{
          VALUES ?qid { 
            $entity_ids
          }
          BIND(IRI(CONCAT("$item_prefix", STR( ?qid))) as ?wd_qid)
          ?wd_qid rdfs:label ?label. FILTER(lang(?label)="$language")
        }
        """)
        if language is None:
            language = "en"
        query_template = Template(query_raw.safe_substitute(language=language, item_prefix=item_prefix))
        values = [f'"{entity_id}"' for entity_id in entity_ids]
        lod = cls.execute_values_query_in_chunks(
            query_template=query_template,
            param_name="entity_ids",
            values=values,
            endpoint_url=endpoint_url,
        )
        return lod

    @classmethod
    def get_property_datatype(
        cls, endpoint_url: HttpUrl, property_ids: list[str], item_prefix: HttpUrl
    ) -> dict[str, WikidataDataTypes]:
        """
        Get the datatype for the given list of property ids
        :param endpoint_url: endpoint to query
        :param property_ids: property ids for which the datatype should be returned
        :param item_prefix: namespace of the wikibase entities
        :return: mapping from the property ids to the datatype
        """
        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX wikibase: <http://wikiba.se/ontology#>
        SELECT * WHERE {
          VALUES ?p {
            $property_ids
          }
          ?p rdf:type wikibase:Property;
            wikibase:propertyType ?type.
        }
        """
        if not property_ids:
            return {}
        property_uris = map(partial(cls.add_namespace, namespace=item_prefix.unicode_string()), property_ids)
        values = list(map(cls.get_sparql_uri, property_uris))
        lod = cls.execute_values_query_in_chunks(
            query_template=Template(query),
            param_name="property_ids",
            values=values,
            endpoint_url=endpoint_url,
        )
        prop_type_map = dict()
        for d in lod:
            pid = cls.remove_namespace(d.get("p"), item_prefix.unicode_string())
            datatype = cls.remove_namespace(d.get("type"), WIKIBASE_PREFIX)
            prop_type_map[pid] = WikidataDataTypes(datatype)
        return prop_type_map

    @classmethod
    def chunks(cls, lst, n):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), n):
            yield lst[i : i + n]

    @classmethod
    def execute_values_query_in_chunks(
        cls, query_template: Template, param_name: str, values: list[str], endpoint_url: HttpUrl, chunk_size: int = 1000
    ):
        """
        Execute given query in chunks to speedup execution
        :param chunk_size:
        :param endpoint_url:
        :param query_template:
        :param param_name:
        :param values:
        :return:
        """
        lod = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for item_id_chunk in cls.chunks(values, chunk_size):
                source_items = "\n".join(item_id_chunk)
                query = query_template.substitute(**{param_name: source_items})
                logger.debug(f"Querying chunk of size {len(item_id_chunk)} labels from {endpoint_url}")
                future = executor.submit(
                    cls.execute_query,
                    query=query,
                    endpoint_url=endpoint_url,
                )
                futures.append(future)
            for future in as_completed(futures):
                lod_chunk = future.result()
                lod.extend(lod_chunk)
        return lod

    @classmethod
    def execute_query(cls, query: str, endpoint_url: HttpUrl) -> list[dict]:
        """
        Execute given query against given endpoint
        :param query:
        :param endpoint_url:
        :return:
        """
        query_first_line = query.split("\n")[0][:30] if query.strip().startswith("#") else ""
        query_hash = hashlib.sha512(query.encode("utf-8")).hexdigest()
        logger.debug(f"Executing SPARQL query {query_first_line} ({query_hash}) against {endpoint_url}")
        start = datetime.now()
        sparql = SPARQLWrapper(endpoint_url.unicode_string(), agent=get_default_user_agent(), returnFormat=JSON)
        sparql.setQuery(query)
        sparql.setMethod(POST)
        resp = sparql.query().convert()
        lod_raw = resp.get("results", {}).get("bindings")
        logger.debug(
            f"Query ({query_hash}) execution finished! execution time : {(datetime.now() - start).total_seconds()}s, No. results: {len(lod_raw)}"  # noqa: E501
        )  # noqa: E501
        if logging.root.level <= logging.DEBUG:
            file_name = f"{start}_{query_hash}"
            cls.save_query(name=file_name, query=query)
            cls.save_results(name=file_name, lod=lod_raw)
        lod = []
        for d_raw in lod_raw:
            d = {key: record.get("value", None) for key, record in d_raw.items()}
            if d:
                lod.append(d)
        return lod

    @classmethod
    def check_availability_of_sparql_endpoint(cls, endpoint_url: HttpUrl):
        """
        Checks if the given endpoint is available.
        Uses the availability check proposed by Vandenbussche et al. see https://ceur-ws.org/Vol-1035/iswc2013_demo_21.pdf
        :param endpoint:
        :return: True if the endpoint is available. Otherwise, False
        """
        query = "ASK WHERE{ ?s ?p ?o . }"
        sparql = SPARQLWrapper(endpoint_url.unicode_string(), agent=get_default_user_agent(), returnFormat=JSON)
        sparql.setQuery(query)
        sparql.setMethod(POST)
        try:
            resp = sparql.query().convert()
            return resp.get("boolean", False)
        except Exception as e:
            logger.error(e)
        return False

    @classmethod
    def save_results(cls, name: str, lod: list[dict], path: Path | None = None) -> None:
        """
        store the results as json file
        :param lod:
        :param path:
        :return:
        """
        if path is None:
            path = cls._get_tmp_dir()
        path = path.joinpath(f"{name}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Saving results to {path}")
        with open(path, "w") as f:
            json.dump(lod, f, indent=2)

    @classmethod
    def save_query(cls, name: str, query: str, path: Path | None = None) -> None:
        """
        store the results as json file
        :param query:
        :param name:
        :param path:
        :return:
        """
        if path is None:
            path = cls._get_tmp_dir()
        path = path.joinpath(f"{name}.rq")
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Saving query to {path}")
        with open(path, "w") as f:
            f.write(query)

    @classmethod
    def _get_tmp_dir(cls) -> Path:
        d = tempfile.gettempdir()
        path = Path(d).joinpath("WikibaseMigrator")
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def add_namespace(cls, value: str, namespace: str) -> str:
        """
        Adds the namespace prefix to each value if needed
        :param value: value to which the prefix is added
        :param namespace: namespace to add
        :return: list of URLs
        """
        return value if value.startswith(namespace) else namespace + value

    @classmethod
    def remove_namespace(cls, value: str, namespace: str) -> str:
        """
        Removes the namespace prefix from the value if needed
        :param value:
        :param namespace:
        :return:
        """
        return value.removeprefix(namespace)

    @classmethod
    def get_sparql_uri(cls, value: str) -> str:
        return f"<{value}>"


class MediaWikiEndpoint:
    """
    Holds basic function to get data from a mediawiki api
    """

    @classmethod
    def get_supported_languages(cls, mediawiki_api_url: HttpUrl) -> dict[str, str]:
        """
        Get the languages supported by given MediaWiki
        :param mediawiki_api_url: api endpoint of the wiki
        :return: Mapping from language cot to the label
        """
        params = {
            "action": "query",
            "meta": "siteinfo",
            "siprop": "general|languages",
            "format": "json",
        }
        res = {}
        try:
            logger.debug(f"Querying supported languages from {mediawiki_api_url}")
            response = requests.get(mediawiki_api_url, params=params)
            data = response.json()
        except Exception as e:
            logger.error(e)
            data = {}
        for lang_record in data.get("query", {}).get("languages", []):
            code = lang_record.get("code")
            label = lang_record.get("*")
            if code:
                res[code] = label
        return res

    @classmethod
    def check_availability(cls, mediawiki_api_url: HttpUrl):
        """
        Check if the mediawiki api is available
        :param mediawiki_api_url:
        :return: True if the api is available, otherwise False
        """
        query = "action=query&titles=Main_Page&prop=revisions&rvprop=content&format=json"
        try:
            response = requests.get(f"{mediawiki_api_url.unicode_string()}?{query}")
            response.raise_for_status()
        except Exception:
            return False
        return True


class WikibaseEntityTypes(str, Enum):
    """
    wikibaseintegrator entity types
    """

    BASE_ENTITY = "base-entity"
    ITEM = "item"
    PROPERTY = "property"
    LEXEME = "lexeme"
    MEDIAINFO = "mediainfo"

    @classmethod
    def support_sitelinks(cls) -> list["WikibaseEntityTypes"]:
        """
        Returns list of Wikibase types which support sitelinks
        """
        return [WikibaseEntityTypes.ITEM]
