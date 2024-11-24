from pydantic import BaseModel, ConfigDict, HttpUrl


class MediaWikiUserIdentity(BaseModel):
    """
    mediawiki user information
    """

    model_config = ConfigDict(extra="ignore")

    iss: HttpUrl
    aud: str
    exp: int
    iat: int
    sub: int
    username: str
    editcount: int
    confirmed_email: bool
    registered: int
    groups: list[str]
    rights: list[str]
    grants: list[str]
    nonce: str
