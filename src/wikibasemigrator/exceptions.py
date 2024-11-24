class UnknownEntityTypeException(Exception):
    """
    Type of the entity is not known.
    """

    def __init__(self, entity_id: str):
        self.entity_id = entity_id
        super().__init__(f'Unknown entity type "{entity_id}"')


class UserLoginRequiredException(Exception):
    """
    User login required.
    """
