from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from app.core.config import DEFAULT_CONFIG_PATH, load_config
from app.services.inventory_scanner import InventoryScanner

app = typer.Typer(help="Personal KB CLI. Implement commands according to specs.")
console = Console()


@app.command()
def scan(
    path: str = typer.Option(..., "--path", help="Directory to scan for document files."),
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Path to app.yaml. Defaults to project config/app.yaml.",
    ),
    source_root: str | None = typer.Option(
        None,
        "--source-root",
        help="Optional source root label stored on file instances.",
    ),
) -> None:
    config_path = config or DEFAULT_CONFIG_PATH
    app_config = load_config(config_path)
    scanner = InventoryScanner(app_config)
    scan_root = Path(path)
    source_root_path = Path(source_root) if source_root else None
    result = scanner.scan(scan_root=scan_root, source_root=source_root_path)

    console.print(f"Scanned files: {result.scanned_files}")
    console.print(f"New instances: {result.new_instances}")
    console.print(f"Updated instances: {result.updated_instances}")
    console.print(f"New contents: {result.new_contents}")
    console.print(f"Updated contents: {result.updated_contents}")
    console.print(f"Duplicate instances: {result.duplicate_instances}")
    console.print(f"Errors: {len(result.errors)}")


@app.command("build-parse-queue")
def build_parse_queue() -> None:
    typer.echo("build-parse-queue placeholder")


@app.command("parse")
def parse(limit: int = 10) -> None:
    typer.echo(f"parse placeholder limit={limit}")


if __name__ == "__main__":
    app()
