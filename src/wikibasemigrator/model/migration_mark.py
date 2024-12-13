import logging

from pydantic import BaseModel
from wikibaseintegrator import datatypes

from wikibasemigrator.model.datatypes import WbiDataTypes
from wikibasemigrator.model.profile import MigrationMarkConfig

logger = logging.getLogger(__name__)


class MigrationMark(BaseModel):
    """
    Migration mark to apply the
    """

    property_id: str
    property_type: WbiDataTypes
    value: str | None = None

    @classmethod
    def from_config(cls, config: MigrationMarkConfig | None) -> "MigrationMark | None":
        """
        inti MigrationMark from config
        :param config:
        :return:
        """
        if config is None:
            return None
        return MigrationMark(property_id=config.property_id, property_type=config.property_type)

    def get_claim(self) -> datatypes.BaseDataType | None:
        """
        Get the migration mark as claim
        :return:
        """
        if self.value is None or self.value == "":
            return None
        claim = None
        match self.property_type:
            case WbiDataTypes.WIKIBASE_ITEM:
                claim = datatypes.Item(prop_nr=self.property_id, value=self.value)
            case WbiDataTypes.STRING:
                claim = datatypes.String(prop_nr=self.property_id, value=self.value)
            case _:
                logger.debug(f"Unsupported MigrationMArk property_type: {self.property_type} → can not create claim")
        return claim
