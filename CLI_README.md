# Zen MCP CLI - User Guide

This guide explains how to use `zen_cli.py` to configure and manage the Zen MCP server with an intuitive, user-friendly interface.

## Features

- 🎨 **Beautiful CLI** - Color-coded output and formatted tables (when `rich` library is installed)
- ✅ **API Key Validation** - Validates API key format before saving
- 📋 **Configuration Viewer** - View current settings without exposing full API keys
- 📊 **Health Checks** - Comprehensive system health diagnostics
- 📝 **Log Viewer** - Easy access to server logs with follow mode
- 🎯 **Interactive Menu** - User-friendly menu for all operations
- 💡 **Smart Error Messages** - Helpful suggestions when things go wrong

## Installation

1. Ensure Python 3.11+ is installed
2. Clone this repository and enter the directory
3. Install dependencies (optional, for enhanced CLI experience):
   ```bash
   pip install rich>=13.0.0
   ```

## Quick Start

### Interactive Menu (Recommended)
Simply run without arguments to launch the interactive menu:
```bash
python zen_cli.py
```
or explicitly:
```bash
python zen_cli.py menu
```

### Command-Line Interface

#### Setup - Configure API Keys
Create the `.env` file with your API keys:
```bash
# Interactive setup (prompts for keys)
python zen_cli.py setup

# Or provide keys directly
python zen_cli.py setup --gemini <GEMINI_KEY> --openai <OPENAI_KEY>
```
**Note:** At least one API key is required. The CLI validates key format and asks for confirmation if format looks incorrect.

#### View Configuration
Check your current configuration without exposing full API keys:
```bash
python zen_cli.py config
```

#### Start Services
Start the MCP server using Docker Compose:
```bash
python zen_cli.py start
```

#### Check Status
View the status of Docker containers:
```bash
python zen_cli.py status
```

#### View Logs
View server logs:
```bash
# Show last 100 log lines
python zen_cli.py logs

# Follow logs in real-time
python zen_cli.py logs -f
```

#### Health Check
Run comprehensive health diagnostics:
```bash
python zen_cli.py health
```
This checks:
- Configuration file exists
- API keys are set
- Docker is installed and running
- Containers are healthy

#### Stop Services
Stop the MCP server:
```bash
python zen_cli.py stop
```

## Command Reference

| Command | Description | Options |
|---------|-------------|---------|
| `menu` | Launch interactive menu | None |
| `setup` | Configure API keys | `--gemini`, `--openai` |
| `config` | View current configuration | None |
| `start` | Start Docker services | None |
| `stop` | Stop Docker services | None |
| `status` | Show container status | None |
| `logs` | View server logs | `-f, --follow` |
| `health` | Run health check | None |

## Examples

### First-time Setup
```bash
# Run interactive setup
python zen_cli.py setup

# Or provide keys directly
python zen_cli.py setup --gemini AIza... --openai sk-...

# Start the server
python zen_cli.py start

# Check that everything is working
python zen_cli.py health
```

### Daily Operations
```bash
# Quick status check
python zen_cli.py status

# View logs to troubleshoot
python zen_cli.py logs

# Follow logs in real-time
python zen_cli.py logs -f

# Stop server when done
python zen_cli.py stop
```

### Troubleshooting
```bash
# Run health check to identify issues
python zen_cli.py health

# View configuration
python zen_cli.py config

# Check detailed logs
python zen_cli.py logs
```

## Features Detail

### API Key Validation
When setting up, the CLI validates:
- **Gemini keys**: Should start with `AIza` and be at least 39 characters
- **OpenAI keys**: Should start with `sk-` and be at least 20 characters

If validation fails, you'll be asked to confirm before proceeding.

### Enhanced Error Messages
The CLI provides helpful suggestions when errors occur:
- Missing `.env` file → Suggests running `setup`
- Docker not installed → Provides installation links
- Docker not running → Suggests starting Docker Desktop
- No containers running → Suggests running `start`

### Color-Coded Output
When the `rich` library is installed, you'll see:
- ✅ Green for success messages
- ❌ Red for errors
- ⚠️  Yellow for warnings
- ℹ️  Blue for informational messages
- Beautiful tables and panels for structured data

### Progress Indicators
Operations show progress with spinners when `rich` is available, providing better feedback during long-running tasks.

## Docker Requirements

The CLI automatically checks for:
1. Docker CLI installation
2. Docker daemon running
3. Docker Compose support

If any requirement is missing, you'll receive helpful error messages with links to installation resources.

## Testing
Run the Python unit tests to verify core behaviour:
```bash
python -m pytest tests/ -v
```

For full simulation against a running Docker stack:
```bash
python communication_simulator_test.py --tests basic_conversation
```
This requires Docker and at least one valid API key.

## Need Help?

Run any command with `-h` or `--help` for detailed usage:
```bash
python zen_cli.py --help
python zen_cli.py setup --help
python zen_cli.py logs --help
```

Or use the interactive menu for a guided experience:
```bash
python zen_cli.py menu
```
