import asyncio
import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

import pandas as pd
from nicegui import run, ui
from nicegui.events import ValueChangeEventArguments

from wikibasemigrator import config
from wikibasemigrator.model.profile import WikibaseMigrationProfile
from wikibasemigrator.wikibase import Query

logger = logging.getLogger(__name__)


class WikibaseItemSelector(ABC):
    """
    abstract class the defining the wikibase entity selection interface
    """

    def __init__(self, profile: WikibaseMigrationProfile, selection_callback: Callable[[list[str]], Awaitable[None]]):
        self.profile = profile
        self.selection_callback = selection_callback

    @abstractmethod
    def setup_ui(self):
        """
        setup the ui of the element
        """
        raise NotImplementedError

    @abstractmethod
    def get_selected_entities(self) -> list[str]:
        """
        Get selected entities
        :return: list of the selected entities
        """
        raise NotImplementedError

    async def handle_selection_callback(self):
        """
        Handle the selection callback
        :param selected_ids: list of selected entities
        """
        await self.selection_callback(self.get_selected_entities())

    def _add_translation_button_info_icon(self):
        """
        adds info icon for the translation button
        :return:
        """
        info_icon = ui.icon("info").classes("text-primary")
        info_icon.tooltip(
            f"Button starts the translation process that matches the {self.profile.source.name} IDs against the corresponding IDs of {self.profile.target.name}. This step does not change the {self.profile.target.name} Wikibase instance yet."  # noqa: E501
        )


class ItemSelectorElement(WikibaseItemSelector):
    """
    Select the
    """

    SEPERATOR = ","

    def __init__(self, profile: WikibaseMigrationProfile, selection_callback: Callable[[list[str]], Awaitable[None]]):
        super().__init__(profile, selection_callback)
        self.value: str = ""
        self.rows: list[dict] = []
        self._worker: asyncio.Task | None = None
        self._preview_table_container: ui.element | None = None

    def setup_ui(self):
        """
        setup the view
        """
        with ui.element("div") as container:
            container.classes("flex flex-col gap-2")
            ui.label("Provide a list of entities to translate. The list of entities must be comma seperated.")
            entity_input = ui.input(
                label="Item IDs",
                placeholder="e.g. Q1,Q123,Q423,...",
                on_change=self._handle_value_change,
                validation={"InvalidFormat": self._validate_value},
            )
            entity_input.classes("w-full rounded-md  hover:border-blue-500 border-blue-200")
            entity_input.props("clearable").props("outlined")
            entity_input.bind_value(self)
            entity_input.on("keydown.enter", self.handle_selection_callback)
            self._add_translation_button_info_icon()
            ui.button("Run matching!", on_click=self.handle_selection_callback)
            self._preview_table_container = ui.element("div")

    def update_preview_table(self):
        """
        update the preview table
        :return:
        """
        if self._preview_table_container is None:
            logger.debug("Preview table not yet created → Skipping selected entity preview")
            return
        rows = []
        for row in self.rows:
            qid = row.get("qid")
            label = row.get("label")
            url = self.profile.source.item_prefix.unicode_string() + qid
            rows.append({"id": f"""<a href="{url}" target="_blank">{qid}</a>""", "label": label})
        self._preview_table_container.clear()
        with self._preview_table_container:
            ui.label("Selected entities:")
            ui.aggrid(
                {
                    "columnDefs": [
                        {"headerName": "Entity ID", "field": "id"},
                        {"headerName": "Label", "field": "label"},
                    ],
                    "rowData": rows,
                    "enableCellTextSelection": True,
                },
                html_columns=[0],
            )

    def value_is_valid(self) -> bool:
        """
        Check if the value string is valid
        :return: True if the value string is valid, False otherwise
        """
        return self._validate_value(self.value)

    def get_selected_entities(self) -> list[str]:
        if self.value_is_valid():
            return self.value.strip().split(self.SEPERATOR)
        else:
            return []

    def _validate_value(self, value: str) -> bool:
        """
        Validate the input value
        :param value:
        :return:
        """
        if value is None:
            return True
        pattern = re.compile("^([PQ][0-9]+)(,([PQ][0-9]+))*$")
        return bool(pattern.match(value))

    async def _handle_value_change(self, event: ValueChangeEventArguments) -> None:
        if self.value and self._validate_value(self.value):
            if self._worker and not self._worker.done():
                self._worker.cancel()
            values = self.value.split(self.SEPERATOR)
            worker = asyncio.create_task(
                run.io_bound(
                    callback=Query.get_entity_label,
                    entity_ids=values,
                    endpoint_url=self.profile.source.sparql_url,
                    item_prefix=self.profile.source.item_prefix,
                )
            )
            self._worker = worker
            response = await worker
            if response:
                self.rows = response
            else:
                self.rows = []
            self.update_preview_table()


class QueryItemSelectorElement(WikibaseItemSelector):
    """
    Allows to select entities by providing a query
    """

    def __init__(self, profile: WikibaseMigrationProfile, selection_callback: Callable[[list[str]], Awaitable[None]]):
        """
        constructor
        :param profile: migration profile
        """
        super().__init__(profile, selection_callback)
        self.value = ""
        self.result_container: ui.element | None = None
        self.result: list[dict] | None = None

    def setup_ui(self):
        """
        setup the view
        """
        with ui.element("div") as container:
            container.classes("flex flex-col gap-2")
            ui.label(
                f"The SPARQL query must bind the ID of the entities to translate to the variable ?{config.ITEM_QUERY_VARIABLE}."  # noqa: E501
            )
            with ui.element("div") as div:
                div.classes("w-full h-min-1/2")
                editor = ui.codemirror(language="SPARQL", theme="githubLight")
                editor.classes("ring-2 ring-offset-2 border-blue-200 rounded-md")
                editor.bind_value(self)
            ui.button("Query", on_click=self._handle_query)

            self.result_container = ui.element(tag="div").classes("flex flex-col gap-2")
            self.display_result()

    async def _handle_query(self) -> None:
        """
        handle query b< executing the query and displaying the result
        :return:
        """
        if self.result_container is None:
            logger.debug("Result container is not setup → aborting handling of query")
            return
        self.result_container.clear()
        with self.result_container:
            ui.spinner(size="lg").classes("mx-auto")
        response = await run.io_bound(
            callback=Query.execute_query,
            query=self.value,
            endpoint_url=self.profile.source.sparql_url,
        )

        if response:
            self.result = response
            self.display_result()
        else:
            ui.notify("Query has no results", color="warning")

    def get_selected_entities(self) -> list[str]:
        """
        Get selected entities
        """
        if self.result is None:
            return []
        entity_ids_with_none: list[str | None] = [record.get(config.ITEM_QUERY_VARIABLE) for record in self.result]
        entity_ids_with_prefix: list[str] = [entity_id for entity_id in entity_ids_with_none if entity_id is not None]
        entity_ids = [
            entity_id.removeprefix(self.profile.source.item_prefix.unicode_string())
            for entity_id in entity_ids_with_prefix
        ]
        return entity_ids

    def display_result(self) -> None:
        """
        display the result of the query
        """
        if self.result and self.result_container is not None:
            self.result_container.clear()
            with self.result_container:
                df = pd.DataFrame.from_records(self.result)
                ui.aggrid.from_pandas(df).classes()
                valid_result = True
                with ui.element(tag="div").classes("flex flex-row gap-2"):
                    ui.label(f"{len(self.result)} results").classes("bg-green rounded-full px-2 py-1 flex-none")
                    if config.ITEM_QUERY_VARIABLE not in df.columns:
                        ui.label(f"?{config.ITEM_QUERY_VARIABLE} variable missing").classes(
                            "bg-red rounded-full px-2 py-1 flex-none"
                        )
                        valid_result = False
                self._add_translation_button_info_icon()
                translate_btn = ui.button(
                    "Run matching!",
                    on_click=self.handle_selection_callback,
                )
                translate_btn.set_enabled(valid_result)
