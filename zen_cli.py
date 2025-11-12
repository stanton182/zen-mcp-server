import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Confirm, Prompt
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None

# Initialize rich console if available
console = Console() if RICH_AVAILABLE else None


def print_message(message: str, style: str = ""):
    """Print message with optional styling if rich is available."""
    if RICH_AVAILABLE and console:
        console.print(message, style=style)
    else:
        print(message)


def print_error(message: str):
    """Print error message in red."""
    print_message(f"❌ {message}", "bold red")


def print_success(message: str):
    """Print success message in green."""
    print_message(f"✅ {message}", "bold green")


def print_info(message: str):
    """Print info message in blue."""
    print_message(f"ℹ️  {message}", "bold blue")


def print_warning(message: str):
    """Print warning message in yellow."""
    print_message(f"⚠️  {message}", "bold yellow")


def validate_api_key(key: str, provider: str) -> bool:
    """Validate API key format.

    Args:
        key: The API key to validate
        provider: The provider name ('gemini' or 'openai')

    Returns:
        True if key appears valid, False otherwise
    """
    if not key or len(key.strip()) < 20:
        return False

    # Basic format validation
    if provider == "gemini":
        # Gemini keys typically start with 'AIza'
        return key.startswith("AIza") and len(key) >= 39
    elif provider == "openai":
        # OpenAI keys typically start with 'sk-'
        return key.startswith("sk-") and len(key) >= 20

    return True


def create_env_file(gemini_key: Optional[str], openai_key: Optional[str], filename: Path | str = Path(".env")) -> Path:
    """Create an .env file with provided API keys.

    Args:
        gemini_key: Gemini API key (optional)
        openai_key: OpenAI API key (optional)
        filename: Path to .env file

    Returns:
        Path to created .env file

    Raises:
        ValueError: If no valid API keys provided
    """
    filename = Path(filename)
    lines = []

    # Validate and add Gemini key
    if gemini_key:
        gemini_key = gemini_key.strip()
        if validate_api_key(gemini_key, "gemini"):
            lines.append(f"GEMINI_API_KEY={gemini_key}")
            print_success(f"Gemini API key validated and added")
        else:
            print_warning(f"Gemini API key format appears invalid (expected to start with 'AIza')")
            if RICH_AVAILABLE:
                if not Confirm.ask("Add anyway?", default=False):
                    gemini_key = None
            else:
                response = input("Add anyway? (y/N): ").lower()
                if response != 'y':
                    gemini_key = None

            if gemini_key:
                lines.append(f"GEMINI_API_KEY={gemini_key}")

    # Validate and add OpenAI key
    if openai_key:
        openai_key = openai_key.strip()
        if validate_api_key(openai_key, "openai"):
            lines.append(f"OPENAI_API_KEY={openai_key}")
            print_success(f"OpenAI API key validated and added")
        else:
            print_warning(f"OpenAI API key format appears invalid (expected to start with 'sk-')")
            if RICH_AVAILABLE:
                if not Confirm.ask("Add anyway?", default=False):
                    openai_key = None
            else:
                response = input("Add anyway? (y/N): ").lower()
                if response != 'y':
                    openai_key = None

            if openai_key:
                lines.append(f"OPENAI_API_KEY={openai_key}")

    if not lines:
        raise ValueError("At least one valid API key is required")

    content = "\n".join(lines) + "\n"
    filename.write_text(content, encoding="utf-8")
    return filename


def run_command(command: list[str], show_output: bool = True) -> tuple[bool, str]:
    """Run a system command with better error handling.

    Args:
        command: Command and arguments to run
        show_output: Whether to show command output to user

    Returns:
        Tuple of (success: bool, output: str)
    """
    try:
        if show_output:
            result = subprocess.run(command, check=True, capture_output=False, text=True)
            return True, ""
        else:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            return True, result.stdout
    except FileNotFoundError as exc:
        print_error(f"Command not found: {command[0]}")
        print_info(f"Make sure {command[0]} is installed and in your PATH")
        return False, ""
    except subprocess.CalledProcessError as exc:
        print_error(f"Command failed: {' '.join(command)}")
        if exc.stderr:
            print_error(f"Error: {exc.stderr}")
        return False, ""


def ensure_docker() -> bool:
    """Return True if Docker CLI is available and daemon responsive."""
    # Check if docker command exists
    if shutil.which("docker") is None:
        print_error("Docker is not installed")
        print_info("Please install Docker Desktop:")
        print_info("  • macOS/Windows: https://www.docker.com/products/docker-desktop/")
        print_info("  • Linux: https://docs.docker.com/engine/install/")
        return False

    # Check if docker daemon is running
    try:
        subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=5)
        return True
    except subprocess.TimeoutExpired:
        print_error("Docker command timed out")
        print_info("Docker may be starting up. Please wait and try again.")
        return False
    except subprocess.CalledProcessError:
        print_error("Docker daemon is not running")
        print_info("Please start Docker Desktop and try again")
        return False


def get_config_info() -> dict:
    """Get current configuration information.

    Returns:
        Dictionary with configuration details
    """
    config = {
        "env_file_exists": Path(".env").exists(),
        "gemini_key_set": False,
        "openai_key_set": False,
        "docker_available": shutil.which("docker") is not None,
        "docker_running": False,
    }

    # Check API keys
    if config["env_file_exists"]:
        try:
            env_content = Path(".env").read_text()
            config["gemini_key_set"] = "GEMINI_API_KEY=" in env_content and len(env_content.split("GEMINI_API_KEY=")[1].split("\n")[0].strip()) > 0
            config["openai_key_set"] = "OPENAI_API_KEY=" in env_content and len(env_content.split("OPENAI_API_KEY=")[1].split("\n")[0].strip()) > 0
        except Exception:
            pass

    # Check docker status
    if config["docker_available"]:
        try:
            subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=5)
            config["docker_running"] = True
        except Exception:
            pass

    return config


def show_config(_: argparse.Namespace) -> None:
    """Display current configuration."""
    if RICH_AVAILABLE and console:
        console.print("\n[bold cyan]📋 Current Configuration[/bold cyan]\n")

        table = Table(box=box.ROUNDED)
        table.add_column("Setting", style="cyan")
        table.add_column("Status", style="white")

        config = get_config_info()

        # Environment file
        table.add_row(
            ".env file",
            "✅ Present" if config["env_file_exists"] else "❌ Missing"
        )

        # API Keys
        if config["env_file_exists"]:
            table.add_row(
                "Gemini API Key",
                "✅ Configured" if config["gemini_key_set"] else "❌ Not set"
            )
            table.add_row(
                "OpenAI API Key",
                "✅ Configured" if config["openai_key_set"] else "❌ Not set"
            )

        # Docker
        table.add_row(
            "Docker",
            "✅ Installed & Running" if config["docker_running"] else
            "⚠️  Installed but not running" if config["docker_available"] else
            "❌ Not installed"
        )

        console.print(table)
        console.print()

        if not config["env_file_exists"]:
            print_info("Run 'python zen_cli.py setup' to configure API keys")
    else:
        print("\n=== Current Configuration ===\n")
        config = get_config_info()
        print(f".env file: {'Present' if config['env_file_exists'] else 'Missing'}")
        if config["env_file_exists"]:
            print(f"Gemini API Key: {'Configured' if config['gemini_key_set'] else 'Not set'}")
            print(f"OpenAI API Key: {'Configured' if config['openai_key_set'] else 'Not set'}")
        print(f"Docker: {'Installed & Running' if config['docker_running'] else 'Installed but not running' if config['docker_available'] else 'Not installed'}")
        print()


def setup(args: argparse.Namespace) -> None:
    """Interactively create the .env file for API keys."""
    if RICH_AVAILABLE and console:
        console.print(Panel.fit(
            "[bold cyan]🔧 Zen MCP Server Setup[/bold cyan]\n\n"
            "At least one API key is required:\n"
            "  • Gemini: Get from https://aistudio.google.com/apikey\n"
            "  • OpenAI: Get from https://platform.openai.com/api-keys",
            border_style="cyan"
        ))
        print()

    # Check if .env exists and ask to overwrite
    if Path(".env").exists():
        print_warning(".env file already exists")
        if RICH_AVAILABLE:
            if not Confirm.ask("Do you want to overwrite it?", default=False):
                print_info("Setup cancelled")
                return
        else:
            response = input("Do you want to overwrite it? (y/N): ").lower()
            if response != 'y':
                print("Setup cancelled")
                return

    try:
        # Get API keys
        if args.gemini:
            gemini = args.gemini
        else:
            if RICH_AVAILABLE:
                gemini = Prompt.ask("Enter Gemini API Key (or leave blank)", default="")
            else:
                gemini = input("Enter Gemini API Key (or leave blank): ").strip()
            gemini = gemini or None

        if args.openai:
            openai = args.openai
        else:
            if RICH_AVAILABLE:
                openai = Prompt.ask("Enter OpenAI API Key (or leave blank)", default="")
            else:
                openai = input("Enter OpenAI API Key (or leave blank): ").strip()
            openai = openai or None

        if not gemini and not openai:
            print_error("At least one API key is required")
            return

        # Create .env file
        create_env_file(gemini, openai)
        print_success("Created .env file successfully")
        print()
        print_info("Next steps:")
        print_info("  1. Run 'python zen_cli.py start' to start the server")
        print_info("  2. Configure Claude Desktop with the MCP server")
        print_info("  3. See README.md for Claude Desktop configuration")

    except ValueError as e:
        print_error(str(e))
        return


def start(_: argparse.Namespace) -> None:
    """Start the MCP server via docker."""
    if not Path(".env").exists():
        print_error("No .env file found")
        print_info("Run 'python zen_cli.py setup' first to configure API keys")
        return

    if not ensure_docker():
        return

    print_info("Starting Zen MCP Server...")
    if RICH_AVAILABLE and console:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Starting services...", total=None)
            success, _ = run_command(["bash", "setup-docker.sh"], show_output=False)
            progress.update(task, completed=True)

        if success:
            print_success("Server started successfully")
            print_info("Check status with: python zen_cli.py status")
        else:
            print_error("Failed to start server")
    else:
        success, _ = run_command(["bash", "setup-docker.sh"])
        if success:
            print_success("Server started successfully")


def stop(_: argparse.Namespace) -> None:
    """Stop the MCP server."""
    if not ensure_docker():
        return

    print_info("Stopping Zen MCP Server...")
    success, _ = run_command(["docker", "compose", "down"])
    if success:
        print_success("Server stopped successfully")
    else:
        print_error("Failed to stop server")


def status(_: argparse.Namespace) -> None:
    """Show docker compose status."""
    if not ensure_docker():
        return

    print_info("Checking server status...\n")
    success, output = run_command(["docker", "compose", "ps"], show_output=False)

    if success and output:
        if RICH_AVAILABLE and console:
            console.print(output)
        else:
            print(output)
    else:
        run_command(["docker", "compose", "ps"], show_output=True)


def logs(args: argparse.Namespace) -> None:
    """View server logs."""
    if not ensure_docker():
        return

    follow = args.follow if hasattr(args, 'follow') else False

    print_info(f"{'Following' if follow else 'Showing'} server logs... (Press Ctrl+C to stop)\n")

    try:
        cmd = ["docker", "compose", "logs"]
        if follow:
            cmd.append("-f")
        cmd.extend(["--tail", "100"])

        subprocess.run(cmd)
    except KeyboardInterrupt:
        print_info("\nStopped viewing logs")


def health(_: argparse.Namespace) -> None:
    """Run health check on the server."""
    if RICH_AVAILABLE and console:
        console.print("\n[bold cyan]🏥 Health Check[/bold cyan]\n")
    else:
        print("\n=== Health Check ===\n")

    config = get_config_info()
    issues = []
    warnings = []
    containers = []  # Initialize containers list

    # Check configuration
    if not config["env_file_exists"]:
        issues.append("No .env file found")
    else:
        if not config["gemini_key_set"] and not config["openai_key_set"]:
            issues.append("No API keys configured")
        elif not config["gemini_key_set"]:
            warnings.append("Gemini API key not set (optional)")
        elif not config["openai_key_set"]:
            warnings.append("OpenAI API key not set (optional)")

    # Check Docker
    if not config["docker_available"]:
        issues.append("Docker is not installed")
    elif not config["docker_running"]:
        issues.append("Docker daemon is not running")

    # Check if containers are running
    if config["docker_running"]:
        try:
            result = subprocess.run(
                ["docker", "compose", "ps", "--format", "json"],
                capture_output=True,
                text=True,
                check=True
            )
            if result.stdout.strip():
                for line in result.stdout.strip().split('\n'):
                    try:
                        container = json.loads(line)
                        containers.append(container)
                    except json.JSONDecodeError:
                        pass

                if not containers:
                    warnings.append("No containers running")
                else:
                    for container in containers:
                        if container.get('State') != 'running':
                            issues.append(f"Container {container.get('Name', 'unknown')} is not running")
            else:
                warnings.append("No containers found")
        except Exception as e:
            warnings.append(f"Could not check container status: {e}")

    # Display results
    if RICH_AVAILABLE and console:
        table = Table(box=box.ROUNDED)
        table.add_column("Check", style="cyan")
        table.add_column("Result", style="white")

        table.add_row("Configuration", "✅ OK" if config["env_file_exists"] and (config["gemini_key_set"] or config["openai_key_set"]) else "❌ Issues found")
        table.add_row("Docker", "✅ OK" if config["docker_running"] else "❌ Issues found")

        console.print(table)
        console.print()

    if issues:
        print_error("Issues found:")
        for issue in issues:
            print_error(f"  • {issue}")
        print()

    if warnings:
        print_warning("Warnings:")
        for warning in warnings:
            print_warning(f"  • {warning}")
        print()

    if not issues and not warnings:
        print_success("All checks passed!")
    elif not issues:
        print_success("No critical issues found")

    # Suggestions
    if issues or warnings:
        print_info("Suggestions:")
        if not config["env_file_exists"] or (not config["gemini_key_set"] and not config["openai_key_set"]):
            print_info("  • Run 'python zen_cli.py setup' to configure API keys")
        if not config["docker_available"]:
            print_info("  • Install Docker Desktop from https://www.docker.com/products/docker-desktop/")
        if config["docker_available"] and not config["docker_running"]:
            print_info("  • Start Docker Desktop")
        if not containers:
            print_info("  • Run 'python zen_cli.py start' to start the server")


def menu(_: argparse.Namespace) -> None:
    """Interactive menu for beginners."""
    from types import SimpleNamespace

    options: dict[str, tuple[str, callable]] = {
        "1": ("Setup API keys", lambda: setup(SimpleNamespace(gemini=None, openai=None))),
        "2": ("Start services", lambda: start(SimpleNamespace())),
        "3": ("Stop services", lambda: stop(SimpleNamespace())),
        "4": ("Show status", lambda: status(SimpleNamespace())),
        "5": ("View configuration", lambda: show_config(SimpleNamespace())),
        "6": ("View logs", lambda: logs(SimpleNamespace(follow=False))),
        "7": ("Health check", lambda: health(SimpleNamespace())),
    }

    while True:
        if RICH_AVAILABLE and console:
            console.print("\n[bold cyan]╔══════════════════════════════╗[/bold cyan]")
            console.print("[bold cyan]║   🧘 Zen MCP Server Menu   ║[/bold cyan]")
            console.print("[bold cyan]╚══════════════════════════════╝[/bold cyan]\n")
            for key, (desc, _) in sorted(options.items()):
                console.print(f"  [cyan]{key}[/cyan]) {desc}")
            console.print(f"  [cyan]8[/cyan]) Exit\n")
            choice = Prompt.ask("Select an option", default="8").strip()
        else:
            print("\n" + "="*35)
            print("     Zen MCP Server Menu")
            print("="*35)
            for key, (desc, _) in sorted(options.items()):
                print(f"  {key}) {desc}")
            print(f"  8) Exit")
            choice = input("\nSelect an option: ").strip()

        if choice in {"8", "q", "quit", "exit"}:
            print_info("Goodbye!")
            break

        action = options.get(choice)
        if action:
            try:
                action[1]()
            except KeyboardInterrupt:
                print_info("\nOperation cancelled")
            except Exception as e:
                print_error(f"Error: {e}")
        else:
            print_error("Invalid option. Please try again.")


def main() -> None:
    """Main entry point for the CLI."""
    # Show welcome message if rich is available
    if RICH_AVAILABLE and console and len(sys.argv) == 1:
        console.print(Panel.fit(
            "[bold cyan]🧘 Zen MCP Server CLI[/bold cyan]\n\n"
            "Orchestrate multiple AI models for enhanced development",
            border_style="cyan"
        ))
        print()

    parser = argparse.ArgumentParser(
        description="Zen MCP Server - Multi-model AI orchestration for Claude",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python zen_cli.py menu          # Interactive menu
  python zen_cli.py setup         # Configure API keys
  python zen_cli.py start         # Start the server
  python zen_cli.py logs -f       # Follow logs in real-time
  python zen_cli.py health        # Run health check

For more information, visit: https://github.com/BeehiveInnovations/zen-mcp-server
        """
    )
    subparsers = parser.add_subparsers(dest="command")

    # Setup command
    setup_parser = subparsers.add_parser(
        "setup",
        help="Create .env with API keys",
        description="Configure API keys for Gemini and/or OpenAI"
    )
    setup_parser.add_argument("--gemini", help="Gemini API Key")
    setup_parser.add_argument("--openai", help="OpenAI API Key")
    setup_parser.set_defaults(func=setup)

    # Start command
    start_parser = subparsers.add_parser(
        "start",
        help="Start Docker services",
        description="Start the Zen MCP Server using Docker Compose"
    )
    start_parser.set_defaults(func=start)

    # Stop command
    stop_parser = subparsers.add_parser(
        "stop",
        help="Stop Docker services",
        description="Stop the Zen MCP Server"
    )
    stop_parser.set_defaults(func=stop)

    # Status command
    status_parser = subparsers.add_parser(
        "status",
        help="Show Docker status",
        description="Display status of Docker containers"
    )
    status_parser.set_defaults(func=status)

    # Config command
    config_parser = subparsers.add_parser(
        "config",
        help="View current configuration",
        description="Display current configuration and API key status"
    )
    config_parser.set_defaults(func=show_config)

    # Logs command
    logs_parser = subparsers.add_parser(
        "logs",
        help="View server logs",
        description="View logs from the Docker containers"
    )
    logs_parser.add_argument("-f", "--follow", action="store_true", help="Follow log output")
    logs_parser.set_defaults(func=logs)

    # Health command
    health_parser = subparsers.add_parser(
        "health",
        help="Run health check",
        description="Check server health and configuration"
    )
    health_parser.set_defaults(func=health)

    # Menu command
    menu_parser = subparsers.add_parser(
        "menu",
        help="Interactive text menu",
        description="Launch interactive menu for easy server management"
    )
    menu_parser.set_defaults(func=menu)

    args = parser.parse_args()

    # If no command specified, show menu if rich is available, otherwise show help
    if not hasattr(args, "func"):
        if RICH_AVAILABLE:
            from types import SimpleNamespace
            menu(SimpleNamespace())
        else:
            parser.print_help()
            print()
            print_info("Tip: Run 'python zen_cli.py menu' for an interactive menu")
    else:
        try:
            args.func(args)
        except KeyboardInterrupt:
            print_info("\nOperation cancelled")
            sys.exit(0)
        except Exception as e:
            print_error(f"Unexpected error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
