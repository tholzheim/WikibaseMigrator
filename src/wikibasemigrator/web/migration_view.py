import logging
from concurrent.futures import Future

from nicegui import run, ui

from wikibasemigrator.migrator import ItemSetTranslationResult, WikibaseMigrator
from wikibasemigrator.web.components.progress import ProgressBar

logger = logging.getLogger(__name__)


class MigrationView:
    """
    Provides a progress overview
    """

    def __init__(self, migrator: WikibaseMigrator):
        """
        constructor
        :param profile: Migration profile
        """
        self.migrator = migrator
        self.profile = migrator.profile
        self.container: ui.element | None = None
        self.migration_container: ui.element | None = None
        self.progress_counter = 0
        self.progress_bar: ProgressBar | None = None
        self.migration_log: ui.log | None = None

    def setup_ui(self):
        with ui.element("div").classes("container mx-auto flex flex-col") as self.container:
            ui.label("Migrating Entities").classes("text-xl")
            with ui.element("div").classes("container flex flex-col") as self.migration_container:
                ui.spinner()

    async def start_migration(self, translations: ItemSetTranslationResult, summary: str):
        ui.notify("Staring migration")
        self.migration_container.clear()
        with self.migration_container:
            self.progress_bar = ProgressBar(total=len(translations.get_target_items()))
            self.migration_log = ui.log(max_lines=10).classes("w-full h-90")

        migrated_entities = await run.io_bound(
            self.migrator.migrate_entities_to_target,
            translations,
            summary=summary,
            entity_done_callback=self._update_progress,
        )
        ui.notify("Migration completed")
        self.migration_container.clear()
        with self.migration_container:
            self.display_entities(translations)

    def _update_progress(self, future: Future):
        """
        Update the progress bar
        :param future:
        :return:
        """
        result = future.result()
        self.progress_bar.increment()
        self.migration_log.push(f"Migrated entity: {result.created_entity.id}")

    def display_entities(self, translations: ItemSetTranslationResult):
        """
        Display the given entities as table
        :param entities:
        :return:
        """
        rows = []
        for translation in translations:
            label = (
                translation.created_entity.labels.get("en").value
                if "en" in translation.created_entity.labels.values
                else None
            )
            url = f"{self.profile.target.item_prefix}{translation.created_entity.id}"
            rows.append(
                {
                    "id": translation.created_entity.id,
                    "label": label,
                    "link": f"""<a href="{url}">{url}</a>""",
                }
            )
        ui.aggrid(
            {
                "columnDefs": [
                    {"headerName": "ID", "field": "id"},
                    {"headerName": "Label", "field": "label"},
                    {"headerName": "URL", "field": "link"},
                ],
                "rowData": rows,
            },
            html_columns=[2],
        )
        # ToDo: uncomment for darkmode support
        # grid.classes(add="ag-theme-alpine-auto-dark", remove="ag-theme-balham ag-theme-balham-dark")
