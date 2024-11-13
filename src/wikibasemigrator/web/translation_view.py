import datetime
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from nicegui import run, ui

from wikibasemigrator.migrator import ItemSetTranslationResult, WikibaseMigrator
from wikibasemigrator.qsgenerator import QuickStatementsGenerator
from wikibasemigrator.web.components.code import Code
from wikibasemigrator.web.components.wikibase_item import TranslatedWikibaseItemWidget
from wikibasemigrator.wikibase import Query

logger = logging.getLogger(__name__)


class LogElementHandler(logging.Handler):
    """A logging handler that emits messages to a log element."""

    def __init__(self, element: ui.log, level: int = logging.NOTSET) -> None:
        self.element = element
        super().__init__(level)

    def emit(self, record: logging.LogRecord) -> None:
        """
        emit changes to the log element
        :param record:
        :return:
        """
        try:
            msg = self.format(record)
            self.element.push(msg)
        except Exception:
            self.handleError(record)


class TranslationView:
    """
    Provides an overview of the translated items and options to generate quickstatements
    or to directly migrate the items to another wikibase
    """

    def __init__(
        self, migrator: WikibaseMigrator, migration_callback: Callable[[ItemSetTranslationResult, str], Awaitable[None]]
    ) -> None:
        self.migrator = migrator
        self.profile = self.migrator.profile
        self.migration_callback = migration_callback
        self.container: ui.element | None = None
        self.translation_result_container: ui.element | None = None
        self.translations: ItemSetTranslationResult | None = None
        self.source_labels: dict[str, str] | None = None
        self.target_labels: dict[str, str] | None = None
        self.summary = ""

    def setup_ui(self):
        """
        setup ui
        :return:
        """
        with ui.element("div").classes("container mx-auto flex flex-col") as self.container:
            ui.label("Translation Overview").classes("text-xl")
            with ui.element("div").classes("container flex flex-col") as self.translation_result_container:
                ui.spinner()

    async def translate(self, item_ids: list[str]):
        """
        start the translation process for the given item_ids and show the progress and result
        :param item_ids:
        :return:
        """
        if self.translation_result_container is None:
            logger.debug("translation result container is not setup yet")
            return
        self.translation_result_container.clear()
        with ui.element("div").classes("container mx-auto flex flex- gap-2") as self.translation_result_container:
            ui.spinner().classes("mx-auto")
            log = ui.log(max_lines=10).classes("w-full h-60")
            handler = LogElementHandler(log)
            logging.root.addHandler(handler)
        self.translation_result_container.update()
        logger.info(f"Start translation of {len(item_ids)} items...")
        self.translations = await run.io_bound(self.migrator.translate_items_by_id, item_ids)
        await self.fetch_labels()
        logger.info("Displaying Translation result...")
        self.translation_result_container.clear()
        with ui.element("div").classes("container flex flex-col gap-2") as self.translation_result_container:
            self.display_applied_mappings()
            self.display_migration_controls()
            self.display_translation_item_viewer()
            self.display_missing_mappings()
            self.display_quickstatements()

    def display_migration_controls(self):
        """
        display migration controls
        :return:
        """
        with ui.element("div").classes("container flex flex-row gap-2 w"):
            ui.input(label="summary", placeholder="Migrated items for...").bind_value(self, "summary").classes("grow")
            ui.button(text="Migrate", on_click=self.migrate).classes("max-w-1/3")

    def display_translation_item_viewer(self):
        """
        display translation iten viewer
        :return:
        """
        with ui.expansion(
            "Translation Item Viewer", icon="preview", caption="view translation per item in detail"
        ).classes("w-full ring-2 rounded"):
            with ui.element("div").classes("rounded bg-sky-50 p-4 flex flex-col gap-2"):
                selections = self.get_translated_items_from_source()
                if selections:
                    first_value = next(iter(selections))
                    select = ui.select(selections, value=first_value).classes("w-full")
                    item_container = ui.element("div").classes("container flex flex-col")
                    select.on_value_change(lambda e: self.display_translated_items(item_container, e.value))
                    self.display_translated_items(item_container, first_value)

    def display_quickstatements(self):
        """
        display quickstatements
        :return:
        """
        qs_generator = QuickStatementsGenerator()
        quickstatements = qs_generator.generate_items(self.translations.get_target_entities())
        with ui.expansion(text="QuickStatements").classes("ring-2 rounded"):
            if self.profile.target.quickstatement_url is not None:
                with ui.link(
                    target=self.profile.target.quickstatement_url.unicode_string(),
                    new_tab=True,
                ) as link:
                    link.classes("flex flex-row gap-2")
                    qs_icon = Path(__file__).parent.joinpath("../resources/Commons_to_Wikidata_QuickStatements.svg")
                    ui.html(qs_icon.read_text())
                    ui.label("Open Quickstatements Endpoint")
            ui.button(
                "Download",
                on_click=lambda: ui.download(
                    quickstatements.encode(), f"{datetime.datetime.now().strftime('%Y-%m-%dT%H%M%S')}_qs-migration.qs"
                ),
            )
            Code(quickstatements, language="quickstatements").classes(" p-2")

    def display_missing_mappings(self):
        """
        display missing mappings
        :return:
        """
        with ui.expansion(text="Missing Mappings").classes("ring-2 rounded"):
            self.display_missing_properties()
            self.display_missing_items()

    def get_translated_items_from_source(self) -> dict[str, str]:
        """
        Assumes that the translations and source_labels are defined
        :return:
        """
        if not (self.translations and self.source_labels):
            return {}
        source_items = self.translations.get_translation_source_item_ids()
        mapping = {item: f"{item} ({self.source_labels.get(item, '')})" for item in source_items}
        return mapping

    async def fetch_labels(self):
        """
        fetch labels from source and target
        :return:
        """
        logger.info("Fetching source labels...")
        source_labels_raw = await run.io_bound(
            callback=Query.get_item_label,
            item_ids=self.translations.get_source_entity_ids(),
            endpoint_url=self.profile.source.sparql_url,
            item_prefix=self.profile.source.item_prefix,
            language=None,
        )
        self.source_labels = {label["qid"]: label.get("label") for label in source_labels_raw}
        logger.info("Fetching target labels...")
        target_labels_raw = await run.io_bound(
            callback=Query.get_item_label,
            item_ids=self.translations.get_target_entity_ids(),
            endpoint_url=self.profile.target.sparql_url,
            item_prefix=self.profile.target.item_prefix,
            language=None,
        )
        self.target_labels = {label["qid"]: label.get("label") for label in target_labels_raw}

    def display_translated_items(self, item_container: ui.element, source_item_id: str):
        """
        Display Translation result of given Item
        :param item_container:
        :param source_item_id:
        :return:
        """
        if self.translations is None:
            logger.debug("No translations to display → skipping setup of TranslatedWikibaseItemWidget")
            return
        item_container.clear()
        with item_container:
            try:
                translation = self.translations.get_translation_result_by_source_id(source_item_id)
                TranslatedWikibaseItemWidget(
                    source_url=self.profile.source.item_prefix,
                    target_url=self.profile.target.item_prefix,
                    source_labels=self.source_labels,
                    target_labels=self.target_labels,
                    translation_result=translation,
                )
            except Exception as e:
                logger.error(e)
                raise e

    async def migrate(self):
        """
        handle migration button event
        :return:
        """
        if not self.translations.items:
            ui.notify("No entities to migrate. (Selected entities might already exist)", type="warning")
        elif not self.summary:
            ui.notify("Please provide a summary for the migration", type="warning")
        else:
            await self.migration_callback(self.translations, self.summary)

    def display_missing_properties(self):
        """
        display missing properties
        :return:
        """
        rows = []
        values = self.translations.get_missing_property_mapings()
        values = list(set(values) - set(self.translations.get_source_root_entity_ids()))
        for entity_id in values:
            label = self.source_labels.get(entity_id, "")
            url = f"{self.profile.source.item_prefix}{entity_id}"
            rows.append(
                {
                    "id": entity_id,
                    "label": label,
                    "link": f"""<a href="{url}" target="_blank">{url}</a>""",
                }
            )
        with ui.element("div").classes("flex flex-col gap-2 w-full"):
            ui.label(f"Missing Properties {len(values)}").classes("text-xl mx-auto")
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

    def display_missing_items(self):
        """
        display missing items as table
        :return:
        """
        rows = []
        values = self.translations.get_missing_item_mapings()
        values = list(set(values) - set(self.translations.get_source_root_entity_ids()))
        self.translations.get_target_entities()
        for entity_id in values:
            label = self.source_labels.get(entity_id, "")
            url = f"{self.profile.source.item_prefix}{entity_id}"
            rows.append(
                {
                    "id": entity_id,
                    "label": label,
                    "link": f"""<a href="{url}" target="_blank">{url}</a>""",
                }
            )
        with ui.element("div").classes("flex flex-col gap-2 w-full"):
            ui.label(f"Missing Items {len(values)}").classes("text-xl mx-auto")
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

    def display_applied_mappings(self):
        """
        display applied mappings as table
        """
        rows = []
        mappings = self.translations.get_existing_mappings()
        for source_id, target_id in mappings.items():
            source_label = self.source_labels.get(source_id, "")
            source_url = f"{self.profile.source.item_prefix}{source_id}"
            target_label = self.target_labels.get(target_id, "")
            target_url = f"{self.profile.target.item_prefix}{target_id}"
            rows.append(
                {
                    "source": f"""<a href="{source_url}" target="_blank">{source_id} ({source_label})</a>""",
                    "target": f"""<a href="{target_url}" target="_blank">{target_id} ({target_label})</a>""",
                }
            )
        with ui.element("div").classes("flex flex-col gap-2 w-full"):
            ui.label(f"Applied Mapping {len(mappings)}").classes("text-xl mx-auto")
            ui.aggrid(
                {
                    "columnDefs": [
                        {"headerName": "Source", "field": "source"},
                        {"headerName": "Target", "field": "target"},
                    ],
                    "rowData": rows,
                },
                html_columns=[0, 1],
            )
