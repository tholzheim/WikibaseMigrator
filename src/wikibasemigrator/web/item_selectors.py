import asyncio
import re
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

import pandas as pd
from nicegui import run, ui
from nicegui.events import ValueChangeEventArguments

from wikibasemigrator.model.profile import WikibaseMigrationProfile
from wikibasemigrator.wikibase import Query


class WikibaseItemSelector(ABC):
    """
    abstract class the defining the wikibase item selection interface
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
    def get_selected_items(self) -> list[str]:
        """
        Get selected items
        :return: list of the selected items
        """
        raise NotImplementedError

    async def handle_selection_callback(self):
        """
        Handle the selection callback
        :param selected_ids: list of selected items
        """
        await self.selection_callback(self.get_selected_items())


class ItemSelectorElement(WikibaseItemSelector):
    """
    Select the
    """

    SEPERATOR = ","

    def __init__(self, profile: WikibaseMigrationProfile, selection_callback: Callable[[list[str]], Awaitable[None]]):
        super().__init__(profile, selection_callback)
        self.value = None
        self.rows = []
        self.selection_display: ui.table | None = None
        self._worker: asyncio.Task | None = None

    def setup_ui(self):
        """
        setup the view
        """
        with ui.element("div") as container:
            container.classes("flex flex-col gap-2")
            ui.label("Provide a list of items to translate. The list of items must be comma seperated.")
            item_input = ui.input(
                label="Item IDs",
                placeholder="e.g. Q1,Q123,Q423,...",
                on_change=self._handle_value_change,
                validation={"InvalidFormat": self._validate_value},
            )
            item_input.classes("w-full rounded-md  hover:border-blue-500 border-blue-200")
            item_input.props("clearable").props("outlined")
            item_input.bind_value(self)
            item_input.on("keydown.enter", self.handle_selection_callback)
            ui.button("Translate", on_click=self.handle_selection_callback)

            ui.label("Selected items:")
            with ui.element(tag="div"):
                columns = [
                    {"name": "qid", "label": "Qid", "field": "qid", "required": True, "align": "left"},
                    {"name": "label", "label": "Label", "field": "label", "sortable": True, "align": "left"},
                ]

                self.selection_display = ui.table(columns=columns, rows=self.rows, row_key="qid")
                self.selection_display.add_slot(
                    "body-cell-qid",
                    f"""
                    <q-td :props="props">
                        <a :href="'{self.profile.source.item_prefix}' + props.value">{{{{ props.value }}}}</a>
                    </q-td>
                """,
                )

    def value_is_valid(self) -> bool:
        """
        Check if the value string is valid
        :return: True if the value string is valid, False otherwise
        """
        return self._validate_value(self.value)

    def get_selected_items(self) -> list[str]:
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
                    callback=Query.get_item_label,
                    item_ids=values,
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
            self.selection_display.update_rows(self.rows)


class QueryItemSelectorElement(WikibaseItemSelector):
    """
    Allows to select items by providing a query
    """

    ITEM_QUERY_VARIABLE = "item"

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
            ui.label("The SPARQL query must bind the items to translate to the variable ?item.")
            with ui.element("div") as div:
                div.classes("w-full h-min-1/2")
                editor = ui.codemirror(language="SPARQL", theme="githubLight")
                editor.classes("ring-2 ring-offset-2 border-blue-200 rounded-md")
                editor.bind_value(self)
            ui.button("Query", on_click=self._handle_query)

            self.result_container = ui.element(tag="div").classes("flex flex-col gap-2")
            self.display_result()

    async def _handle_query(self) -> None:
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

    def get_selected_items(self) -> list[str]:
        """
        Get selected items
        """
        item_ids: list[str] = [record.get(self.ITEM_QUERY_VARIABLE) for record in self.result]
        item_ids = filter(lambda item: item is not None, item_ids)
        item_ids = [item_id.removeprefix(self.profile.source.item_prefix.unicode_string()) for item_id in item_ids]
        return item_ids

    def display_result(self) -> None:
        """
        display the result of the query
        """
        if self.result:
            self.result_container.clear()
            with self.result_container:
                df = pd.DataFrame.from_records(self.result)
                ui.aggrid.from_pandas(df).classes()
                valid_result = True
                with ui.element(tag="div").classes("flex flex-row gap-2"):
                    ui.label(f"{len(self.result)} results").classes("bg-green rounded-full px-2 py-1 flex-none")
                    if self.ITEM_QUERY_VARIABLE not in df.columns:
                        ui.label(f"?{self.ITEM_QUERY_VARIABLE} variable missing").classes(
                            "bg-red rounded-full px-2 py-1 flex-none"
                        )
                        valid_result = False
                translate_btn = ui.button(
                    "Translate",
                    on_click=self.handle_selection_callback,
                )
                translate_btn.set_enabled(valid_result)
