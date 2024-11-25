from pathlib import Path

from typer.testing import CliRunner

from wikibasemigrator.cli import app

runner = CliRunner()


def test_app_help():
    """
    test --help option
    """
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_app_migration_abort():
    """
    test migration of entities
    """
    path = Path(__file__).parent.joinpath("../src/wikibasemigrator/profiles/WikibaseMigrationTest.yaml")
    result = runner.invoke(
        app,
        ["migrate", "--config", path.resolve(), "--summary", "test cli", "--show-details", "--entity", "Q80"],
        input="n\n",
    )
    assert result.exit_code == 1


def test_app_migration_without_authentication():
    """
    test migration of entities without authentication which should result in an error message
    """
    path = Path(__file__).parent.joinpath("../src/wikibasemigrator/profiles/WikibaseMigrationTest.yaml")
    result = runner.invoke(
        app,
        ["migrate", "--config", path.resolve(), "--summary", "test cli", "--show-details", "--entity", "Q80"],
        input="Y\n",
    )
    assert result.exit_code == 0
    assert "Q80 (Tim Berners-Lee)" in result.output
    assert "Something went wrong migrating entity Q80" in result.output
