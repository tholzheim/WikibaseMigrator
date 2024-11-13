import logging
from collections.abc import Awaitable, Callable

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from wikibasemigrator.model.profile import WikibaseMigrationProfile
from wikibasemigrator.web.item_selectors import ItemSelectorElement, QueryItemSelectorElement

logger = logging.getLogger(__name__)


class SelectionView:
    """
    Provides input methods to select items for translation
    """

    def __init__(self, profile: WikibaseMigrationProfile, selection_callback: Callable[[list[str]], Awaitable[None]]):
        self.profile = profile
        self.container: ui.element | None = None
        self.controls_container: ui.element | None = None
        self.selection_container: ui.element | None = None
        self.selection_callback = selection_callback
        self.selected_selector: int = 1
        self.selectors = {
            1: ItemSelectorElement(self.profile, selection_callback=self.selection_callback),
            2: QueryItemSelectorElement(self.profile, selection_callback=self.selection_callback),
        }

    def setup_ui(self):
        """
        setup ui
        """
        with ui.element("div").classes("container mx-auto flex flex-col") as self.container:
            ui.label("Select Entities to migrate").classes("text-xl")
            with ui.element(tag="div") as self.controls_container:
                self.controls_container.classes("container flex flex-row gap-2")
                toggle2 = ui.toggle({1: "Item IDs", 2: "Query"}, on_change=self.switch_selector)
            with ui.element("div").classes("container flex flex-col") as self.selection_container:
                self.selectors[self.selected_selector].setup_ui()
            toggle2.bind_value(self, "selected_selector")

    def switch_selector(self, event: ValueChangeEventArguments) -> None:
        """
        Handle selector change event
        :param event:
        :return:
        """
        self.switch_to_selector(event.value)

    def switch_to_selector(self, selector_id: int) -> None:
        """
        Swithc go given selector
        :param selector_id: id of the selector to switch to
        :return: None
        """
        if self.selection_container is None:
            return
        selector = self.selectors[selector_id]
        self.selection_container.clear()
        with self.selection_container:
            selector.setup_ui()
