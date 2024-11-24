from nicegui import ui
from nicegui.element import Element
from pydantic import HttpUrl
from wikibaseintegrator.models import Reference, Snak
from wikibaseintegrator.wbi_enums import WikibaseSnakType

from wikibasemigrator.model.translations import EntityTranslationResult


class TranslatedWikibaseItemWidget(Element, component="wikibase_item.js"):
    def __init__(
        self,
        source_url: str | HttpUrl,
        target_url: str | HttpUrl,
        source_labels: dict[str, str] | None,
        target_labels: dict[str, str] | None,
        translation_result: EntityTranslationResult | None = None,
        entity: dict | None = None,
    ) -> None:
        super().__init__()
        if translation_result is not None:
            entity = self._convert_to_translation_record(translation_result)
        self._props["s_wikibase"] = str(source_url)
        self._props["t_wikibase"] = str(target_url)
        self._props["source_labels"] = source_labels
        self._props["target_labels"] = target_labels
        self._props["entity"] = entity

    def _convert_to_translation_record(self, translation_result: EntityTranslationResult) -> dict:
        """
        Conver the translation result to a translation record which can be rendered by the vue template
        :param translation_result:
        :return:
        """
        item = translation_result.original_entity
        mappings = translation_result.entity_mapping
        claims: dict[str, list] = {}
        for claim in item.claims:
            mainsnak = self._convert_snak(claim.mainsnak, mappings)
            qulifier_recors = []
            reference_records = []
            for property_number, snaks in claim.qualifiers.qualifiers.entities():
                qualifier_record = {
                    "s_id": property_number,
                    "t_id": mappings.get(property_number, None),
                    "snaks": [self._convert_snak(snak, mappings) for snak in snaks],
                }
                qulifier_recors.append(qualifier_record)
            reference_block: Reference
            for reference_block in claim.references:
                block_records = []
                for property_number, snaks in reference_block.snaks.snaks.entities():
                    reference_record = {
                        "s_id": property_number,
                        "t_id": mappings.get(property_number, None),
                        "snaks": [self._convert_snak(snak, mappings) for snak in snaks],
                    }
                    block_records.append(reference_record)
                reference_records.append({"reference": block_records})
            claim_record = {"mainsnak": mainsnak, "qualifiers": qulifier_recors, "references": reference_records}
            if claim.mainsnak.property_number not in claims:
                claims[claim.mainsnak.property_number] = []
            claims[claim.mainsnak.property_number].append(claim_record)
        claim_records: list[dict[str, str | list | None]] = [
            {"s_id": s_id, "t_id": mappings.get(s_id, None), "snaks": snaks} for s_id, snaks in claims.items()
        ]
        # Sort claims: properties with mapping first than sort by property number
        claim_records.sort(
            key=lambda x: int(f"1{x.get('s_id', '').removeprefix('P')}")  # type: ignore
            if x.get("t_id") is not None
            else int(f"9{x.get('s_id', '').removeprefix('P')}")  # type: ignore
        )
        entity_record = {
            "s_id": item.id,
            "t_id": mappings.get(item.id, None),
            "labels": {label.language: label.value for label in translation_result.entity.labels},
            "descriptions": {desc.language: desc.value for desc in translation_result.entity.descriptions},
            "aliases": {
                language: [alias.value for alias in aliases]
                for language, aliases in translation_result.entity.aliases.aliases.entities()
            },
            "claims": claim_records,
        }
        return entity_record

    def _convert_snak(self, snak: Snak, mappings: dict) -> dict:
        record = {"type": snak.datatype, "snaktype": snak.snaktype.value}
        # ToDo: refactor all to .get()
        if snak.snaktype is WikibaseSnakType.UNKNOWN_VALUE:
            record["value"] = WikibaseSnakType.UNKNOWN_VALUE.value
        elif snak.snaktype is WikibaseSnakType.NO_VALUE:
            record["value"] = WikibaseSnakType.NO_VALUE.value
        else:
            match snak.datatype:
                case (
                    "string"
                    | "external-id"
                    | "commonsMedia"
                    | "entity-schema"
                    | "url"
                    | "property"
                    | "geo-shape"
                    | "tabular-data"
                ):
                    record["value"] = snak.datavalue["value"]
                case "wikibase-item":
                    record["value"] = snak.datavalue["value"]["id"]
                    record["target_value"] = mappings.get(snak.datavalue["value"]["id"], None)
                case "time":
                    record["value"] = snak.datavalue["value"]["time"]
                case "quantity":
                    record["value"] = f"""{snak.datavalue}"""
                case "monolingualtext":
                    record["value"] = snak.datavalue["value"].get("text", None)
                    record["language"] = snak.datavalue["value"].get("language", None)
                case "globecoordinate":
                    record["value"] = str(snak.datavalue["value"])
        return record


if __name__ in {"__main__", "__mp_main__"}:
    data = {
        "s_id": "Q80",
        "t_id": None,
        "labels": {
            "en": "Tim Berners-Lee",
            "de": "Tim Berners-Lee",
            "fr": "Tim Berners-Lee",
            "es": "Tim Berners-Lee",
            "en-us": "Tim Berners-Lee",
        },
        "descriptions": {"en": "Tim Berners-Lee"},
        "aliases": {"en": ["Tim Berners-Lee", "TBL"]},
        "claims": [
            {
                "s_id": "P31",
                "t_id": "P2",
                "snaks": [
                    {
                        "mainsnak": {"type": "wikibase-item", "value": "Q5", "target_value": "Q7"},
                        "qualifiers": [],
                        "references": [],
                    },
                    {
                        "mainsnak": {"type": "monolingualtext", "value": "Test", "language": "en"},
                        "qualifiers": [
                            {
                                "s_id": "P31",
                                "t_id": "P2",
                                "snaks": [
                                    {"type": "wikibase-item", "value": "Q5", "target_value": "Q7"},
                                    {"type": "monolingualtext", "value": "Test", "language": "en"},
                                ],
                            },
                            {
                                "s_id": "P580",
                                "t_id": "P42",
                                "snaks": [
                                    {"type": "wikibase-item", "value": "Q5", "target_value": "Q7"},
                                    {"type": "monolingualtext", "value": "Test", "language": "en"},
                                ],
                            },
                        ],
                        "references": [
                            {
                                "reference": [
                                    {
                                        "s_id": "P580",
                                        "t_id": "P42",
                                        "snaks": [
                                            {"type": "wikibase-item", "value": "Q5", "target_value": "Q7"},
                                            {"type": "monolingualtext", "value": "Test", "language": "en"},
                                        ],
                                    },
                                    {
                                        "s_id": "P420",
                                        "t_id": "P80",
                                        "snaks": [
                                            {"type": "wikibase-item", "value": "Q5", "target_value": "Q7"},
                                            {"type": "monolingualtext", "value": "Test", "language": "en"},
                                        ],
                                    },
                                ]
                            },
                            {
                                "reference": [
                                    {
                                        "s_id": "P580",
                                        "t_id": "P42",
                                        "snaks": [
                                            {"type": "wikibase-item", "value": "Q5", "target_value": "Q7"},
                                            {"type": "monolingualtext", "value": "Test", "language": "en"},
                                        ],
                                    },
                                    {
                                        "s_id": "P420",
                                        "t_id": "P80",
                                        "snaks": [
                                            {"type": "wikibase-item", "value": "Q5", "target_value": "Q7"},
                                            {"type": "monolingualtext", "value": "Test", "language": "en"},
                                        ],
                                    },
                                ]
                            },
                        ],
                    },
                ],
            },
            {
                "s_id": "P580",
                "t_id": "P49",
                "snaks": [
                    {
                        "mainsnak": {"type": "time", "value": "2024-10-10T15:05:04"},
                    }
                ],
            },
        ],
    }

    TranslatedWikibaseItemWidget(
        source_url="http://www.wikidata.org/entity/",
        target_url="https://database.factgrid.de/entity/",
        source_labels={
            "P31": "instance of",
            "Q5": "human",
        },
        target_labels={
            "P2": "instance of",
            "Q7": "human",
        },
        entity=data,
    )
    ui.run(port=9080)
