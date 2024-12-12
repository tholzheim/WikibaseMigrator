from pydantic import BaseModel

from wikibasemigrator.model.datatypes import WbiDataTypes
from wikibasemigrator.model.profile import MigrationMarkConfig


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
