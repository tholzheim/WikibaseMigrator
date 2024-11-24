import logging
import time
from io import StringIO

from nicegui import ui
from rich.console import Console
from rich.progress import track

file = StringIO()
console = Console(file=file, log_path=False)
console.print("Hello, world!")
logger = logging.getLogger()


class LogElementHandler(logging.Handler):
    """A logging handler that emits messages to a log element."""

    def __init__(self, element: ui.log, level: int = logging.NOTSET) -> None:
        self.element = element
        super().__init__(level)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.element.push(msg)
        except Exception:
            self.handleError(record)


log = ui.log(max_lines=10).classes("w-full")


async def update_log():
    print("Updating logs...")
    file.seek(0)
    content = file.read()
    log.push(content)


async def progress_test():
    total = 0
    for _ in track(range(100), description="Processing...", console=console, auto_refresh=True):
        # Fake processing time
        time.sleep(0.1)
        total += 1
    print(f"Processed {total} things.")


# ui.timer(0.5, update_log)


def update_label(x):
    print(x)
    file.seek(0)
    return file.read()


handler = LogElementHandler(log)
ui.label().bind_text_from(file, backward=update_label)
logger.addHandler(handler)
ui.context.client.on_disconnect(lambda: logger.removeHandler(handler))
ui.button("Log time", on_click=progress_test)

ui.run(port=9200)
