from nicegui import ui


class ProgressBar:
    """
    ProgressBar
    """

    def __init__(self, total: int):
        self.total = total
        self.current = 0
        self.progress_bar = ui.linear_progress().bind_value_from(self).classes("rounded")

    @property
    def value(self) -> float:
        return self.current / self.total

    def increment(self):
        self.current += 1
