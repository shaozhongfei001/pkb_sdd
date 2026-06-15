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
from app.services.parse_registry import (
    PARSE_REGISTRY_MAX_LIMIT,
    ParseRegistryError,
    ParseRegistryService,
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


@app.command("register-parse-report")
def register_parse_report(
    report_path: Path = typer.Option(..., "--report-path", help="005 parse report JSON path."),
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Path to app.yaml. Defaults to project config/app.yaml.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview registry writes without persisting to MySQL.",
    ),
) -> None:
    config_path = config or DEFAULT_CONFIG_PATH
    app_config = load_config(config_path)
    service = ParseRegistryService(app_config)
    try:
        result = service.register_parse_report(
            report_path=report_path,
            dry_run=dry_run,
        )
    except ParseRegistryError as exc:
        console.print(f"ERROR: {exc.code}: {exc.message}")
        raise typer.Exit(code=1) from exc

    console.print(f"Dry run: {result.dry_run}")
    if result.run_uid:
        console.print(f"Run UID: {result.run_uid}")
    if result.status:
        console.print(f"Status: {result.status}")
    console.print(f"Results recorded: {result.results_recorded}")
    console.print(f"Artifacts recorded: {result.artifacts_recorded}")
    console.print(f"Errors: {len(result.errors)}")
    if result.registry_report_path is not None:
        console.print(f"Registry report: {result.registry_report_path}")


@app.command("list-parse-jobs")
def list_parse_jobs(
    config: Path | None = typer.Option(None, "--config"),
    limit: int = typer.Option(50, "--limit"),
    status: str | None = typer.Option(None, "--status"),
    parser_name: str | None = typer.Option(None, "--parser-name"),
) -> None:
    config_path = config or DEFAULT_CONFIG_PATH
    app_config = load_config(config_path)
    service = ParseRegistryService(app_config)
    runs = service.list_parse_runs(limit=limit, status=status, parser_name=parser_name)
    for run in runs:
        console.print(
            f"{run.run_uid}  {run.status}  {run.parser_name}  "
            f"parsed={run.parsed_count} skipped={run.skipped_count} failed={run.failed_count}"
        )
    console.print(f"Total: {len(runs)}")


@app.command("show-parse-job")
def show_parse_job(
    run_uid: str = typer.Option(..., "--run-uid"),
    config: Path | None = typer.Option(None, "--config"),
    include_results: bool = typer.Option(False, "--include-results"),
    include_artifacts: bool = typer.Option(False, "--include-artifacts"),
) -> None:
    config_path = config or DEFAULT_CONFIG_PATH
    app_config = load_config(config_path)
    service = ParseRegistryService(app_config)
    run = service.get_parse_run(run_uid)
    if run is None:
        console.print(f"ERROR: run not found: {run_uid}")
        raise typer.Exit(code=1)

    console.print(f"Run UID: {run.run_uid}")
    console.print(f"Status: {run.status}")
    console.print(f"Parser: {run.parser_name} ({run.parser_adapter_version})")
    console.print(f"Trigger: {run.trigger_type}")
    console.print(f"Report path: {run.report_path}")
    console.print(
        f"Summary: total={run.total_candidates} in_scope={run.in_scope_candidates} "
        f"parsed={run.parsed_count} empty={run.empty_count} "
        f"skipped={run.skipped_count} failed={run.failed_count}"
    )
    if include_results:
        results = service.list_parse_results(run_uid=run_uid, limit=500)
        console.print(f"Results ({len(results)}):")
        for result in results:
            console.print(
                f"  {result.content_uid}  {result.status}  sha256={result.sha256[:12]}..."
            )
    if include_artifacts:
        artifacts = service.list_parsed_artifacts(limit=500)
        run_artifacts = [a for a in artifacts if a.run_uid == run_uid]
        console.print(f"Artifacts ({len(run_artifacts)}):")
        for artifact in run_artifacts:
            console.print(
                f"  {artifact.artifact_type}  {artifact.content_uid or '(run)'}  "
                f"{artifact.artifact_path}"
            )


@app.command("list-parse-results")
def list_parse_results_cmd(
    config: Path | None = typer.Option(None, "--config"),
    run_uid: str | None = typer.Option(None, "--run-uid"),
    content_uid: str | None = typer.Option(None, "--content-uid"),
    sha256: str | None = typer.Option(None, "--sha256"),
    status: str | None = typer.Option(None, "--status"),
    limit: int = typer.Option(50, "--limit"),
) -> None:
    config_path = config or DEFAULT_CONFIG_PATH
    app_config = load_config(config_path)
    service = ParseRegistryService(app_config)
    results = service.list_parse_results(
        run_uid=run_uid,
        content_uid=content_uid,
        sha256=sha256,
        status=status,
        limit=limit,
    )
    for result in results:
        console.print(
            f"{result.run_uid}  {result.content_uid}  {result.status}  {result.sha256}"
        )
    console.print(f"Total: {len(results)}")


@app.command("list-parsed-artifacts")
def list_parsed_artifacts_cmd(
    config: Path | None = typer.Option(None, "--config"),
    content_uid: str | None = typer.Option(None, "--content-uid"),
    sha256: str | None = typer.Option(None, "--sha256"),
    artifact_type: str | None = typer.Option(None, "--artifact-type"),
    limit: int = typer.Option(50, "--limit"),
) -> None:
    config_path = config or DEFAULT_CONFIG_PATH
    app_config = load_config(config_path)
    service = ParseRegistryService(app_config)
    artifacts = service.list_parsed_artifacts(
        content_uid=content_uid,
        sha256=sha256,
        artifact_type=artifact_type,
        limit=limit,
    )
    for artifact in artifacts:
        console.print(
            f"{artifact.run_uid}  {artifact.artifact_type}  "
            f"{artifact.content_uid or '(run)'}  {artifact.status}"
        )
    console.print(f"Total: {len(artifacts)}")


@app.command("reconcile-parsed-artifacts")
def reconcile_parsed_artifacts_cmd(
    config: Path | None = typer.Option(None, "--config"),
    sha256: str | None = typer.Option(None, "--sha256"),
    content_uid: str | None = typer.Option(None, "--content-uid"),
    limit: int | None = typer.Option(None, "--limit"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    if not sha256 and not content_uid and limit is None:
        console.print("ERROR: must provide at least one of --sha256, --content-uid, or --limit")
        raise typer.Exit(code=1)
    if limit is not None and limit > PARSE_REGISTRY_MAX_LIMIT:
        console.print(f"ERROR: --limit must be <= {PARSE_REGISTRY_MAX_LIMIT}")
        raise typer.Exit(code=1)

    config_path = config or DEFAULT_CONFIG_PATH
    app_config = load_config(config_path)
    service = ParseRegistryService(app_config)
    try:
        result = service.reconcile_parsed_artifacts(
            sha256=sha256,
            content_uid=content_uid,
            limit=limit,
            dry_run=dry_run,
        )
    except ParseRegistryError as exc:
        console.print(f"ERROR: {exc.code}: {exc.message}")
        raise typer.Exit(code=1) from exc

    console.print(f"Dry run: {result.dry_run}")
    if result.run_uid:
        console.print(f"Run UID: {result.run_uid}")
    console.print(f"Manifests scanned: {result.manifests_scanned}")
    console.print(f"Results recorded: {result.results_recorded}")
    console.print(f"Artifacts recorded: {result.artifacts_recorded}")
    console.print(f"Errors: {len(result.errors)}")


@app.command("build-parse-queue")
def build_parse_queue() -> None:
    typer.echo("build-parse-queue placeholder")


@app.command("parse")
def parse(limit: int = 10) -> None:
    typer.echo(f"parse placeholder limit={limit}")


if __name__ == "__main__":
    app()
