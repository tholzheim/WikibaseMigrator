import logging
from pathlib import Path

from fastapi import HTTPException
from nicegui import app, ui
from starlette.requests import Request
from starlette.responses import RedirectResponse

from wikibasemigrator.model.profile import load_profile
from wikibasemigrator.oauth import OAuth
from wikibasemigrator.web.wikibase_controller_page import WikibaseControllerPage

icon = Path(__file__).parent.joinpath("../resources/logo.svg")
# path = Path(__file__).parent.joinpath("../profiles/test.yaml")
path = Path(__file__).parent.joinpath("../profiles/WikibaseMigrationTest.yaml")
# path = Path(__file__).parent.joinpath("../profiles/FactGrid.yaml")
# path = Path.home().joinpath(".config/WikibaseMigrator/profiles/WikibaseMigrationTest.yaml")
config = load_profile(path)

logger = logging.getLogger(__name__)


@ui.page("/")
def main_page() -> None:
    WikibaseControllerPage(config, icon).setup_ui()


@app.get("/oauth_callback")
async def oauth_authenticate_callback(code: str, request: Request):
    if config.target.consumer_key is None:
        logger.debug("No consumer key defined unable to authenticate over OAauth")
        return RedirectResponse("/")
    try:
        logger.info(code)
        OAuth.fetch_access_token(
            code=code,
            consumer_key=config.target.consumer_key,
            mediawiki_rest_url=config.target.mediawiki_rest_url,
            callback_url="http://localhost:8009/oauth_callback",
        )
    except Exception as e:
        return HTTPException(status_code=401, detail=str(e))
    return RedirectResponse("/")


logging.basicConfig(level=logging.DEBUG)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("wikibaseintegrator").setLevel(logging.WARNING)
ui.run(port=8009, title=config.name, favicon=icon, storage_secret="WikibaseMigratorSecret")
