import logging
from pathlib import Path

from wikibasemigrator.web.webserver import DEFAULT_ICON_PATH, Webserver

# path = Path(__file__).parent.joinpath("../profiles/test.yaml")
# path = Path(__file__).parent.joinpath("../profiles/WikibaseMigrationTest.yaml")
# path = Path(__file__).parent.joinpath("../profiles/FactGrid.yaml")
# path = Path.home().joinpath(".config/WikibaseMigrator/profiles/FactGridDev.yaml")
path = Path.home().joinpath(".config/WikibaseMigrator/profiles/WikibaseMigrationTest.yaml")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-8s %(name)-8s %(message)s",
)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("wikibaseintegrator").setLevel(logging.WARNING)
logging.getLogger("oauthlib.oauth1.rfc5849").setLevel(logging.WARNING)
logging.getLogger("requests_oauthlib.oauth1_auth").setLevel(logging.WARNING)
Webserver(path, DEFAULT_ICON_PATH).run(host="0.0.0.0", port=8009, reload=False, reconnect_timeout=10)
