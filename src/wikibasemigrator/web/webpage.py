from pathlib import Path

from nicegui import app, ui

from wikibasemigrator import __version__
from wikibasemigrator.model.profile import WikibaseMigrationProfile
from wikibasemigrator.web.oauth import MediaWikiUserIdentity


class Webpage:
    """
    Webpage template
    """

    def __init__(
        self,
        profile: WikibaseMigrationProfile,
        icon_path: Path | None = None,
        user: MediaWikiUserIdentity | None = None,
    ):
        self.profile = profile
        self.icon_path = icon_path
        self.user = user
        self.container: ui.element | None = None

    def setup_ui(self):
        ui.colors(primary="#2c4e80ff")
        self.setup_header()
        self.setup_footer()
        self.container = ui.element(tag="div").classes("container flex flex-col mx-auto w-full h-full flex p-2")

    def setup_footer(self):
        """
        setup footer
        :return:
        """
        with ui.footer():
            with ui.element("div").classes("mx-auto"):
                ui.label(f"WikibaseMigrator {__version__}")

    def setup_header(self):
        """
        setup page header
        """
        with ui.header().classes(replace="row items-center") as header:
            header.classes("bg-white dark:bg-slate-800 border-2 gap-2 flex flex-row p-2 gap-2")
            self.display_page_icon()
            with ui.link(target="/"):
                ui.button(icon="home", text="Home").props("flat")
            with ui.link(target="/config"):
                ui.button(icon="settings", text="Config").props("flat")
            with ui.element("a").classes(
                "flex flex-row text-lg text-black gap-1 hover:bg-slate-100 p-2 px-4 rounded"
            ) as link:
                link._props["href"] = "https://github.com/tholzheim/WikibaseMigrator"
                link._props["target"] = "_blank"
                ui.html(
                    content="""
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
                    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z">
                    </path>
                </svg>
                """  # noqa: E501
                )
                ui.label("GitHub")
            ui.element("div").classes("grow")
            if self.user:
                ui.button(self.user.username, on_click=self.logout).tooltip("Click to logout")
            else:
                oauth_login_url = "/login/wiki"
                with ui.link(target=oauth_login_url):
                    ui.button(icon="login", text="Login").props("flat")

    def display_page_icon(self):
        """
        Display page icon
        :return:
        """
        if self.icon_path.exists() and self.icon_path.is_file() and self.icon_path.suffix == ".svg":
            with ui.link(target="/"):
                ui.html(content=self.icon_path.read_text()).classes("w-32")

    def logout(self):
        app.storage.user["token"] = None
        app.storage.user["user"] = None
        ui.navigate.to("/", new_tab=False)
