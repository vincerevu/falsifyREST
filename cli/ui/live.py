from contextlib import contextmanager

from rich.console import Console
from rich.status import Status


@contextmanager
def live_status(message: str):
    console = Console()
    with Status(message, console=console, spinner="dots") as status:
        yield status
