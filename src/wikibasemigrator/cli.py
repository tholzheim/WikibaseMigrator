from concurrent.futures import Future
from pathlib import Path
from typing import Annotated

import typer
from nicegui import native
from rich import get_console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.progress import open as rich_open
from rich.table import Table

from wikibasemigrator import config
from wikibasemigrator.migrator import WikibaseMigrator
from wikibasemigrator.model.profile import WikibaseMigrationProfile, load_profile
from wikibasemigrator.model.translations import EntitySetTranslationResult
from wikibasemigrator.web.webserver import DEFAULT_ICON_PATH, Webserver
from wikibasemigrator.wikibase import Query

app = typer.Typer()
console = get_console()
DEFAULT_PROFILE_PATH = Path().home().joinpath(".config/WikibaseMigrator/profiles")

STYLE_ERROR_MSG = "bold red"


def complete_profile_paths(incomplete: str):
    """
    List of wikibase migration profiles in the default location
    """
    profiles = DEFAULT_PROFILE_PATH.iterdir()
    valid_completion_items = [profile.name for profile in profiles]
    for name in valid_completion_items:
        if name.startswith(incomplete):
            yield name


def get_profile_path(name: str) -> Path:
    """
    Get profile path
    :param name: name of the profile
    :return: path of the profile
    """
    return DEFAULT_PROFILE_PATH.joinpath(name)


@app.command(
    name="app",
)
def native_app(
    config: Annotated[
        str,
        typer.Option(help="The configuration file defining the Wikibases", autocompletion=complete_profile_paths),
    ],
):
    """
    Run the WikibaseMigrator web server as local app
    Note: Experimental feature as some of the imported resources are not localized yet
    """
    profile_path = get_profile_path(config)
    webserver = Webserver(profile_path, icon_path=DEFAULT_ICON_PATH)
    webserver.run(
        native=True, window_size=(1920, 1080), fullscreen=False, port=native.find_open_port(), frameless=False
    )


@app.command(
    name="webserver",
)
def webserver_app(
    config: Annotated[
        str,
        typer.Option(help="The configuration file defining the Wikibases", autocompletion=complete_profile_paths),
    ],
    host: Annotated[str, typer.Option(help="host of the webserver")] = "0.0.0.0",
    port: Annotated[int, typer.Option(help="port of the webserver")] = 8080,
):
    """
    Start the WikibaseMigrator web server
    """
    profile_path = get_profile_path(config)
    Webserver(profile_path, DEFAULT_ICON_PATH).run(host=host, port=port, reload=False)


@app.command()
def migrate(
    config: Annotated[
        str,
        typer.Option(help="The configuration file defining the Wikibases", autocompletion=complete_profile_paths),
    ],
    summary: Annotated[str | None, typer.Option(help="Summary message to add to the wikibase edits")] = None,
    entity: Annotated[list[str] | None, typer.Option(help="The items to migrate")] = None,
    query: Annotated[
        str | None,
        typer.Option(help="The query querying the items to migrate. The items to migrate must have the binding ?items"),
    ] = None,
    query_file: Annotated[
        str | None,
        typer.Option(
            help=f"The query file with a query querying the items to migrate. The items to migrate must have the binding ?{config.ITEM_QUERY_VARIABLE}"  # noqa: E501
        ),
    ] = None,
    show_details: Annotated[bool, typer.Option(help="Show detailed information during the migration process")] = False,
    force: Annotated[bool, typer.Option(help="If True migrate items directly to target wikibase")] = False,
):
    """
    Migrate the provided entities
    """
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
    )
    profile_path = get_profile_path(config)
    if not profile_path.exists():
        console.print(f"Profile {profile_path} not found", style=STYLE_ERROR_MSG)
        raise typer.Abort()
    profile: WikibaseMigrationProfile = load_profile(profile_path)
    console.print(f"Loaded profile: {profile.name}")

    if entity is None:
        query_path: Path | None
        if isinstance(query_file, str):
            query_path = Path(query_file)
        else:
            query_path = query_file
        query_str = resolve_query_params(query=query, query_file=query_path)
        entities = select_entities_from_query(query_str, profile=profile, progress=progress)
    else:
        entities = entity
    migrator = WikibaseMigrator(profile)
    translations = translate_entities(entities, migrator, progress)
    source_labels = _query_source_labels(translations=translations, profile=profile, progress=progress)
    target_labels = _query_target_labels(translations=translations, profile=profile, progress=progress)
    show_translation_result(translations)
    if show_details or not force:
        show_translation_details(
            translations=translations, source_labels=source_labels, target_labels=target_labels, profile=profile
        )
    if not force:
        apply_migration = typer.confirm("Migrate entities with the shown mapping?")
    else:
        apply_migration = force
    if not apply_migration:
        print("Not migrating entities")
        raise typer.Abort()
    else:
        with Progress(*Progress.get_default_columns()) as progress:
            migration_task = progress.add_task("[green]Migrating entities...", total=len(translations.entities))

            def update_progress(future: Future):
                """
                Update the progress bar
                :param future:
                :return:
                """
                progress.advance(migration_task)
                result = future.result()
                if show_details:
                    console.print(f"Migrated entity {result.created_entity.id}")

            migrator.migrate_entities_to_target(translations, summary=summary, entity_done_callback=update_progress)
        show_migration_result(translations, profile)
        console.print("Migration done", style="bold green")


def show_translation_details(
    translations: EntitySetTranslationResult,
    source_labels: dict[str, str | None],
    target_labels: dict[str, str | None],
    profile: WikibaseMigrationProfile,
):
    """
    Show detailed information of the translation process
    :param translations:
    :param source_labels:
    :param target_labels:
    :param profile:
    :return:
    """
    show_applied_mappings(
        translations=translations, source_labels=source_labels, target_labels=target_labels, profile=profile
    )
    show_missing_items(translations=translations, source_labels=source_labels, profile=profile)
    show_missing_properties(translations, source_labels=source_labels, profile=profile)


def translate_entities(entities: list[str], migrator, progress: Progress) -> EntitySetTranslationResult:
    """
    Translate the entities
    :return:
    """
    console.log(f"Start translation of {len(entities)} items")
    with progress:
        translation_task = progress.add_task("[green]Translating entities...", total=1, completed=1)
        translations = migrator.translate_entities_by_id(entities)
        progress.update(translation_task, completed=1)
    return translations


def _query_source_labels(
    translations: EntitySetTranslationResult, profile: WikibaseMigrationProfile, progress: Progress
) -> dict[str, str | None]:
    """
    Query source labels
    :return:
    """
    with progress:
        target_label_task = progress.add_task("[green]Querying target labels...", total=1, completed=1)
        lod = Query.get_entity_label(
            endpoint_url=profile.target.sparql_url,
            entity_ids=translations.get_target_entity_ids(),
            item_prefix=profile.target.item_prefix,
        )
        target_labels = {label["qid"]: label.get("label") for label in lod if isinstance(label.get("label"), str)}
        progress.update(target_label_task, completed=1)
    return target_labels


def _query_target_labels(
    translations: EntitySetTranslationResult, profile: WikibaseMigrationProfile, progress: Progress
) -> dict[str, str | None]:
    """
    Query target labels
    :return:
    """
    source_labels = {}
    with progress:
        source_label_task = progress.add_task("[green]Querying source labels...", total=1, completed=1)
        lod = Query.get_entity_label(
            endpoint_url=profile.source.sparql_url,
            entity_ids=translations.get_source_entity_ids(),
            item_prefix=profile.source.item_prefix,
        )
        source_labels = {label["qid"]: label.get("label") for label in lod if isinstance(label.get("label"), str)}
        progress.update(source_label_task, completed=1)
    return source_labels


def resolve_query_params(query_file: Path | None, query: str | None):
    """
    Resolve query parameters
    :param query_file:
    :param query:
    :return:
    """
    if query_file:
        if not query_file.exists():
            console.print(f"Provided query file {query_file} does not exist", style=STYLE_ERROR_MSG)
            console.log("Aborting migration")
            raise typer.Abort()
        with rich_open(query_file, "rb") as file:
            query_str = file.read()
    elif query:
        query_str = query
    else:
        raise typer.BadParameter("No items to migrate. Please provide a list of entity IDs, a query or a query file")
    return query_str


def select_entities_from_query(query: str, profile: WikibaseMigrationProfile, progress: Progress):
    """
    Select the entities by executing the query
    :return:
    """
    with progress:
        query_task = progress.add_task("[green]Querying entities...", total=1, completed=1)
        lod = Query.execute_query(query=query, endpoint_url=profile.source.sparql_url)
        entities_with_prefix = [
            d.get(config.ITEM_QUERY_VARIABLE) for d in lod if d.get(config.ITEM_QUERY_VARIABLE, None)
        ]
        entities = [
            entity_id.replace(profile.source.item_prefix.unicode_string(), "")
            for entity_id in entities_with_prefix
            if entity_id is not None
        ]
        progress.update(query_task, completed=1)
    return entities


def show_translation_result(translations: EntitySetTranslationResult):
    """
    show short overview table of the translation result
    :param translations:
    :return:
    """
    table = Table(title="Translation Result")
    table.add_column("Existing Mappings", justify="right", style="green")
    table.add_column("Missing Items", style="magenta")
    table.add_column("Missing Properties", justify="right", style="red")
    table.add_row(
        str(len([k for k, v in translations.get_mapping().items() if v])),
        str(len(translations.get_missing_items())),
        str(len(translations.get_missing_properties())),
    )
    console.print(table)


def show_applied_mappings(
    translations: EntitySetTranslationResult,
    source_labels: dict[str, str | None],
    target_labels: dict[str, str | None],
    profile: WikibaseMigrationProfile,
):
    """
    show table of applied mappings
    """
    mapping_table = Table(title="Applied Mapping")
    mapping_table.add_column("Source", style="blue")
    mapping_table.add_column("Target", style="green")
    mapping_table.add_column("Source URL", justify="left")
    mapping_table.add_column("Target URL", justify="left")
    for source_id, target_id in sorted(translations.get_mapping().items()):
        if target_id is None:
            continue
        mapping_table.add_row(
            f"{source_id} ({source_labels.get(source_id)})",
            f"{target_id} ({target_labels.get(target_id)})",
            f"{profile.source.item_prefix}{source_id}",
            f"{profile.target.item_prefix}{target_id}",
        )
    console.print(mapping_table)


def show_missing_items(
    translations: EntitySetTranslationResult, source_labels: dict[str, str | None], profile: WikibaseMigrationProfile
):
    """
    show table of missing items
    """
    item_table = Table(title="Missing Items")
    item_table.add_column("Item", style="red")
    item_table.add_column("Source URL", justify="left")
    for source_id in sorted(translations.get_missing_items()):
        item_table.add_row(f"{source_id} ({source_labels.get(source_id)})", f"{profile.source.item_prefix}{source_id}")
    console.print(item_table)


def show_missing_properties(
    translations: EntitySetTranslationResult, source_labels: dict[str, str | None], profile: WikibaseMigrationProfile
):
    """
    show table of missing properties
    """
    property_table = Table(title="Missing Properties")
    property_table.add_column("Property", style="red")
    property_table.add_column("Source URL", justify="left")
    for source_id in sorted(translations.get_missing_properties()):
        property_table.add_row(
            f"{source_id} ({source_labels.get(source_id)})", f"{profile.source.item_prefix}{source_id}"
        )
    console.print(property_table)


def show_migration_result(translations: EntitySetTranslationResult, profile: WikibaseMigrationProfile):
    """
    Show migration result and migration errors as table
    """
    result_table = Table(title="Migrated Entities")
    result_table.add_column("Entity", style="green")
    result_table.add_column("Target URL", justify="left")
    error_table = Table(title="Migration Errors")
    error_table.add_column("Entity", style="red")
    error_table.add_column("Source URL", justify="left")
    error_table.add_column("Error Message", justify="left")
    for translation in translations:
        if translation.created_entity is None:
            console.log(f"Something went wrong migrating entity {translation.original_entity.id} {translation.errors}")
            if "en" in translation.original_entity.labels.values:
                label = translation.original_entity.labels.get("en").value
            else:
                label = None
            target_id = translation.original_entity.id
            error_table.add_row(
                f"{target_id} ({label})", f"{profile.source.item_prefix}{target_id}", f"{translation.errors}"
            )
        else:
            if "en" in translation.created_entity.labels.values:
                label = translation.created_entity.labels.get("en").value
            else:
                label = None
            target_id = translation.created_entity.id
            result_table.add_row(f"{target_id} ({label})", f"{profile.target.item_prefix}{target_id}")
    console.print(result_table)
    console.print(error_table)


if __name__ == "__main__":
    app()
