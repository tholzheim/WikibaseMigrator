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
            for property_number, snaks in claim.qualifiers.qualifiers.items():
                qualifier_record = {
                    "s_id": property_number,
                    "t_id": mappings.get(property_number, None),
                    "snaks": [self._convert_snak(snak, mappings) for snak in snaks],
                }
                qulifier_recors.append(qualifier_record)
            reference_block: Reference
            for reference_block in claim.references:
                block_records = []
                for property_number, snaks in reference_block.snaks.snaks.items():
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
                for language, aliases in translation_result.entity.aliases.aliases.items()
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
