import datetime
import logging
from concurrent.futures import Future

from nicegui import run, ui

from wikibasemigrator.migrator import WikibaseMigrator
from wikibasemigrator.model.migration_mark import MigrationMark
from wikibasemigrator.model.translations import EntitySetTranslationResult
from wikibasemigrator.web.components.progress import ProgressBar
from wikibasemigrator.web.translation_view import _get_csv_string, _get_tsv_string

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

    async def start_migration(
        self, translations: EntitySetTranslationResult, summary: str, migration_mark: MigrationMark | None = None
    ):
        """
        Start the migration process on the given translations
        :param translations:
        :param summary:
        :param migration_mark:
        :return:
        """
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
            migration_mark=migration_mark,
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
        csv_rows = []
        rows_errors = []
        csv_error_rows = []
        for translation in translations:
            if translation.created_entity is None:
                logger.debug("created_entity is not defined for translation → skipping")
                label = (
                    translation.original_entity.labels.get("en").value
                    if "en" in translation.original_entity.labels.values
                    else None
                )
                entity_id = translation.original_entity.id
                url = f"{self.profile.source.item_prefix}{entity_id}"
                rows_errors.append(
                    {
                        "id": entity_id,
                        "link": f"""<a href="{url}" target="_blank">{entity_id} ({label})</a>""",
                        "errors": str(translation.errors),
                    }
                )
                csv_error_rows.append(
                    {
                        "id": entity_id,
                        "label": label,
                        "url": url,
                        "errors": str(translation.errors),
                    }
                )
            else:
                label = (
                    translation.created_entity.labels.get("en").value
                    if "en" in translation.created_entity.labels.values
                    else None
                )
                entity_id = translation.created_entity.id
                url = f"{self.profile.target.item_prefix}{entity_id}"
                source_url = f"{self.profile.source.item_prefix}{translation.original_entity.id}"
                rows.append(
                    {
                        "id": entity_id,
                        "label": label,
                        "link": f"""<a href="{url}" target="_blank">{url}</a>""",
                        "source_entity": f"""<a href="{source_url}" target="_blank">{source_url}</a>""",
                        "migration_details": str(translation.errors),
                    }
                )
                csv_rows.append(
                    {
                        "id": entity_id,
                        "label": label,
                        "url": url,
                        "source_id": translation.original_entity.id,
                        "source_url": source_url,
                        "errors": str(translation.errors),
                    }
                )
        ui.label("Migrated Entities").classes("mx-auto")
        self.display_table_download(
            csv_rows,
            "migrated_entities",
            fieldnames=["id", "label", "url", "source_id", "source_url", "migration_details"],
        )
        ui.aggrid(
            {
                "columnDefs": [
                    {"headerName": "ID", "field": "id"},
                    {"headerName": "Label", "field": "label"},
                    {"headerName": "URL", "field": "link"},
                    {"headerName": "Source URL", "field": "source_entity"},
                    {
                        "headerName": "Migration Details",
                        "field": "errors",
                        "wrapText": True,
                        "autoHeight": True,
                    },
                ],
                "rowData": rows,
                "enableCellTextSelection": True,
            },
            html_columns=[2, 3],
        )
        if rows_errors:
            ui.label("Failed Migrations").classes("mx-auto")
            self.display_table_download(
                csv_error_rows, "failed_migrations", fieldnames=["id", "label", "url", "errors"]
            )
            ui.aggrid(
                {
                    "columnDefs": [
                        {"headerName": "ID", "field": "id"},
                        {"headerName": "Source", "field": "link"},
                        {
                            "headerName": "Error Messages",
                            "field": "errors",
                            "wrapText": True,
                            "autoHeight": True,
                            "enableCellTextSelection": True,
                        },
                    ],
                    "rowData": rows_errors,
                },
                html_columns=[0],
            )
        # ToDo: uncomment for darkmode support
        # grid.classes(add="ag-theme-alpine-auto-dark", remove="ag-theme-balham ag-theme-balham-dark")

    def display_table_download(self, rows: list[dict], postfix: str, fieldnames: list[str] | None = None):
        """
        Display the given download button to download the given table rows as csv or tsv
        :param rows:
        :param postfix:
        :return:
        """
        with ui.element("div"):
            with ui.dropdown_button("Download", auto_close=True):
                ui.item(
                    "table (.csv)",
                    on_click=lambda: ui.download(
                        _get_csv_string(rows, fieldnames=fieldnames),
                        f"{datetime.datetime.now().isoformat()}_{postfix}.csv",
                    ),
                )
                ui.item(
                    "table (.tsv)",
                    on_click=lambda: ui.download(
                        _get_tsv_string(rows, fieldnames=fieldnames),
                        f"{datetime.datetime.now().isoformat()}_{postfix}.tsv",
                    ),
                )
