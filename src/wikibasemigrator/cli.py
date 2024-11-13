from concurrent.futures import Future
from pathlib import Path
from typing import Annotated

import typer
from rich import get_console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.progress import open as rich_open
from rich.table import Table

from wikibasemigrator.migrator import WikibaseMigrator
from wikibasemigrator.model.profile import WikibaseMigrationProfile, load_profile
from wikibasemigrator.wikibase import Query

app = typer.Typer()
console = get_console()
DEFAULT_PROFILE_PATH = Path().home().joinpath(".config/WikibaseMigrator/profiles")
ITEM_QUERY_VARIABLE = "item"


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


@app.command()
def migrate(
    config: Annotated[
        str,
        typer.Option(help="The configuration file defining the Wikibases", autocompletion=complete_profile_paths),
    ],
    summary: Annotated[str, typer.Option(help="Summary message to add to the wikibase edits")],
    entity: Annotated[list[str] | None, typer.Option(help="The items to migrate")] = None,
    query: Annotated[
        str | None,
        typer.Option(help="The query querying the items to migrate. The items to migrate must have the binding ?items"),
    ] = None,
    query_file: Annotated[
        Path | None,
        typer.Option(
            help=f"The query file with a query querying the items to migrate. The items to migrate must have the binding ?{ITEM_QUERY_VARIABLE}"  # noqa: E501
        ),
    ] = None,
    show_details: Annotated[bool, typer.Option(help="Show detailed information during the migration process")] = False,
    force: Annotated[bool, typer.Option(help="If True migrate items directly to target wikibase")] = False,
):
    """
    Migrate the provided entities
    :param config:
    :param summary:
    :param entity:
    :param query:
    :param query_file:
    :param show_details:
    :param force:
    :return:
    """
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
    )
    profile_path = get_profile_path(config)
    if not profile_path.exists():
        console.print(f"Profile {profile_path} not found", style="bold red")
        raise typer.Abort()
    profile: WikibaseMigrationProfile = load_profile(profile_path)
    console.print(f"Loaded profile: {profile.name}")

    if entity is None:
        if query or query_file:
            if query_file:
                if not query_file.exists():
                    console.print(f"Provided query file {query_file} does not exist", style="bold red")
                    console.log("Aborting migration")
                    raise typer.Abort()
                with rich_open(query_file, "rb") as file:
                    query_str = file.read()
            elif query:
                query_str = query
            else:
                raise typer.BadParameter("If no items are given a query has to be provided")
            with progress:
                query_task = progress.add_task("[green]Querying entities...", total=1, completed=1)
                lod = Query.execute_query(query=query_str, endpoint_url=profile.source.sparql_url)
                entities_with_prefix = [d.get(ITEM_QUERY_VARIABLE) for d in lod if d.get(ITEM_QUERY_VARIABLE, None)]
                entity = [
                    entity_id.replace(profile.source.item_prefix.unicode_string(), "")
                    for entity_id in entities_with_prefix
                    if entity_id is not None
                ]
                progress.update(query_task, completed=1)
        else:
            console.print(
                "No items to migrate. Please provide a list of entity IDs, a query or a query file", style="bold red"
            )
            console.log("Aborting migration")
            raise typer.Abort()
    console.log(f"Start translation of {len(entity)} items")
    with progress:
        translation_task = progress.add_task("[green]Translating entities...", total=1, completed=1)
        migrator = WikibaseMigrator(profile)
        translations = migrator.translate_items_by_id(entity)
        progress.update(translation_task, completed=1)
    with progress:
        source_label_task = progress.add_task("[green]Querying source labels...", total=1, completed=1)
        lod = Query.get_item_label(
            endpoint_url=profile.source.sparql_url,
            item_ids=translations.get_source_entity_ids(),
            item_prefix=profile.source.item_prefix,
        )
        source_labels = {label["qid"]: label.get("label") for label in lod}
        progress.update(source_label_task, completed=1)
    with progress:
        target_label_task = progress.add_task("[green]Querying target labels...", total=1, completed=1)
        lod = Query.get_item_label(
            endpoint_url=profile.target.sparql_url,
            item_ids=translations.get_target_entity_ids(),
            item_prefix=profile.target.item_prefix,
        )
        target_labels = {label["qid"]: label.get("label") for label in lod}
        progress.update(target_label_task, completed=1)
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
    if show_details or not force:
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

        item_table = Table(title="Missing Items")
        item_table.add_column("Item", style="red")
        item_table.add_column("Source URL", justify="left")
        for source_id in sorted(translations.get_missing_items()):
            item_table.add_row(
                f"{source_id} ({source_labels.get(source_id)})", f"{profile.source.item_prefix}{source_id}"
            )
        console.print(item_table)

        property_table = Table(title="Missing Properties")
        property_table.add_column("Property", style="red")
        property_table.add_column("Source URL", justify="left")
        for source_id in sorted(translations.get_missing_properties()):
            property_table.add_row(
                f"{source_id} ({source_labels.get(source_id)})", f"{profile.source.item_prefix}{source_id}"
            )
        console.print(property_table)
    if not force:
        apply_migration = typer.confirm("Migrate entities with the shown mapping?")
    else:
        apply_migration = force
    if not apply_migration:
        print("Not migrating entities")
        raise typer.Abort()
    else:
        with Progress(*Progress.get_default_columns()) as progress:
            migration_task = progress.add_task("[green]Migrating entities...", total=len(translations.items))

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
        result_table = Table(title="Migrated Entities")
        result_table.add_column("Entity", style="green")
        result_table.add_column("Target URL", justify="left")
        for translation in translations:
            if translation.created_entity is None:
                console.log(
                    f"Something went wrong migrating entity {translation.original_item.id} {translation.errors}"
                )
                continue
            label = (
                translation.created_entity.labels.get("en").value
                if "en" in translation.created_entity.labels.values
                else None
            )
            target_id = translation.created_entity.id
            result_table.add_row(f"{target_id} ({label})", f"{profile.target.item_prefix}{target_id}")
        console.print(result_table)
        console.print("Migration done", style="bold green")


if __name__ == "__main__":
    app()
