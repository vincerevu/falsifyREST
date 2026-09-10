from __future__ import annotations

import typer

try:
    import questionary
except ImportError:  # questionary is optional for minimal/headless installs.
    questionary = None


def ask_text(message: str, default: str | None = None, secret: bool = False) -> str:
    if questionary is not None:
        answer = questionary.password(message, default=default or "").ask() if secret else questionary.text(message, default=default or "").ask()
        if answer is not None:
            return answer
    return typer.prompt(message, default=default, hide_input=secret)


def ask_choice(message: str, choices: list[tuple[str, str]], default: str | None = None) -> str:
    if questionary is not None:
        answer = questionary.select(message, choices=[questionary.Choice(label, value=value) for label, value in choices], default=default).ask()
        if answer is not None:
            return answer
    numbered = "\n".join(f"{index + 1}. {label}" for index, (label, _) in enumerate(choices))
    selected = typer.prompt(f"{message}\n{numbered}", default=next((str(index + 1) for index, (_, value) in enumerate(choices) if value == default), "1"))
    return choices[int(selected) - 1][1]


def ask_confirm(message: str, default: bool = True) -> bool:
    if questionary is not None:
        answer = questionary.confirm(message, default=default).ask()
        if answer is not None:
            return answer
    return typer.confirm(message, default=default)
