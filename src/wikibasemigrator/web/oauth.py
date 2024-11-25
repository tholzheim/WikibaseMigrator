import time

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

    def is_valid(self) -> bool:
        """
        Check if the value is still valid
        :return:
        """
        now = time.time()
        issued_at = float(self.iat)
        return now < issued_at + self.exp
