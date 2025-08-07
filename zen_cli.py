import argparse
import subprocess
import shutil
from pathlib import Path
from typing import Optional


def create_env_file(gemini_key: Optional[str], openai_key: Optional[str], filename: Path | str = Path(".env")) -> Path:
    """Create an .env file with provided API keys."""
    filename = Path(filename)
    lines = []
    if gemini_key:
        lines.append(f"GEMINI_API_KEY={gemini_key}")
    if openai_key:
        lines.append(f"OPENAI_API_KEY={openai_key}")
    content = "\n".join(lines) + ("\n" if lines else "")
    filename.write_text(content, encoding="utf-8")
    return filename


def run_command(command: list[str]) -> None:
    """Run a system command, forwarding output to the user."""
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        print(f"Command not found: {command[0]}")
        raise SystemExit(1) from exc
    except subprocess.CalledProcessError as exc:
        print(f"Command failed: {' '.join(command)}")
        raise SystemExit(exc.returncode) from exc


def ensure_docker() -> bool:
    """Return True if Docker CLI is available and daemon responsive."""
    if shutil.which("docker") is None:
        print("Docker is not installed. Please install Docker Desktop.")
        return False
    try:
        subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except subprocess.CalledProcessError:
        print("Docker daemon is not running. Start Docker and try again.")
        return False
    return True


def setup(args: argparse.Namespace) -> None:
    """Interactively create the .env file for API keys."""
    gemini = args.gemini or input("Enter Gemini API Key (or leave blank): ").strip() or None
    openai = args.openai or input("Enter OpenAI API Key (or leave blank): ").strip() or None
    create_env_file(gemini, openai)
    print("Created .env file")


def start(_: argparse.Namespace) -> None:
    """Start the MCP server via docker."""
    if not Path(".env").exists():
        print("No .env file found. Run 'python zen_cli.py setup' first.")
        return
    if ensure_docker():
        run_command(["bash", "setup-docker.sh"])


def stop(_: argparse.Namespace) -> None:
    """Stop the MCP server."""
    if ensure_docker():
        run_command(["docker", "compose", "down"])


def status(_: argparse.Namespace) -> None:
    """Show docker compose status."""
    if ensure_docker():
        run_command(["docker", "compose", "ps"])


def menu(_: argparse.Namespace) -> None:
    """Interactive menu for beginners."""
    from types import SimpleNamespace

    options: dict[str, tuple[str, callable]] = {
        "1": ("Setup API keys", lambda: setup(SimpleNamespace(gemini=None, openai=None))),
        "2": ("Start services", lambda: start(SimpleNamespace())),
        "3": ("Stop services", lambda: stop(SimpleNamespace())),
        "4": ("Show status", lambda: status(SimpleNamespace())),
    }

    while True:
        print("\nZen MCP Menu")
        for key, (desc, _) in sorted(options.items()):
            print(f"{key}) {desc}")
        print("5) Exit")
        choice = input("Select an option: ").strip()
        if choice in {"5", "q", "quit", "exit"}:
            break
        action = options.get(choice)
        if action:
            action[1]()
        else:
            print("Invalid option")


def main() -> None:
    parser = argparse.ArgumentParser(description="Helper CLI for Zen MCP server")
    subparsers = parser.add_subparsers(dest="command")

    setup_parser = subparsers.add_parser("setup", help="Create .env with API keys")
    setup_parser.add_argument("--gemini", help="Gemini API Key")
    setup_parser.add_argument("--openai", help="OpenAI API Key")
    setup_parser.set_defaults(func=setup)

    start_parser = subparsers.add_parser("start", help="Start Docker services")
    start_parser.set_defaults(func=start)

    stop_parser = subparsers.add_parser("stop", help="Stop Docker services")
    stop_parser.set_defaults(func=stop)

    status_parser = subparsers.add_parser("status", help="Show Docker status")
    status_parser.set_defaults(func=status)

    menu_parser = subparsers.add_parser("menu", help="Interactive text menu")
    menu_parser.set_defaults(func=menu)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
