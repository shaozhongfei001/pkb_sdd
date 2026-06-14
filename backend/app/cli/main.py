from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from app.core.config import get_settings, load_settings
from app.core.database import get_session
from app.services.inventory_scanner import InventoryScanner

app = typer.Typer(help="Personal KB CLI. Implement commands according to specs.")
console = Console()


def _resolve_config_path(config: str | None) -> Path | None:
    if config is None:
        return None
    return Path(config).expanduser().resolve()


@app.command()
def scan(
    path: str = typer.Option(..., "--path", help="Directory to scan for document files."),
    config: str | None = typer.Option(
        None,
        "--config",
        help="Path to app.yaml (default: project config/app.yaml).",
    ),
    source_root: str | None = typer.Option(
        None,
        "--source-root",
        help="Logical source root stored on file instances (default: same as --path).",
    ),
):
    """Scan a directory and register file instances and content objects."""
    scan_path = Path(path).expanduser().resolve()
    config_path = _resolve_config_path(config)
    settings = load_settings(config_path) if config_path else get_settings()
    settings.ensure_readonly()

    source_root_path = Path(source_root).expanduser().resolve() if source_root else scan_path

    with get_session(settings) as session:
        scanner = InventoryScanner(session, settings)
        report = scanner.scan_directory(scan_path, source_root_path)

    table = Table(title="Inventory Scan Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Scanned files", str(report.scanned_files))
    table.add_row("New instances", str(report.new_instances))
    table.add_row("Updated instances", str(report.updated_instances))
    table.add_row("New contents", str(report.new_contents))
    table.add_row("Updated contents", str(report.updated_contents))
    table.add_row("Duplicate instances", str(report.duplicate_instances))
    table.add_row("Errors", str(len(report.errors)))
    console.print(table)

    if report.errors:
        for item in report.errors:
            console.print(f"[red]ERROR[/red] {item.path}: {item.message}")
        raise typer.Exit(code=1)


@app.command("build-parse-queue")
def build_parse_queue():
    typer.echo("build-parse-queue placeholder")


@app.command("parse")
def parse(limit: int = 10):
    typer.echo(f"parse placeholder limit={limit}")


if __name__ == "__main__":
    app()
