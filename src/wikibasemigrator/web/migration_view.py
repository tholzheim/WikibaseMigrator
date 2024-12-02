import logging
from concurrent.futures import Future

from nicegui import run, ui

from wikibasemigrator.migrator import WikibaseMigrator
from wikibasemigrator.model.translations import EntitySetTranslationResult
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
            with ui.element("div").classes("container flex flex-col gap-2") as self.migration_container:
                ui.spinner()

    async def start_migration(self, translations: EntitySetTranslationResult, summary: str):
        if self.migration_container is None:
            logger.debug("Migration container has not been setup")
            return
        ui.notify("Staring migration")
        self.migration_container.clear()
        with self.migration_container:
            self.progress_bar = ProgressBar(total=len(translations.get_target_entities()))
            self.migration_log = ui.log(max_lines=10).classes("w-full h-90")

        await run.io_bound(
            self.migrator.migrate_entities_to_target,
            translations,
            summary=summary,
            entity_done_callback=self._update_progress,
        )
        ui.notify("Migration completed", type="positive")
        self.migration_container.clear()
        with self.migration_container:
            with ui.link(target="/"):
                ui.button("Back to selection")
            self.display_entities(translations)

    def _update_progress(self, future: Future):
        """
        Update the progress bar
        :param future:
        :return:
        """
        result = future.result()
        if self.progress_bar:
            self.progress_bar.increment()
        if self.migration_log:
            if result.created_entity is None:
                self.migration_log.push(f"Migration of entity {result.original_entity.id} failed")
            else:
                self.migration_log.push(f"Migrated entity: {result.created_entity.id}")

    def display_entities(self, translations: EntitySetTranslationResult):
        """
        Display the given entities as table
        :param entities:
        :return:
        """
        rows = []
        rows_errors = []
        for translation in translations:
            if translation.created_entity is None:
                logger.debug("created_entity is not defined for translation → skipping")
                label = (
                    translation.original_entity.labels.get("en").value
                    if "en" in translation.original_entity.labels.values
                    else None
                )
                url = f"{self.profile.source.item_prefix}{translation.original_entity.id}"
                rows_errors.append(
                    {
                        "link": f"""<a href="{url}" target="_blank">{translation.original_entity.id} ({label})</a>""",
                        "errors": str(translation.errors),
                    }
                )
            else:
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
                        "link": f"""<a href="{url}" target="_blank">{url}</a>""",
                        "errors": str(translation.errors),
                    }
                )
        ui.label("Migrated Entities").classes("mx-auto")
        ui.aggrid(
            {
                "columnDefs": [
                    {"headerName": "ID", "field": "id"},
                    {"headerName": "Label", "field": "label"},
                    {"headerName": "URL", "field": "link"},
                    {
                        "headerName": "Migration Details",
                        "field": "errors",
                        "wrapText": True,
                        "autoHeight": True,
                    },
                ],
                "rowData": rows,
            },
            html_columns=[2],
        )
        if rows_errors:
            ui.label("Failed Migrations").classes("mx-auto")
            ui.aggrid(
                {
                    "columnDefs": [
                        {"headerName": "Source", "field": "link"},
                        {
                            "headerName": "Error Messages",
                            "field": "errors",
                            "wrapText": True,
                            "autoHeight": True,
                        },
                    ],
                    "rowData": rows_errors,
                },
                html_columns=[0],
            )
        # ToDo: uncomment for darkmode support
        # grid.classes(add="ag-theme-alpine-auto-dark", remove="ag-theme-balham ag-theme-balham-dark")
