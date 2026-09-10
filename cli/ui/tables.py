from rich.table import Table

from cli.session import RunConfig


def config_table(config: RunConfig) -> Table:
    table = Table(title="Run Configuration", show_header=False)
    table.add_column("Setting", style="bold cyan")
    table.add_column("Value")
    table.add_row("Target", config.target.base_url)
    table.add_row("OpenAPI", config.target.openapi)
    table.add_row("Explorer", config.exploration.provider)
    table.add_row("Mode", config.llm.mode)
    table.add_row("LLM", f"{config.llm.provider}/{config.llm.model}" if config.llm.model else config.llm.provider)
    table.add_row("Actors", ", ".join(actor.name for actor in config.actors) or "none")
    table.add_row("Budget", str(config.budget))
    return table


def result_table(result) -> Table:
    """Compact completion status without printing internal Python/JSON structures."""
    table = Table(title="falsifyREST result", show_header=False)
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value")
    table.add_row("OpenAPI operations", str(result.operation_count))
    if result.analysis:
        report = result.analysis["report"]
        table.add_row("Trace coverage", f"{report['traced_operation_count']}/{report['operation_count']} operations")
        table.add_row("Hypotheses", str(result.analysis["hypotheses"]))
        synthesis = result.analysis.get("recipe_synthesis")
        if synthesis:
            table.add_row("LLM recipes", f"{len(synthesis['proposed'])} proposed, {len(synthesis['accepted'])} accepted, {len(synthesis['rejected'])} rejected")
    if result.live:
        table.add_row("Live experiments", str(result.live["experiments"]))
        table.add_row("Live outcomes", str(result.live["outcomes"]))
        table.add_row("Security witnesses", str(len(result.findings or [])))
        if result.live.get("recipe_coverage") is not None:
            coverage = result.live["recipe_coverage"]
            table.add_row("Recipe coverage", f"{len(coverage['provisioned'])} provisioned, {len(coverage['skipped'])} skipped")
        table.add_row("Artifact", result.live["artifact"])
    if result.report_path:
        table.add_row("Markdown report", result.report_path)
    return table


def findings_table(findings: list[dict]) -> Table:
    table = Table(title="Security-relevant witnesses", show_lines=True)
    table.add_column("#", style="bold red", width=3)
    table.add_column("Endpoint", style="cyan")
    table.add_column("Actor switch")
    table.add_column("HTTP", justify="right")
    table.add_column("Hypothesis")
    table.add_column("Observed effect")
    for index, finding in enumerate(findings, start=1):
        table.add_row(
            str(index), finding["endpoint"], f"{finding['control_actor']} → {finding['treatment_actor']}",
            str(finding["status"]), finding["hypothesis"], finding["effect"],
        )
    return table
