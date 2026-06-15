from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from app.core.config import DEFAULT_CONFIG_PATH, load_config
from app.services.duplicate_governance import DuplicateGovernanceService
from app.services.file_content_vault import FileContentVaultService
from app.services.inventory_scanner import InventoryScanner
from app.services.parser_router import ParserRouterService

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


@app.command("copy-to-vault")
def copy_to_vault(
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Path to app.yaml. Defaults to project config/app.yaml.",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Maximum number of content records to process.",
    ),
    sha256: str | None = typer.Option(
        None,
        "--sha256",
        help="Process only the specified content sha256.",
    ),
    content_uid: str | None = typer.Option(
        None,
        "--content-uid",
        help="Process only the specified content uid (same as sha256 in 001).",
    ),
    refresh_metadata_only: bool = typer.Option(
        False,
        "--refresh-metadata-only",
        help="Refresh sidecar JSON and DB metadata without copying original.bin.",
    ),
) -> None:
    config_path = config or DEFAULT_CONFIG_PATH
    app_config = load_config(config_path)
    service = FileContentVaultService(app_config)
    result = service.copy_to_vault(
        limit=limit,
        sha256=sha256,
        content_uid=content_uid,
        refresh_metadata_only=refresh_metadata_only,
    )

    console.print(f"Candidates: {result.candidates}")
    console.print(f"Copied: {result.copied}")
    console.print(f"Skipped (already copied): {result.skipped}")
    console.print(f"Metadata refreshed: {result.metadata_refreshed}")
    console.print(f"Errors: {len(result.errors)}")


@app.command("govern-duplicates")
def govern_duplicates(
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Path to app.yaml. Defaults to project config/app.yaml.",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Maximum number of duplicate candidate contents to process.",
    ),
    sha256: str | None = typer.Option(
        None,
        "--sha256",
        help="Process only the specified content sha256.",
    ),
    content_uid: str | None = typer.Option(
        None,
        "--content-uid",
        help="Process only the specified content uid (same as sha256 in 001).",
    ),
) -> None:
    config_path = config or DEFAULT_CONFIG_PATH
    app_config = load_config(config_path)
    service = DuplicateGovernanceService(app_config)
    result = service.govern_duplicates(
        limit=limit,
        sha256=sha256,
        content_uid=content_uid,
    )

    console.print(f"Candidates: {result.candidates}")
    console.print(f"Groups processed: {result.groups_processed}")
    console.print(f"Groups upserted: {result.groups_upserted}")
    console.print(f"Instances linked: {result.instances_linked}")
    console.print(f"Suggestions generated: {result.suggestions_generated}")
    console.print(f"Skipped (unchanged): {result.skipped}")
    console.print(f"Errors: {len(result.errors)}")
    if result.duplicate_report_path is not None:
        console.print(f"Duplicate report: {result.duplicate_report_path}")
    if result.cleanup_suggestion_report_path is not None:
        console.print(f"Cleanup suggestion report: {result.cleanup_suggestion_report_path}")


@app.command("route-parsers")
def route_parsers(
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Path to app.yaml. Defaults to project config/app.yaml.",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Maximum number of vault-copied contents to route.",
    ),
    sha256: str | None = typer.Option(
        None,
        "--sha256",
        help="Process only the specified content sha256.",
    ),
    content_uid: str | None = typer.Option(
        None,
        "--content-uid",
        help="Process only the specified content uid (same as sha256 in 001).",
    ),
) -> None:
    config_path = config or DEFAULT_CONFIG_PATH
    app_config = load_config(config_path)
    service = ParserRouterService(app_config)
    result = service.route_parsers(
        limit=limit,
        sha256=sha256,
        content_uid=content_uid,
    )

    console.print(f"Candidates: {result.candidates}")
    console.print(f"Routed: {result.routed}")
    console.print(f"Skipped: {result.skipped}")
    console.print(f"Unknown: {result.unknown}")
    console.print(f"Unsupported: {result.unsupported}")
    console.print(f"Errors: {len(result.errors)}")
    if result.report_path is not None:
        console.print(f"Parser route report: {result.report_path}")


@app.command("build-parse-queue")
def build_parse_queue() -> None:
    typer.echo("build-parse-queue placeholder")


@app.command("parse")
def parse(limit: int = 10) -> None:
    typer.echo(f"parse placeholder limit={limit}")


if __name__ == "__main__":
    app()
