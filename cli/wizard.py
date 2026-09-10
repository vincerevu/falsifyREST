from rich.console import Console
from rich.panel import Panel

from cli.prompts._common import ask_choice, ask_confirm, ask_text
from cli.prompts.auth import prompt_actors
from cli.prompts.llm import prompt_llm
from cli.prompts.run import prompt_run
from cli.prompts.target import prompt_target
from cli.session import RunConfig, list_profiles, load_config, profiles_dir, save_config
from cli.ui.tables import config_table


def build_run_config() -> RunConfig:
    """Collect input only; execution belongs to cli.runner."""
    console = Console()
    console.print(Panel("[bold]Stateful REST Security Testing[/bold]", title="falsifyREST"))
    profiles = list_profiles()
    source = ask_choice("Configuration", [("New target", "new"), *[(path.stem, str(path)) for path in profiles]], "new")
    if source != "new":
        return load_config(source)
    target = prompt_target()
    llm = prompt_llm()
    exploration, budget, output = prompt_run()
    actors = prompt_actors() if ask_confirm("Do you need authenticated actors?", True) else []
    config = RunConfig(target, exploration, llm, actors, budget, output)
    console.print(config_table(config))
    if ask_confirm("Save this configuration as a profile?", False):
        name = ask_text("Profile name")
        config.profile_name = name
        save_config(config, profiles_dir() / f"{name}.yaml")
    return config
