import argparse
import os
import subprocess
from typing import Optional


def create_env_file(gemini_key: Optional[str], openai_key: Optional[str], filename: str = ".env") -> str:
    """Create an .env file with provided API keys."""
    lines = []
    if gemini_key:
        lines.append(f"GEMINI_API_KEY={gemini_key}")
    if openai_key:
        lines.append(f"OPENAI_API_KEY={openai_key}")
    content = "\n".join(lines) + ("\n" if lines else "")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    return filename


def run_command(command: list[str]) -> None:
    """Run a system command, forwarding output to the user."""
    subprocess.run(command, check=True)


def setup(args: argparse.Namespace) -> None:
    """Interactively create the .env file for API keys."""
    gemini = args.gemini or input("Enter Gemini API Key (or leave blank): ").strip() or None
    openai = args.openai or input("Enter OpenAI API Key (or leave blank): ").strip() or None
    create_env_file(gemini, openai)
    print("Created .env file")


def start(_: argparse.Namespace) -> None:
    """Start the MCP server via docker."""
    if not os.path.exists(".env"):
        print("No .env file found. Run 'python zen_cli.py setup' first.")
        return
    run_command(["bash", "setup-docker.sh"])


def stop(_: argparse.Namespace) -> None:
    """Stop the MCP server."""
    run_command(["docker", "compose", "down"])


def status(_: argparse.Namespace) -> None:
    """Show docker compose status."""
    run_command(["docker", "compose", "ps"])


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

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
