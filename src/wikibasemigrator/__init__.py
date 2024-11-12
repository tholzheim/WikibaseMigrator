import importlib.metadata

from wikibaseintegrator.entities import ItemEntity, LexemeEntity, MediaInfoEntity, PropertyEntity

__version__ = importlib.metadata.version("wikibasemigrator")

# Wikibaseintegrator BaseEntity does not support all the methods that the subclasses all have
WbEntity = ItemEntity | PropertyEntity | LexemeEntity | MediaInfoEntity
