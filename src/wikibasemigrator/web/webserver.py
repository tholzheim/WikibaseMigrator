import logging
import os
from pathlib import Path

from authlib.integrations.starlette_client import OAuth
from authlib.jose import jwt
from authlib.jose.errors import InvalidTokenError
from nicegui import Client, app, ui
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

from wikibasemigrator.model.profile import UserToken, load_profile
from wikibasemigrator.web.config_page import ConfigPage
from wikibasemigrator.web.oauth import MediaWikiUserIdentity
from wikibasemigrator.web.wikibase_controller_page import WikibaseControllerPage

DEFAULT_ICON_PATH = Path(__file__).parent.joinpath("../resources/logo.svg")
logger = logging.getLogger(__name__)


class Webserver:
    """
    WikibaseMigrator Webserver
    """

    def __init__(self, profile_path: Path, icon_path: Path):
        """
        constructor
        :param profile_path: path to the profile configuration file
        """
        self.profile_path = profile_path
        self.profile = load_profile(profile_path)
        self.icon_path = icon_path
        self.oauth = OAuth()
        self.oauth.register(
            name="mediawiki",
            client_id=self.profile.target.consumer_key,
            client_secret=self.profile.target.consumer_secret,
            request_token_url=f"{self.profile.target.website}wiki/Special:OAuth/initiate",
            # request_token_params={"params": {"oauth_callback": "oob"}},
            access_token_url=f"{self.profile.target.website}wiki/Special:OAuth/token",
            access_token_params=None,
            authorize_url=f"{self.profile.target.website}wiki/Special:OAuth/authorize",
            authorize_params=None,
            api_base_url=self.profile.target.mediawiki_api_url,
            client_kwargs=None,
        )
        app.add_middleware(SessionMiddleware, secret_key=os.environ.get("NICEGUI_SECRET_KEY", ""))

        @app.route("/oauth_callback")
        async def oauth_callback(request: Request):
            wiki_oauth = self.oauth.create_client("mediawiki")
            token = await wiki_oauth.authorize_access_token(request)
            self.user_token = token

            return RedirectResponse("/")

        @app.route("/login/wiki")
        async def login_via_wiki(request: Request):
            wiki_oauth = self.oauth.create_client("mediawiki")
            redirect_url = "oob"
            response = await wiki_oauth.authorize_redirect(request, redirect_url)
            return response

        @ui.page("/")
        async def main_page(client: Client) -> None:
            await client.connected()
            profile = self.get_profile()
            user = await self.get_user()
            WikibaseControllerPage(profile, self.get_icon_path(), user=user).setup_ui()

        @ui.page("/config")
        async def config_page(client: Client) -> None:
            await client.connected()
            profile = self.get_profile()
            user = await self.get_user()
            ConfigPage(profile, self.get_icon_path(), user=user).setup_ui()

    @property
    def user_token(self) -> dict | None:
        """
        Get the user token from storage
        :return:
        """
        token = app.storage.user.get("token", None)
        return token

    @user_token.setter
    def user_token(self, token: dict | None) -> None:
        """
        Store the user token in storage
        :param token:
        :return:
        """
        app.storage.user["token"] = token

    @property
    def user(self) -> MediaWikiUserIdentity | None:
        """
        Get the user identity from storage
        :return:
        """
        user_record = app.storage.user.get("user", None)
        if user_record is None:
            user = None
        else:
            user = MediaWikiUserIdentity.model_validate_json(user_record)
            if not user.is_valid():
                user = None
        return user

    @user.setter
    def user(self, user: MediaWikiUserIdentity) -> None:
        if isinstance(user, BaseModel):
            app.storage.user["user"] = user.model_dump_json()
        else:
            app.storage.user["user"] = None

    async def get_user(self):
        """
        Get the user identity from storage
        :return:
        """
        if self.user is None:
            token = self.user_token
            if token is not None:
                self.user = await self.query_user(token)
        return self.user

    async def query_user(self, token: dict) -> MediaWikiUserIdentity:
        """
        Get user information based on the given token
        :param token:
        :return:
        """
        try:
            logger.info("Querying user info")
            resp = await self.oauth.mediawiki.post(
                f"{self.profile.target.website}w/index.php", token=token, params={"title": "Special:OAuth/identify"}
            )
            claims = jwt.decode(resp.text, self.profile.target.consumer_secret)
            claims.validate(leeway=10)
            user = MediaWikiUserIdentity.model_validate(claims)
            logger.info(f"User {user.username} logged in")
        except InvalidTokenError as e:
            logger.error("Error querying user info", exc_info=e)
            user = None
        return user

    def get_profile(self):
        """
        Get copy of profile configuration
        :return:
        """
        profile = self.profile.model_copy(deep=True)
        if self.user_token is not None:
            user_token = UserToken.model_validate(self.user_token)
            profile.target.user_token = user_token
        return profile

    def get_icon_path(self):
        """
        Get copy of icon path
        :return:
        """
        return Path(self.icon_path)

    def run(self, host: str = "0.0.0.0", port: int = 8009, reload: bool = False, **kwargs):
        """
        Start the web server
        :param reload:
        :param host:
        :param port:
        :return:
        """
        ui.run(
            host=host,
            port=port,
            title=self.profile.name,
            favicon=self.icon_path,
            reload=reload,
            **kwargs,
        )
