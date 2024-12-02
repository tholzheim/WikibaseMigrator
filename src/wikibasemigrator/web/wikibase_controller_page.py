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

logger = logging.getLogger(__name__)


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
        self.view_container_updater: ui.timer | None = None

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
            with ui.element("div").classes("flex flex-row mx-auto text-xl"):
                ui.link(self.profile.source.name, target=self.profile.source.website.unicode_string(), new_tab=True)
                ui.label("→")
                ui.link(self.profile.target.name, target=self.profile.target.website.unicode_string(), new_tab=True)
            self.view_container = ui.element(tag="div").classes("container h-full")
            self.view_container_updater = ui.timer(0.1, self.setup_view_container)

    def setup_view_container(self) -> None:
        if self.view_container is None:
            logger.error("Abort setup container not yet setup")
            return
        self.view_container.clear()
        if self.status_check:
            self.status_check.interval = 5.0
        if self.view_container_updater:
            self.view_container_updater.interval = 5.0
        with self.view_container:
            if not self.endpoints_availability.all_available():
                with ui.element("div").classes("flex fle-row"):
                    ui.label("Some required services are not available. Please try again later.").classes(
                        "bg-yellow rounded mx-auto p-2 mt-10 px-8"
                    )
            else:
                if self.status_check:
                    self.status_check.deactivate()
                if self.view_container_updater:
                    self.view_container_updater.deactivate()
                if self.requires_login():
                    ui.notification(
                        timeout=None, type="info", message="Please login to migrate entities", position="center"
                    )
                else:
                    self.selection_view.setup_ui()

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
