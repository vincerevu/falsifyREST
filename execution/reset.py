import subprocess


def reset_docker_target(container: str) -> None:
    """Reset a local benchmark target; callers must explicitly opt into this action."""
    subprocess.run(["docker", "restart", container], check=True, capture_output=True, text=True)
