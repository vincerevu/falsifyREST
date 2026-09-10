"""Portable Markdown report for a completed falsifyREST run."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from cli.session import RunConfig


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def write_markdown_report(config: RunConfig, result) -> Path:
    """Write human-readable findings while retaining JSON as the machine artifact."""
    output = Path(config.output_dir) / "run-report.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# falsifyREST run report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        "## Configuration",
        "",
        "| Setting | Value |",
        "| --- | --- |",
        f"| Target | {_cell(config.target.base_url)} |",
        f"| OpenAPI | `{_cell(result.openapi_path)}` |",
        f"| Explorer | {_cell(config.exploration.provider)} |",
        f"| Testing mode | {_cell(config.llm.mode)} |",
        f"| Actors | {_cell(', '.join(actor.name for actor in config.actors) or 'none')} |",
        f"| Search budget | {config.budget} |",
        "",
        "## Analysis",
        "",
        f"- OpenAPI operations: **{result.operation_count}**",
    ]
    if result.analysis:
        report = result.analysis["report"]
        lines.extend([
            f"- Trace coverage: **{report['traced_operation_count']}/{report['operation_count']}** operations",
            f"- Observations: **{report['observation_count']}**",
            f"- Inferred hypotheses: **{result.analysis['hypotheses']}**",
        ])
        synthesis = result.analysis.get("recipe_synthesis")
        if synthesis:
            lines.extend([f"- LLM recipes proposed: **{len(synthesis['proposed'])}**",
                          f"- LLM recipes accepted structurally: **{len(synthesis['accepted'])}**",
                          f"- LLM recipes rejected structurally: **{len(synthesis['rejected'])}**"])
            if synthesis["rejected"]:
                lines.extend(["", "### Structurally rejected LLM recipes", "", "| Recipe | Reason |", "| --- | --- |"])
                lines.extend(f"| `{_cell(name)}` | {_cell(reason)} |" for name, reason in synthesis["rejected"].items())
    if result.live:
        lines.extend([
            "",
            "## Live validation",
            "",
            f"- Candidate seeds: **{result.live['seeds']}**",
            f"- Executed experiments: **{result.live['experiments']}**",
            f"- Outcomes: **{result.live['outcomes']}**",
            f"- Machine-readable artifact: `{_cell(result.live['artifact'])}`",
        ])
        coverage = result.live.get("recipe_coverage")
        if coverage is not None:
            lines.append(f"- Provisioned recipes: **{', '.join(coverage['provisioned']) or 'none'}**")
            lines.append(f"- Repair attempts: **{len(coverage.get('repairs', []))}**")
            if coverage["skipped"]:
                lines.extend(["", "### Skipped recipes", "", "| Recipe | Reason |", "| --- | --- |"])
                lines.extend(f"| `{_cell(name)}` | {_cell(reason)} |" for name, reason in coverage["skipped"].items())
    findings = result.findings or []
    lines.extend(["", "## Security-relevant witnesses", ""])
    if not findings:
        lines.append("No security-relevant witness was confirmed within the live-search budget.")
    else:
        lines.extend([
            "| # | Endpoint | Actor switch | HTTP | Hypothesis | Observed effect |",
            "| ---: | --- | --- | ---: | --- | --- |",
        ])
        for index, finding in enumerate(findings, start=1):
            lines.append(
                f"| {index} | {_cell(finding['endpoint'])} | {_cell(finding['control_actor'])} → "
                f"{_cell(finding['treatment_actor'])} | {_cell(finding['status'])} | "
                f"`{_cell(finding['hypothesis'])}` | {_cell(finding['effect'])} |"
            )
    lines.extend(["", "## Interpretation", ""])
    if findings:
        lines.append("Each row is a validated witness from the configured adapter and oracle. Review the linked JSON artifact for replay metadata before treating it as a production finding.")
    else:
        lines.append("This run did not confirm a witness; this is not evidence that the target is free of vulnerabilities.")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output
