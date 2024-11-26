import logging
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Union

from pydantic import HttpUrl
from wikibaseintegrator.entities import ItemEntity, PropertyEntity
from wikibaseintegrator.models import Qualifiers, References, Snak
from wikibaseintegrator.wbi_enums import WikibaseSnakType

from wikibasemigrator.model.quickstatements import (
    CreateLine,
    CreatePropertyLine,
    DateLine,
    DateQualifier,
    EntityLine,
    EntityQualifier,
    MonolingualTextLine,
    MonolingualTextQualifier,
    QuantityLine,
    QuantityQualifier,
    TextLine,
    TextQualifier,
    TimeQualifier,
    render_lines,
)
from wikibasemigrator.wikibase import WikibaseEntityTypes

logger = logging.getLogger(__name__)


class QuickStatementsGenerator:
    """
    Generate quick statements based on a given ItemEntity
    """

    def get_qs_url(self, item: ItemEntity, url: HttpUrl) -> HttpUrl:
        """
        The QuickStatements API does not work as expected.
        Not recommended to use at the moment
        :param item:
        :param url:
        :return:
        """

        qs_line = self.generate_item(item, newline="||")
        query = urllib.parse.urlencode({"v1": qs_line})
        qs_url = HttpUrl(f"{url}#/{query}")
        return qs_url

    def generate_items(self, items: list[ItemEntity], newline: str = "\n") -> str:
        """
        Generate QuickStatements for given list of items.
        :param items:
        :param newline:
        :return:
        """
        with ThreadPoolExecutor() as executor:
            func = partial(self.generate_item, newline=newline)
            result = executor.map(func, items)
        item_seperator = newline + newline
        quickstatements = item_seperator.join(result)
        return quickstatements

    def generate_item(self, item: ItemEntity, newline: str = "\n") -> str:
        """
        generate quick statements
        """
        lines: list[EntityLine | CreateLine | TextLine | CreatePropertyLine] = []
        if item.id is None:
            if isinstance(item, ItemEntity):
                lines.append(CreateLine())
            elif isinstance(item, PropertyEntity):
                lines.append(CreatePropertyLine(datatype=item.datatype))
            else:
                logger.debug(f"Quickstatements does not support creation of entities of type {item.ETYPE}")
                return ""
        lines.extend(self._get_label_lines(item))
        lines.extend(self._get_description_lines(item))
        lines.extend(self._get_aliases_lines(item))
        if item.ETYPE in WikibaseEntityTypes.support_sitelinks():
            lines.extend(self._get_sidelink_lines(item))
        lines.extend(self._get_statement_lines(item))
        # ToDo: ADD support for lexemes
        return render_lines(lines, newline=newline)

    def _get_item_subject(self, item: ItemEntity) -> str:
        qid = item.id
        if qid is None:
            qid = "LAST"
        return qid

    def _get_label_lines(self, item: ItemEntity) -> list[TextLine]:
        """
        Convert the labels of the given item into quick statement lines
        """
        subject = self._get_item_subject(item)
        lines: list[TextLine] = []
        for label in item.labels:
            try:
                line = TextLine(subject=subject, predicate=f"L{label.language}", target=label.value)
                lines.append(line)
            except Exception as ex:
                logger.debug(f"Exception while converting label {label}")
                logger.error(ex)
        return lines

    def _get_sidelink_lines(self, item: ItemEntity) -> list[TextLine]:
        """
        Convert the sidelinks of the given item into quick statement lines
        """
        subject = self._get_item_subject(item)
        lines: list[TextLine] = []
        for sidelink in item.sitelinks.sitelinks.values():
            try:
                line = TextLine(subject=subject, predicate=f"S{sidelink.site}", target=sidelink.title)
                lines.append(line)
            except Exception as ex:
                logger.debug("Exception while converting label lines: %s", ex)
        return lines

    def _get_description_lines(self, item: ItemEntity) -> list[TextLine]:
        """
        Convert the description of the given item into quick statement lines
        """
        subject = self._get_item_subject(item)
        lines: list[TextLine] = []
        for description in item.descriptions:
            try:
                line = TextLine(subject=subject, predicate=f"D{description.language}", target=description.value)
                lines.append(line)
            except Exception as ex:
                logger.debug("Exception while converting description lines: %s", ex)
        return lines

    def _get_aliases_lines(self, item: ItemEntity) -> list[TextLine]:
        """
        Convert the aliases of the given item into quick statement lines
        """
        subject = self._get_item_subject(item)
        lines: list[TextLine] = []
        for aliases in item.aliases.aliases.values():
            for alias in aliases:
                try:
                    line = TextLine(subject=subject, predicate=f"A{alias.language}", target=alias.value)
                    lines.append(line)
                except Exception as ex:
                    logger.debug("Exception while converting alias lines: %s", ex)
        return lines

    def _get_statement_lines(self, item: ItemEntity) -> list[TextLine | DateLine | EntityLine]:
        """
        Convert the statements of the given item into quick statement lines
        """
        subject = self._get_item_subject(item)
        lines: list[TextLine] = []
        for claim in item.claims:
            predicate = claim.mainsnak.property_number
            datatype = claim.mainsnak.datatype
            qualifiers = self._get_statement_qualifiers(claim.qualifiers)
            references = self._get_statement_references(claim.references)
            qualifiers.extend(references)
            if claim.mainsnak.snaktype is not WikibaseSnakType.KNOWN_VALUE:
                continue
            if datatype == "wikibase-item":
                line = EntityLine(
                    subject=subject,
                    predicate=predicate,
                    target=claim.mainsnak.datavalue["value"]["id"],
                    qualifiers=qualifiers,
                )
            elif datatype in ["external-id", "string", "url", "commonsMedia"]:
                line = TextLine(
                    subject=subject,
                    predicate=predicate,
                    target=claim.mainsnak.datavalue["value"],
                    qualifiers=qualifiers,
                )
            elif datatype == "time":
                date_str = claim.mainsnak.datavalue["value"]["time"]
                precision = claim.mainsnak.datavalue["value"]["precision"]
                calendar = claim.mainsnak.datavalue["value"]["calendarmodel"]
                line = DateLine(
                    subject=subject,
                    predicate=predicate,
                    target=date_str,
                    calendar=calendar,
                    qualifiers=qualifiers,
                    precision=precision,
                )
            elif datatype == "monolingualtext":
                text = claim.mainsnak.datavalue["value"]["text"]
                language = claim.mainsnak.datavalue["value"]["language"]
                line = MonolingualTextLine(
                    subject=subject, predicate=predicate, target=text, language=language, qualifiers=qualifiers
                )
            elif datatype == "quantity":
                snak = claim.mainsnak
                if not snak.datavalue:
                    logger.debug("Skipping qualifier with 'unknown value'")
                    continue
                amount = snak.datavalue["value"]["amount"]
                unit = snak.datavalue["value"]["unit"]
                if unit == "1":
                    unit = None
                else:
                    unit = unit.split("/")[-1]
                tolerance = snak.datavalue["value"].get("tolerance", None)
                line = QuantityLine(subject=subject, predicate=predicate, target=amount, tolerance=tolerance, unit=unit)
            else:
                print(datatype)
                # ToDo: Coordiantes
                continue
            lines.append(line)
        return lines

    def _get_statement_qualifiers(self, qualifiers: Qualifiers):
        line_qualifiers = []
        for qualifier in qualifiers:
            line = self._convert_snak(qualifier)
            if line:
                line_qualifiers.append(line)
        return line_qualifiers

    def _get_statement_references(self, references: References):
        line_reference = []
        for reference_group in references:
            for i, reference in enumerate(reference_group):
                new_reference_group = i == 0
                line = self._convert_snak(reference, as_reference=True, new_reference_group=new_reference_group)
                if line:
                    line_reference.append(line)
        return line_reference

    def _convert_snak(
        self, snak: Snak, as_reference: bool = False, new_reference_group: bool = False
    ) -> Union[TextQualifier, DateQualifier, "QuantityQualifier", EntityQualifier, None]:
        if snak.snaktype is not WikibaseSnakType.KNOWN_VALUE:
            # other snaktypes are not supported by quick statements
            return None
        property_id = snak.property_number
        if as_reference:
            property_id = property_id.replace("P", "S")
            if new_reference_group:
                property_id = f"!{property_id}"
        datatype = snak.datatype
        if datatype in ["string", "url", "external-id"]:
            value = snak.datavalue["value"]
            line = TextQualifier(predicate=property_id, target=value)
        elif datatype == "time":
            date_str = snak.datavalue["value"]["time"]
            precision = snak.datavalue["value"]["precision"]
            calendar = snak.datavalue["value"]["calendarmodel"]
            line = TimeQualifier(predicate=property_id, target=date_str, precision=precision, calendar=calendar)
        elif datatype == "wikibase-item":
            line = EntityQualifier(predicate=property_id, target=snak.datavalue["value"]["id"])
        elif datatype == "monolingualtext":
            text = snak.datavalue["value"]["text"]
            language = snak.datavalue["value"]["language"]
            line = MonolingualTextQualifier(predicate=property_id, target=text, language=language)
        elif datatype == "quantity":
            if not snak.datavalue:
                logger.debug("Skipping qualifier with 'unknown value'")
                return None
            amount = snak.datavalue["value"]["amount"]
            unit = snak.datavalue["value"]["unit"]
            if unit == "1":
                unit = None
            else:
                unit = unit.split("/")[-1]
            tolerance = snak.datavalue["value"].get("tolerance", None)
            line = QuantityQualifier(predicate=property_id, target=amount, unit=unit, tolerance=tolerance)
        else:
            logger.debug(f"Skipping qualifier with datatype {datatype}")
            return None
        return line
