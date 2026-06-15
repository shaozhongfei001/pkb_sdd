from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from app.core.config import DEFAULT_CONFIG_PATH, load_config
from app.services.duplicate_governance import DuplicateGovernanceService
from app.services.file_content_vault import FileContentVaultService
from app.services.inventory_scanner import InventoryScanner
from app.services.markitdown_parser import (
    PARSE_MARKITDOWN_MAX_LIMIT,
    MarkItDownParserService,
)
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


@app.command("parse-markitdown")
def parse_markitdown(
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Path to app.yaml. Defaults to project config/app.yaml.",
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
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Maximum number of in-scope contents to parse.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Do not write parsed artifacts or call MarkItDown.",
    ),
) -> None:
    if not sha256 and not content_uid and limit is None:
        console.print(
            "ERROR: must provide at least one of --sha256, --content-uid, or --limit"
        )
        raise typer.Exit(code=1)
    if limit is not None and limit < 1:
        console.print("ERROR: --limit must be >= 1")
        raise typer.Exit(code=1)
    if limit is not None and limit > PARSE_MARKITDOWN_MAX_LIMIT:
        console.print(f"ERROR: --limit must be <= {PARSE_MARKITDOWN_MAX_LIMIT}")
        raise typer.Exit(code=1)

    config_path = config or DEFAULT_CONFIG_PATH
    app_config = load_config(config_path)

    if not dry_run:
        from app.adapters.markitdown_adapter import MarkItDownAdapter, MarkItDownAdapterError

        try:
            MarkItDownAdapter.check_import()
        except MarkItDownAdapterError as exc:
            console.print(f"ERROR: {exc.message}")
            raise typer.Exit(code=1) from exc

    service = MarkItDownParserService(app_config)
    result = service.parse_markitdown(
        sha256=sha256,
        content_uid=content_uid,
        limit=limit,
        dry_run=dry_run,
    )

    console.print(f"Candidates: {result.total_candidates}")
    console.print(f"In-scope candidates: {result.in_scope_candidates}")
    console.print(f"Parsed: {result.parsed_count}")
    console.print(f"Skipped: {result.skipped_count}")
    console.print(f"Failed: {result.failed_count}")
    console.print(f"Empty: {result.empty_count}")
    console.print(f"Dry run: {result.dry_run}")
    console.print(f"Errors: {len(result.errors)}")
    if result.report_path is not None:
        console.print(f"Parse markitdown report: {result.report_path}")


@app.command("build-parse-queue")
def build_parse_queue() -> None:
    typer.echo("build-parse-queue placeholder")


@app.command("parse")
def parse(limit: int = 10) -> None:
    typer.echo(f"parse placeholder limit={limit}")


if __name__ == "__main__":
    app()
