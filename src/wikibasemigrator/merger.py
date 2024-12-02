"""
Module to merge wikibase entities
"""

import json
import logging

from wikibaseintegrator.entities import ItemEntity
from wikibaseintegrator.models import Claim, Claims, Reference, Snak
from wikibaseintegrator.wbi_enums import ActionIfExists

from wikibasemigrator import WbEntity

logger = logging.getLogger(__name__)


class EntityMerger:
    """
    Merges wikibase entities
    """

    def __init__(self, action_if_exists: ActionIfExists = ActionIfExists.KEEP):
        """
        constructor
        """

        self.action_if_exists = action_if_exists

    def merge(self, source: WbEntity, target: WbEntity):
        """
        Merge source entity into target entity
        :param source: source entity
        :param target: target entity in which is merged into
        :return: target enttiy
        """
        self._merge_labels(source, target)
        self._merge_descriptions(source, target)
        self._merge_aliases(source, target)
        self._merge_sitelinks(source, target)
        self._merge_statements(source, target)
        return target

    def _merge_labels(self, source: WbEntity, target: WbEntity):
        """
        merge labels from source entity into target entity
        :param source:
        :param target:
        :return:
        """
        for label in source.labels:
            target.labels.set(language=label.language, value=label.value, action_if_exists=self.action_if_exists)

    def _merge_descriptions(self, source: WbEntity, target: WbEntity):
        """
        merge descriptions from source entity into target entity
        :param source:
        :param target:
        :return:
        """
        for description in source.descriptions:
            target.descriptions.set(
                language=description.language, value=description.value, action_if_exists=self.action_if_exists
            )

    def _merge_aliases(self, source: WbEntity, target: WbEntity):
        """
        merge aliases from source entity into target entity
        :param source:
        :param target:
        :return:
        """
        for language, aliases in source.aliases.aliases.items():
            values = [alias.value for alias in aliases]
            target.aliases.set(language=language, values=values, action_if_exists=ActionIfExists.APPEND_OR_REPLACE)

    def _merge_sitelinks(self, source: WbEntity, target: WbEntity):
        """
        merge sitelinks from source entity into target entity
        :param source:
        :param target:
        :return:
        """
        if not isinstance(source, ItemEntity):
            return
        for sitelink in source.sitelinks.sitelinks.values():
            if self.action_if_exists is ActionIfExists.REPLACE_ALL or sitelink.site not in target.sitelinks.sitelinks:
                target.sitelinks.set(site=sitelink.site, title=sitelink.title, badges=sitelink.badges)

    def _merge_statements(self, source: WbEntity, target: WbEntity):
        """
        merge statements from source entity into target entity
        :param source:
        :param target:
        :return:
        """
        for source_claim in source.claims:
            merge_with_claim = self._find_equivalent_mainsnak(
                source_claim, target.claims.get(source_claim.mainsnak.property_number)
            )
            if merge_with_claim:
                self._merge_claim(source_claim, merge_with_claim)
            else:
                # ToDo: Implement merging of statements and report issue in wikibase integrator
                #  → create test case and prepare fix
                # Issue: if snak value is unknown → KeyError
                target.claims.add(source_claim, action_if_exists=ActionIfExists.MERGE_REFS_OR_APPEND)
        for target_claim in target.claims:
            self._update_qualifier_order(target_claim)

    def _update_qualifier_order(self, claim: Claim):
        """
        Update the qualifier order of the given claim
        :param claim:
        :return:
        """
        used_qualifier = {pid for pid in claim.qualifiers.qualifiers}
        missing_qualifier_in_order = used_qualifier - set(claim.qualifiers_order)
        claim.qualifiers_order.extend(missing_qualifier_in_order)

    def _find_equivalent_mainsnak(self, claim: Claim, claims: Claims) -> Claim | bool:
        """
        Find equivalent mainsnak from given list of claims
        Only checks if the mainsnak is equivalent as the qualifier are also merged
        :param claim:
        :param claims:
        :return:
        """
        source_hash = self._get_datavalue_hash(claim.mainsnak.datavalue)
        for target_claim in claims:
            source_or_claim_have_no_qualifier = len(target_claim.qualifiers) == 0 or len(claim.qualifiers) == 0
            if (
                self._get_datavalue_hash(target_claim.mainsnak.datavalue) == source_hash
                and source_or_claim_have_no_qualifier
            ):
                return target_claim
        return False

    def _has_equivalent_snak(self, snak: Snak, snaks: list[Snak]) -> bool:
        """
        Check if an equivalent snak from given list of snaks exists
        Only checks if the mainsnak is equivalent as the qualifier are also merged
        :param claim:
        :param claims:
        :return:
        """
        source_hash = self._get_datavalue_hash(snak.datavalue)
        return any(self._get_datavalue_hash(target_snak.datavalue) == source_hash for target_snak in snaks)

    def _has_equivalent_reference(self, reference: Reference, references: list[Reference]) -> bool:
        """
        Check if an equivalent reference from given list of references exists
        Only checks if the mainsnak is equivalent as the qualifier are also merged
        :param claim:
        :param claims:
        :return:
        """
        source_hash = self._get_reference_hash(reference)
        return any(self._get_reference_hash(target_reference) == source_hash for target_reference in references)

    def _merge_claim(self, source: Claim, target: Claim):
        """
        Merge the claim qualifiers and references from source into target.
        :param source:
        :param target:
        :return:
        """
        if self._get_datavalue_hash(source.mainsnak.datavalue) != self._get_datavalue_hash(target.mainsnak.datavalue):
            logger.warning("Merging claims with different mainsnak hashes")
        qualifier: Snak
        for qualifier in source.qualifiers:
            if self._has_equivalent_snak(qualifier, target.qualifiers.get(qualifier.property_number)):
                # ToDo: can be removed once the action_if_exists is implemented
                pass
            else:
                target.qualifiers.add(qualifier, action_if_exists=self.action_if_exists)
        for reference in source.references.references:
            if self._has_equivalent_reference(reference, target.references.references):
                # ToDo: can be removed once the action_if_exists is implemented
                pass
            else:
                target.references.add(reference, action_if_exists=self.action_if_exists)

    def _get_datavalue_hash(self, datavalue: dict[str, str | int | float]) -> int:
        return hash(json.dumps(datavalue, sort_keys=True))

    def _get_reference_hash(self, reference: Reference) -> int:
        reference_hash = 0
        ref: Snak
        for ref in reference:
            reference_hash += self._get_datavalue_hash(ref.datavalue)
        return reference_hash
