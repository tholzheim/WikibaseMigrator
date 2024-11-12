import asyncio
import json
import time

from nicegui import ui
from nicegui.elements.markdown import remove_indentation
from nicegui.elements.mixins.content_element import ContentElement
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import ABAPLexer, Python3Lexer


class Code(ContentElement):
    """
    based on the default nicegui Code element ui.code but the markdown highlighting replaced by Pygments
    to get better control over the html generation
    """

    def __init__(self, content: str = "", *, language: str = "python") -> None:
        """Code

        This element displays a code block with syntax highlighting.

        In secure environments (HTTPS or localhost), a copy button is displayed to copy the code to the clipboard.

        :param content: code to display
        :param language: language of the code (default: "python")
        """
        super().__init__(content=remove_indentation(content))

        with self:
            self.classes("ring-2 ring-offset-2 ring-blue rounded relative")
            self.markdown = ui.html().bind_content_from(
                self,
                "content",
                lambda content: highlight(
                    content,
                    self._get_lexer(language),
                    HtmlFormatter(style="staroffice", cssclass="source", full=True),
                ),
            )
            self.copy_button = (
                ui.button(icon="content_copy", on_click=self.show_checkmark)
                .props("round flat size=sm")
                .classes("absolute right-4 top-4 opacity-20 hover:opacity-80")
                .on("click", js_handler=f"() => navigator.clipboard.writeText({json.dumps(self.content)})")
            )

        self._last_scroll: float = 0.0
        self.markdown.on("scroll", self._handle_scroll)
        ui.timer(0.1, self._update_copy_button)

        self.client.on_connect(
            lambda: self.client.run_javascript(f"""
            if (!navigator.clipboard) getElement({self.copy_button.id}).$el.style.display = 'none';
        """)
        )

    def _get_lexer(self, language: str) -> ABAPLexer:
        match language.lower():
            case "python":
                return Python3Lexer()
            case "quickstatements":
                return ABAPLexer()

    async def show_checkmark(self) -> None:
        """Show a checkmark icon for 3 seconds."""
        self.copy_button.props("icon=check")
        await asyncio.sleep(3.0)
        self.copy_button.props("icon=content_copy")

    def _handle_scroll(self) -> None:
        self._last_scroll = time.time()

    def _update_copy_button(self) -> None:
        self.copy_button.set_visibility(time.time() > self._last_scroll + 1.0)

    def _handle_content_change(self, content: str) -> None:
        pass  # handled by markdown element
