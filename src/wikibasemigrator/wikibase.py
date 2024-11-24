import hashlib
import json
import logging
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from enum import Enum
from pathlib import Path
from string import Template

import requests
from pydantic import HttpUrl
from SPARQLWrapper import JSON, POST, SPARQLWrapper

logger = logging.getLogger(__name__)


def get_default_user_agent() -> str:
    return "WikibaseMigrator/1.0 (https://www.wikidata.org/wiki/User:tholzheim)"


class Query:
    """
    Holds basic functions to query a wikibase
    """

    @classmethod
    def get_item_label(
        cls,
        endpoint_url: HttpUrl,
        item_ids: list[str],
        language: str | None = None,
        item_prefix: HttpUrl = "http://www.wikidata.org/entity/",
    ) -> list[dict]:
        """
        Get the labels for the given items
        :param endpoint_url:
        :param item_ids:
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
        values = [f'"{item}"' for item in item_ids]
        lod = cls.execute_values_query_in_chunks(
            query_template=query_template,
            param_name="entity_ids",
            values=values,
            endpoint_url=endpoint_url,
        )
        return lod

    @classmethod
    def chunks(cls, lst, n):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), n):
            yield lst[i : i + n]

    @classmethod
    def execute_values_query_in_chunks(
        cls, query_template: Template, param_name: str, values: list[str], endpoint_url=HttpUrl, chunk_size: int = 1000
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
        Execute given qquery against given endpoint
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
    def support_sidelinks(cls) -> list["WikibaseEntityTypes"]:
        """
        Returns list of Wikibase types which support sidelinks
        """
        return [WikibaseEntityTypes.ITEM]
