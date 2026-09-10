from cli.prompts._common import ask_choice, ask_text
from cli.session import ActorConfig


def prompt_actors() -> list[ActorConfig]:
    count = int(ask_text("Number of actors", "2"))
    actors = []
    for index in range(count):
        name = ask_text(f"Actor {index + 1} name", f"user_{chr(97 + index)}")
        auth = ask_choice("Auth type", [("Bearer token", "bearer"), ("Basic auth", "basic"), ("Cookie/session", "cookie"), ("Custom adapter", "custom")], "bearer")
        credential_env = ask_text("Credential environment-variable name (optional)", "") or None
        actors.append(ActorConfig(name, auth, credential_env))
    return actors
