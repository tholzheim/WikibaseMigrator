import logging
import os
from pathlib import Path

from wikibasemigrator.web.webserver import DEFAULT_ICON_PATH, Webserver

profile_path = Path("config.yaml")

logging.basicConfig(
    level=os.environ.get("LOGGING_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-8s %(message)s",
)
webserver = Webserver(profile_path, DEFAULT_ICON_PATH)
webserver.run(
    host=os.environ.get("WEBSERVER_HOST", "0.0.0.0"),
    port=int(os.environ.get("WEBSERVER_PORT", 8080)),
    storage_secret=os.environ.get("STORAGE_SECRET"),
    reload=False,
)
