import concurrent.futures
import logging
from pathlib import Path

from nicegui import app, ui

from wikibasemigrator import __version__
from wikibasemigrator.model.profile import WikibaseMigrationProfile
from wikibasemigrator.web.oauth import MediaWikiUserIdentity
from wikibasemigrator.wikibase import MediaWikiEndpoint, Query

logger = logging.getLogger(__name__)


class EndpointsAvailability:
    """
    Availability status of endpoints
    """

    source_sparql_endpoint: bool = False
    source_mediawiki_api: bool = False
    target_sparql_endpoint: bool = False
    target_mediawiki_api: bool = False

    def all_available(self):
        """
        Returns True if all endpoints are available
        :return:
        """
        return (
            self.source_sparql_endpoint
            and self.target_sparql_endpoint
            and self.target_mediawiki_api
            and self.source_mediawiki_api
        )


class Webpage:
    """
    Webpage template
    """

    def __init__(
        self,
        profile: WikibaseMigrationProfile,
        icon_path: Path | None = None,
        user: MediaWikiUserIdentity | None = None,
    ):
        self.profile = profile
        self.icon_path = icon_path
        self.user = user
        self.container: ui.element | None = None
        self.endpoints_availability = EndpointsAvailability()
        self.status_check: ui.timer | None = None

    def setup_ui(self):
        ui.colors(primary="#2c4e80ff")
        self.setup_header()
        self.setup_footer()
        self.container = ui.element(tag="div").classes("container flex flex-col mx-auto w-full h-full flex p-2")

    def setup_footer(self):
        """
        setup footer
        :return:
        """
        with ui.footer():
            with ui.element("div").classes("flex justify-between w-full"):
                with ui.element("div") as left:
                    left.classes("flex justify-start")
                    pass
                with ui.element("div") as middle:
                    middle.classes("flex justify-center")
                    ui.label(f"WikibaseMigrator {__version__}")
                with ui.element("div") as right:
                    right.classes("flex justify-end ")
                    self.status_container = ui.element("div").classes("flex flex-row")
                    self.status_check = ui.timer(0.1, self.check_service_availabilities)

    def setup_header(self):
        """
        setup page header
        """
        with ui.header().classes(replace="row items-center") as header:
            header.classes("bg-white dark:bg-slate-800 border-2 gap-2 flex flex-row p-2 gap-2")
            self.display_page_icon()
            with ui.link(target="/"):
                ui.button(icon="home", text="Home").props("flat")
            with ui.link(target="/config"):
                ui.button(icon="settings", text="Config").props("flat")
            with ui.element("a").classes(
                "flex flex-row text-lg text-black gap-1 hover:bg-slate-100 p-2 px-4 rounded"
            ) as link:
                link._props["href"] = "https://github.com/tholzheim/WikibaseMigrator"
                link._props["target"] = "_blank"
                ui.html(
                    content="""
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
                    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z">
                    </path>
                </svg>
                """  # noqa: E501
                )
                ui.label("GitHub")
            ui.element("div").classes("grow")
            if self.user:
                ui.button(self.user.username, on_click=self.logout).tooltip("Click to logout")
            else:
                oauth_login_url = "/login/wiki"
                with ui.link(target=oauth_login_url):
                    ui.button(icon="login", text="Login").props("flat")

    def display_page_icon(self):
        """
        Display page icon
        :return:
        """
        if self.icon_path.exists() and self.icon_path.is_file() and self.icon_path.suffix == ".svg":
            with ui.link(target="/"):
                ui.html(content=self.icon_path.read_text()).classes("w-32")

    def logout(self):
        app.storage.user["token"] = None
        app.storage.user["user"] = None
        ui.navigate.to("/", new_tab=False)

    def check_service_availabilities(self):
        """
        Check the availability of the used services
        """
        logger.info("Checking availability of used Services")
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future1 = executor.submit(Query.check_availability_of_sparql_endpoint, self.profile.source.sparql_url)
            future4 = executor.submit(MediaWikiEndpoint.check_availability, self.profile.source.mediawiki_api_url)
            future2 = executor.submit(Query.check_availability_of_sparql_endpoint, self.profile.target.sparql_url)
            future3 = executor.submit(MediaWikiEndpoint.check_availability, self.profile.target.mediawiki_api_url)

            self.endpoints_availability.source_sparql_endpoint = future1.result()
            self.endpoints_availability.target_sparql_endpoint = future2.result()
            self.endpoints_availability.target_mediawiki_api = future3.result()
            self.endpoints_availability.source_mediawiki_api = future4.result()

        self.setup_status_bar()

    def setup_status_bar(self) -> None:
        """
        Setup status bar showing the availability of the source and target services
        """
        icon_available = "wifi"
        icon_unavailable = "wifi_off"

        def show_endpoint_status(name: str, status: bool) -> None:
            with ui.element("div").classes("flex flex-row w-full"):
                ui.label(f"{name}:").classes("grow")
                ui.icon(icon_available if status else icon_unavailable, color="green" if status else "red").classes(
                    "justify-self-end"
                )

        if self.status_container is None:
            logger.error("Abort setup container not yet setup")
            return
        self.status_container.clear()

        with self.status_container:
            icon = icon_available if self.endpoints_availability.all_available() else icon_unavailable
            with ui.dialog() as dialog, ui.card().classes("flex flex-col"):
                ui.label("Endpoint availabilities").classes("text-xl")
                show_endpoint_status(
                    f"{self.profile.source.name} SPARQL Endpoint availability",
                    self.endpoints_availability.source_sparql_endpoint,
                )
                show_endpoint_status(
                    f"{self.profile.source.name} Mediawiki API availability",
                    self.endpoints_availability.source_mediawiki_api,
                )
                show_endpoint_status(
                    f"{self.profile.target.name} SPARQL Endpoint availability",
                    self.endpoints_availability.target_sparql_endpoint,
                )
                show_endpoint_status(
                    f"{self.profile.target.name} Mediawiki API availability",
                    self.endpoints_availability.target_mediawiki_api,
                )
                ui.button("Close", on_click=dialog.close)
            ui.icon(icon, color="green" if self.endpoints_availability.all_available() else "red").classes(
                "hover:cursor-pointer"
            ).on("click", dialog.open)
            if self.endpoints_availability.all_available() and self.status_check:
                self.status_check.deactivate()
