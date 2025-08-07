# Zen MCP Beginner CLI

This README explains how to use `zen_cli.py` to configure and manage the Zen MCP server with a single interface.

## Setup
1. Ensure Python 3.11+ is installed.
2. Clone this repository and enter the directory.
3. Create the `.env` file with your API keys:
   ```bash
   python zen_cli.py setup --gemini <GEMINI_KEY> --openai <OPENAI_KEY>
   ```
   Either key may be omitted.

## Managing Services
- **Start containers**
  ```bash
  python zen_cli.py start
  ```
- **Check status**
  ```bash
  python zen_cli.py status
  ```
- **Stop containers**
  ```bash
  python zen_cli.py stop
  ```

The CLI checks for Docker and shows a friendly warning if it isn't installed or running.

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
