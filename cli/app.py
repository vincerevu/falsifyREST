from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from cli.runner import run
from cli.session import ExplorationConfig, LLMConfig, RunConfig, TargetConfig, load_config, save_config
from cli.ui.tables import config_table, findings_table, result_table
from cli.wizard import build_run_config

app = typer.Typer(no_args_is_help=False, add_completion=False, help="Stateful REST security testing.")
console = Console()


def _print_result(result) -> None:
    console.print(result_table(result))
    if result.findings:
        console.print(findings_table(result.findings))
    elif result.live:
        console.print("[yellow]No security-relevant witness was confirmed during the live search budget.[/yellow]")


def _apply_overrides(config: RunConfig, target: str | None, openapi: str | None, mode: str | None, budget: int | None) -> RunConfig:
    if target:
        config.target.base_url = target.rstrip("/")
    if openapi:
        config.target.openapi = openapi
        config.target.openapi_source = "url" if openapi.startswith(("http://", "https://")) else "file"
    if mode:
        config.llm.mode = mode
        if mode == "rule-only":
            config.llm.provider = "disabled"
    if budget is not None:
        config.budget = budget
    return config


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Launch the interactive configuration wizard when no subcommand is used."""
    if ctx.invoked_subcommand is None:
        config = build_run_config()
        console.print(config_table(config))
        if typer.confirm("Start testing?", default=True):
            result = run(config)
            _print_result(result)


@app.command("run")
def run_command(
    config: Path | None = typer.Option(None, "--config", "-c"),
    no_interactive: bool = typer.Option(False, "--no-interactive"),
    target: str | None = typer.Option(None, "--target"),
    openapi: str | None = typer.Option(None, "--openapi"),
    mode: str | None = typer.Option(None, "--mode", help="rule-only, llm-prior, or compare"),
    budget: int | None = typer.Option(None, "--budget"),
    trace: Path | None = typer.Option(None, "--trace", help="Existing normalized JSONL trace"),
    live: bool = typer.Option(False, "--live", help="Execute live counterexamples through the configured TargetAdapter"),
) -> None:
    """Run a saved profile/config or explicit non-interactive configuration."""
    if config:
        run_config = load_config(config)
    elif no_interactive:
        if not target or not openapi:
            raise typer.BadParameter("--target and --openapi are required with --no-interactive without --config")
        run_config = RunConfig(TargetConfig(target, openapi, "url" if openapi.startswith(("http://", "https://")) else "file"))
    else:
        run_config = build_run_config()
    _apply_overrides(run_config, target, openapi, mode, budget)
    if trace:
        run_config.exploration = ExplorationConfig("trace", str(trace))
    if live:
        run_config.live.enabled = True
    console.print(config_table(run_config))
    result = run(run_config)
    _print_result(result)


@app.command()
def profile(path: Path, name: str) -> None:
    """Save a config file under the supplied profile name."""
    config = load_config(path)
    config.profile_name = name
    destination = save_config(config, Path.home() / ".falsifyrest" / "profiles" / f"{name}.yaml")
    console.print(f"Saved profile to {destination}")


if __name__ == "__main__":
    app()
