import logging
from pathlib import Path

from nicegui import app, ui

from wikibasemigrator import __version__
from wikibasemigrator.exceptions import UserLoginRequiredException
from wikibasemigrator.migrator import ItemSetTranslationResult, WikibaseMigrator
from wikibasemigrator.model.profile import WikibaseMigrationProfile
from wikibasemigrator.oauth import MediaWikiUserIdentity
from wikibasemigrator.web.migration_view import MigrationView
from wikibasemigrator.web.selection_view import SelectionView
from wikibasemigrator.web.translation_view import TranslationView

logger = logging.getLogger(__name__)


class WikibaseControllerPage:
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
        self.profile = profile
        self.user = user
        self.icon_path = icon_path
        self.migrator = WikibaseMigrator(self.profile)
        self.selection_view = SelectionView(self.profile, self.load_translator)
        self.translation_view = TranslationView(migrator=self.migrator, migration_callback=self.load_migration_view)
        self.migration_view = MigrationView(migrator=self.migrator)
        self.container: ui.element | None = None
        self.view_container: ui.element | None = None

    def setup_ui(self) -> None:
        with ui.header().classes(replace="row items-center") as header:
            header.classes("bg-white dark:bg-slate-800 border-2 gap-2 flex flex-row p-2")
            self.display_page_icon()
            ui.element("div").classes("grow")
            if self.user:
                ui.button(self.user.username, on_click=self.logout).tooltip("Click to logout")
            else:
                oauth_login_url = "/login/wiki"
                with ui.link(target=oauth_login_url):
                    ui.button(icon="login", text="Login").props("flat")

        with ui.footer() as footer:
            with ui.element("div").classes("mx-auto"):
                ui.label(f"WikibaseMigrator {__version__}")

        with ui.element(tag="div").classes("container flex flex-col mx-auto w-full h-full flex p-2") as self.container:
            ui.label(self.profile.name).classes("text-4xl font-bold text-center p-2")
            with ui.element("div").classes("flex flex-row mx-auto text-xl"):
                ui.link(self.profile.source.name, target=self.profile.source.website.unicode_string(), new_tab=True)
                ui.label("→")
                ui.link(self.profile.target.name, target=self.profile.target.website.unicode_string(), new_tab=True)

            self.view_container = ui.element(tag="div").classes("container h-full")
            with self.view_container:
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
        try:
            self.migrator.get_wikibase_login(self.profile.target)
            return False
        except UserLoginRequiredException:
            return True

    def logout(self):
        app.storage.user["token"] = None
        ui.navigate.to("/", new_tab=False)

    def display_page_icon(self):
        """
        Display page icon
        :return:
        """
        if self.icon_path.exists() and self.icon_path.is_file() and self.icon_path.suffix == ".svg":
            ui.html(content=self.icon_path.read_text()).classes("w-32")

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

    async def load_migration_view(self, translations: ItemSetTranslationResult, summary: str):
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
