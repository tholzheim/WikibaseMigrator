import concurrent.futures
import logging
from pathlib import Path

from nicegui import ui

from wikibasemigrator.exceptions import UserLoginRequiredException
from wikibasemigrator.migrator import WikibaseMigrator
from wikibasemigrator.model.profile import WikibaseMigrationProfile
from wikibasemigrator.model.translations import EntitySetTranslationResult
from wikibasemigrator.web.migration_view import MigrationView
from wikibasemigrator.web.oauth import MediaWikiUserIdentity
from wikibasemigrator.web.selection_view import SelectionView
from wikibasemigrator.web.translation_view import TranslationView
from wikibasemigrator.web.webpage import Webpage
from wikibasemigrator.wikibase import MediaWikiEndpoint, Query

logger = logging.getLogger(__name__)


class EndpointsAvailability:
    """
    Availability status of endpoints
    """

    source_sparql_endpoint: bool = False
    target_sparql_endpoint: bool = False
    target_mediawiki_api: bool = False

    def all_available(self):
        """
        Returns True if all endpoints are available
        :return:
        """
        return self.source_sparql_endpoint and self.target_sparql_endpoint and self.target_mediawiki_api


class WikibaseControllerPage(Webpage):
    """
    Migration Controller consists of the three steps
    - EntitySelection
    - Translation
    - Migration
    """

    def __init__(
        self,
        profile: WikibaseMigrationProfile,
        icon_path: Path | None = None,
        user: MediaWikiUserIdentity | None = None,
    ):
        super().__init__(profile, icon_path, user)
        self.migrator = WikibaseMigrator(self.profile)
        self.selection_view = SelectionView(self.profile, self.load_translator)
        self.translation_view = TranslationView(migrator=self.migrator, migration_callback=self.load_migration_view)
        self.migration_view = MigrationView(migrator=self.migrator)
        self.view_container: ui.element | None = None
        self.status_container: ui.element | None = None
        self.endpoints_availability = EndpointsAvailability()

    def setup_ui(self) -> None:
        """
        setup ui
        :return:
        """
        super().setup_ui()
        if self.container is None:
            logger.error("Abort setup container not yet setup")
            return
        with self.container:
            ui.label(self.profile.name).classes("text-4xl font-bold text-center p-2")
            self.status_container = ui.element("div").classes("flex flex-row mx-auto text-xl")
            self.setup_status_bar()
            self.check_service_availabilities()
            self.view_container = ui.element(tag="div").classes("container h-full")
            with self.view_container:
                if not self.endpoints_availability.all_available():
                    ui.notification(
                        timeout=None,
                        type="warning",
                        message="Some required services are not available. Please try again later.",
                        position="center",
                    )
                elif self.requires_login():
                    ui.notification(
                        timeout=None, type="info", message="Please login to migrate entities", position="center"
                    )
                else:
                    self.selection_view.setup_ui()

    def check_service_availabilities(self):
        """
        Check the availability of the used services
        """
        logger.info("Checking availability of used Services")
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future1 = executor.submit(Query.check_availability_of_sparql_endpoint, self.profile.source.sparql_url)
            future2 = executor.submit(Query.check_availability_of_sparql_endpoint, self.profile.target.sparql_url)
            future3 = executor.submit(MediaWikiEndpoint.check_availability, self.profile.target.mediawiki_api_url)

            self.endpoints_availability.source_sparql_endpoint = future1.result()
            self.endpoints_availability.target_sparql_endpoint = future2.result()
            self.endpoints_availability.target_mediawiki_api = future3.result()

        self.setup_status_bar()

    def setup_status_bar(self) -> None:
        """
        Setup status bar showing the availability of the source and target services
        """
        if self.status_container is None:
            logger.error("Abort setup container not yet setup")
            return
        self.status_container.clear()
        with self.status_container:
            ui.link(self.profile.source.name, target=self.profile.source.website.unicode_string(), new_tab=True)
            ui.icon(
                "wifi" if self.endpoints_availability.source_sparql_endpoint else "wifi_off",
                color="green" if self.endpoints_availability.source_sparql_endpoint else "red",
            ).tooltip(f"{self.profile.source.name} SPARQL Endpoint availability")
            ui.label("→")
            ui.link(self.profile.target.name, target=self.profile.target.website.unicode_string(), new_tab=True)
            ui.icon(
                "wifi" if self.endpoints_availability.target_sparql_endpoint else "wifi_off",
                color="green" if self.endpoints_availability.target_sparql_endpoint else "red",
            ).tooltip(f"{self.profile.target.name} SPARQL Endpoint availability")
            ui.icon(
                "wifi" if self.endpoints_availability.target_mediawiki_api else "wifi_off",
                color="green" if self.endpoints_availability.target_mediawiki_api else "red",
            ).bind_name_from(
                self.endpoints_availability,
                "target_mediawiki_api",
                backward=lambda is_available: "wifi" if is_available else "wifi_off",
            ).tooltip(f"{self.profile.target.name} Mediawiki API availability")

    def requires_login(self) -> bool:
        """
        Check if user login is required
        """
        if not self.profile.target.requires_login:
            return False
        try:
            self.migrator.get_wikibase_login(self.profile.target)
            return False
        except UserLoginRequiredException:
            return True

    async def load_selection_view(self):
        """
        Load selection view
        :return:
        """
        if self.view_container is None:
            return
        self.view_container.clear()
        with self.view_container:
            self.selection_view.setup_ui()

    async def load_translator(self, selected_items: list[str]) -> None:
        """
        Load translation view
        :param selected_items:
        :return:
        """
        if self.view_container is None:
            return
        self.view_container.clear()
        with self.view_container:
            ui.button(icon="back", text="Back to selection", on_click=self.load_selection_view).props("flat")
            self.translation_view.setup_ui()
            await self.translation_view.translate(selected_items)

    async def load_migration_view(self, translations: EntitySetTranslationResult, summary: str):
        """
        load migration view and start migration of the given translations
        :param translations:
        :param summary:
        :return:
        """
        if self.view_container is None:
            return
        self.view_container.clear()
        with self.view_container:
            self.migration_view.setup_ui()
            await self.migration_view.start_migration(translations, summary)
