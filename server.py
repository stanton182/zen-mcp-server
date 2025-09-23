"""
Zen MCP Server - Main server implementation

This module implements the core MCP (Model Context Protocol) server that provides
AI-powered tools for code analysis, review, and assistance using multiple AI models.

The server follows the MCP specification to expose various AI tools as callable functions
that can be used by MCP clients (like Claude). Each tool provides specialized functionality
such as code review, debugging, deep thinking, and general chat capabilities.

Key Components:
- MCP Server: Handles protocol communication and tool discovery
- Tool Registry: Maps tool names to their implementations
- Request Handler: Processes incoming tool calls and returns formatted responses
- Configuration: Manages API keys and model settings

The server runs on stdio (standard input/output) and communicates using JSON-RPC messages
as defined by the MCP protocol.
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import ServerCapabilities, TextContent, Tool, ToolsCapability

from config import DEFAULT_MODEL, MAX_CONTEXT_TOKENS, __author__, __updated__, __version__
from tools import (
    AnalyzeTool,
    ChatTool,
    CodeReviewTool,
    DebugIssueTool,
    Precommit,
    ThinkDeepTool,
)
from tools.models import ToolOutput

# Configure logging for server operations
# Can be controlled via LOG_LEVEL environment variable (DEBUG, INFO, WARNING, ERROR)
log_level = os.getenv("LOG_LEVEL", "INFO").upper()

# Record the precise start time of the server process for diagnostics and uptime reporting
SERVER_START_TIME = datetime.now(timezone.utc)

# Create timezone-aware formatter


class LocalTimeFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        """Override to use local timezone instead of UTC"""
        ct = self.converter(record.created)
        if datefmt:
            s = time.strftime(datefmt, ct)
        else:
            t = time.strftime("%Y-%m-%d %H:%M:%S", ct)
            s = f"{t},{record.msecs:03.0f}"
        return s


# Configure both console and file logging
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format=log_format,
    force=True,  # Force reconfiguration if already configured
    stream=sys.stderr,  # Use stderr to avoid interfering with MCP stdin/stdout protocol
)

# Apply local time formatter to root logger
for handler in logging.getLogger().handlers:
    handler.setFormatter(LocalTimeFormatter(log_format))

# Add file handler for Docker log monitoring
try:
    file_handler = logging.FileHandler("/tmp/mcp_server.log")
    file_handler.setLevel(getattr(logging, log_level, logging.INFO))
    file_handler.setFormatter(LocalTimeFormatter(log_format))
    logging.getLogger().addHandler(file_handler)

    # Create a special logger for MCP activity tracking
    mcp_logger = logging.getLogger("mcp_activity")
    mcp_file_handler = logging.FileHandler("/tmp/mcp_activity.log")
    mcp_file_handler.setLevel(logging.INFO)
    mcp_file_handler.setFormatter(LocalTimeFormatter("%(asctime)s - %(message)s"))
    mcp_logger.addHandler(mcp_file_handler)
    mcp_logger.setLevel(logging.INFO)

except Exception as e:
    print(f"Warning: Could not set up file logging: {e}", file=sys.stderr)

logger = logging.getLogger(__name__)

# Create the MCP server instance with a unique name identifier
# This name is used by MCP clients to identify and connect to this specific server
server: Server = Server("zen-server")

# Initialize the tool registry with all available AI-powered tools
# Each tool provides specialized functionality for different development tasks
# Tools are instantiated once and reused across requests (stateless design)
TOOLS = {
    "thinkdeep": ThinkDeepTool(),  # Extended reasoning for complex problems
    "codereview": CodeReviewTool(),  # Comprehensive code review and quality analysis
    "debug": DebugIssueTool(),  # Root cause analysis and debugging assistance
    "analyze": AnalyzeTool(),  # General-purpose file and code analysis
    "chat": ChatTool(),  # Interactive development chat and brainstorming
    "precommit": Precommit(),  # Pre-commit validation of git changes
}


def configure_providers():
    """
    Configure and validate AI providers based on available API keys.

    This function checks for API keys and registers the appropriate providers.
    At least one valid API key (Gemini or OpenAI) is required.

    Raises:
        ValueError: If no valid API keys are found
    """
    from providers import ModelProviderRegistry
    from providers.base import ProviderType
    from providers.gemini import GeminiModelProvider
    from providers.openai import OpenAIModelProvider

    valid_providers = []

    # Check for Gemini API key
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and gemini_key != "your_gemini_api_key_here":
        ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
        valid_providers.append("Gemini")
        logger.info("Gemini API key found - Gemini models available")

    # Check for OpenAI API key
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and openai_key != "your_openai_api_key_here":
        ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)
        valid_providers.append("OpenAI (o3)")
        logger.info("OpenAI API key found - o3 model available")

    # Require at least one valid provider
    if not valid_providers:
        raise ValueError(
            "At least one API key is required. Please set either:\n"
            "- GEMINI_API_KEY for Gemini models\n"
            "- OPENAI_API_KEY for OpenAI o3 model"
        )

    logger.info(f"Available providers: {', '.join(valid_providers)}")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """
    List all available tools with their descriptions and input schemas.

    This handler is called by MCP clients during initialization to discover
    what tools are available. Each tool provides:
    - name: Unique identifier for the tool
    - description: Detailed explanation of what the tool does
    - inputSchema: JSON Schema defining the expected parameters

    Returns:
        List of Tool objects representing all available tools
    """
    logger.debug("MCP client requested tool list")
    tools = []

    # Add all registered AI-powered tools from the TOOLS registry
    for tool in TOOLS.values():
        tools.append(
            Tool(
                name=tool.name,
                description=tool.description,
                inputSchema=tool.get_input_schema(),
            )
        )

    # Add utility tools that provide server metadata and configuration info
    # These tools don't require AI processing but are useful for clients
    tools.extend(
        [
            Tool(
                name="get_version",
                description=(
                    "VERSION & CONFIGURATION - Get server version, configuration details, "
                    "and list of available tools. Useful for debugging and understanding capabilities."
                ),
                inputSchema={"type": "object", "properties": {}},
            ),
        ]
    )

    logger.debug(f"Returning {len(tools)} tools to MCP client")
    return tools


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """
    Handle incoming tool execution requests from MCP clients.

    This is the main request dispatcher that routes tool calls to their
    appropriate handlers. It supports both AI-powered tools (from TOOLS registry)
    and utility tools (implemented as static functions).

    Thread Context Reconstruction:
    If the request contains a continuation_id, this function reconstructs
    the conversation history and injects it into the tool's context.

    Args:
        name: The name of the tool to execute
        arguments: Dictionary of arguments to pass to the tool

    Returns:
        List of TextContent objects containing the tool's response
    """
    logger.info(f"MCP tool call: {name}")
    logger.debug(f"MCP tool arguments: {list(arguments.keys())}")

    # Log to activity file for monitoring
    try:
        mcp_activity_logger = logging.getLogger("mcp_activity")
        mcp_activity_logger.info(f"TOOL_CALL: {name} with {len(arguments)} arguments")
    except Exception:
        pass

    # Handle thread context reconstruction if continuation_id is present
    if "continuation_id" in arguments and arguments["continuation_id"]:
        continuation_id = arguments["continuation_id"]
        logger.debug(f"Resuming conversation thread: {continuation_id}")
        logger.debug(
            f"[CONVERSATION_DEBUG] Tool '{name}' resuming thread {continuation_id} with {len(arguments)} arguments"
        )
        logger.debug(f"[CONVERSATION_DEBUG] Original arguments keys: {list(arguments.keys())}")

        # Log to activity file for monitoring
        try:
            mcp_activity_logger = logging.getLogger("mcp_activity")
            mcp_activity_logger.info(f"CONVERSATION_RESUME: {name} resuming thread {continuation_id}")
        except Exception:
            pass

        arguments = await reconstruct_thread_context(arguments)
        logger.debug(f"[CONVERSATION_DEBUG] After thread reconstruction, arguments keys: {list(arguments.keys())}")
        if "_remaining_tokens" in arguments:
            logger.debug(f"[CONVERSATION_DEBUG] Remaining token budget: {arguments['_remaining_tokens']:,}")

    # Route to AI-powered tools that require Gemini API calls
    if name in TOOLS:
        logger.info(f"Executing tool '{name}' with {len(arguments)} parameter(s)")
        tool = TOOLS[name]
        result = await tool.execute(arguments)
        logger.info(f"Tool '{name}' execution completed")

        # Log completion to activity file
        try:
            mcp_activity_logger = logging.getLogger("mcp_activity")
            mcp_activity_logger.info(f"TOOL_COMPLETED: {name}")
        except Exception:
            pass
        return result

    # Route to utility tools that provide server information
    elif name == "get_version":
        logger.info(f"Executing utility tool '{name}'")
        result = await handle_get_version()
        logger.info(f"Utility tool '{name}' execution completed")
        return result

    # Handle unknown tool requests gracefully
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


def get_follow_up_instructions(current_turn_count: int, max_turns: int = None) -> str:
    """
    Generate dynamic follow-up instructions based on conversation turn count.

    Args:
        current_turn_count: Current number of turns in the conversation
        max_turns: Maximum allowed turns before conversation ends (defaults to MAX_CONVERSATION_TURNS)

    Returns:
        Follow-up instructions to append to the tool prompt
    """
    if max_turns is None:
        from utils.conversation_memory import MAX_CONVERSATION_TURNS

        max_turns = MAX_CONVERSATION_TURNS

    if current_turn_count >= max_turns - 1:
        # We're at or approaching the turn limit - no more follow-ups
        return """
IMPORTANT: This is approaching the final exchange in this conversation thread.
Do NOT include any follow-up questions in your response. Provide your complete
final analysis and recommendations."""
    else:
        # Normal follow-up instructions
        remaining_turns = max_turns - current_turn_count - 1
        return f"""

CONVERSATION CONTINUATION: You can continue this discussion with Claude! ({remaining_turns} exchanges remaining)

Feel free to ask clarifying questions or suggest areas for deeper exploration naturally within your response.
If something needs clarification or you'd benefit from additional context, simply mention it conversationally.

IMPORTANT: When you suggest follow-ups or ask questions, you MUST explicitly instruct Claude to use the continuation_id
to respond. Use clear, direct language based on urgency:

For optional follow-ups: "Please continue this conversation using the continuation_id from this response if you'd like to explore this further."

For needed responses: "Please respond using the continuation_id from this response - your input is needed to proceed."

For essential/critical responses: "RESPONSE REQUIRED: Please immediately continue using the continuation_id from this response. Cannot proceed without your clarification/input."

This ensures Claude knows both HOW to maintain the conversation thread AND whether a response is optional, needed, or essential.

The tool will automatically provide a continuation_id in the structured response that Claude can use in subsequent
tool calls to maintain full conversation context across multiple exchanges.

Remember: Only suggest follow-ups when they would genuinely add value to the discussion, and always instruct Claude to use the continuation_id when you do."""


async def reconstruct_thread_context(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Reconstruct conversation context for thread continuation.

    This function loads the conversation history from Redis and integrates it
    into the request arguments to provide full context to the tool.

    Args:
        arguments: Original request arguments containing continuation_id

    Returns:
        Modified arguments with conversation history injected
    """
    from utils.conversation_memory import add_turn, build_conversation_history, get_thread

    continuation_id = arguments["continuation_id"]

    # Get thread context from Redis
    logger.debug(f"[CONVERSATION_DEBUG] Looking up thread {continuation_id} in Redis")
    context = get_thread(continuation_id)
    if not context:
        logger.warning(f"Thread not found: {continuation_id}")
        logger.debug(f"[CONVERSATION_DEBUG] Thread {continuation_id} not found in Redis or expired")

        # Log to activity file for monitoring
        try:
            mcp_activity_logger = logging.getLogger("mcp_activity")
            mcp_activity_logger.info(f"CONVERSATION_ERROR: Thread {continuation_id} not found or expired")
        except Exception:
            pass

        # Return error asking Claude to restart conversation with full context
        raise ValueError(
            f"Conversation thread '{continuation_id}' was not found or has expired. "
            f"This may happen if the conversation was created more than 1 hour ago or if there was an issue with Redis storage. "
            f"Please restart the conversation by providing your full question/prompt without the continuation_id parameter. "
            f"This will create a new conversation thread that can continue with follow-up exchanges."
        )

    # Add user's new input to the conversation
    user_prompt = arguments.get("prompt", "")
    if user_prompt:
        # Capture files referenced in this turn
        user_files = arguments.get("files", [])
        logger.debug(f"[CONVERSATION_DEBUG] Adding user turn to thread {continuation_id}")
        logger.debug(f"[CONVERSATION_DEBUG] User prompt length: {len(user_prompt)} chars")
        logger.debug(f"[CONVERSATION_DEBUG] User files: {user_files}")
        success = add_turn(continuation_id, "user", user_prompt, files=user_files)
        if not success:
            logger.warning(f"Failed to add user turn to thread {continuation_id}")
            logger.debug("[CONVERSATION_DEBUG] Failed to add user turn - thread may be at turn limit or expired")
        else:
            logger.debug(f"[CONVERSATION_DEBUG] Successfully added user turn to thread {continuation_id}")

    # Create model context early to use for history building
    from utils.model_context import ModelContext

    model_context = ModelContext.from_arguments(arguments)

    # Build conversation history with model-specific limits
    logger.debug(f"[CONVERSATION_DEBUG] Building conversation history for thread {continuation_id}")
    logger.debug(f"[CONVERSATION_DEBUG] Thread has {len(context.turns)} turns, tool: {context.tool_name}")
    logger.debug(f"[CONVERSATION_DEBUG] Using model: {model_context.model_name}")
    conversation_history, conversation_tokens = build_conversation_history(context, model_context)
    logger.debug(f"[CONVERSATION_DEBUG] Conversation history built: {conversation_tokens:,} tokens")
    logger.debug(f"[CONVERSATION_DEBUG] Conversation history length: {len(conversation_history)} chars")

    # Add dynamic follow-up instructions based on turn count
    follow_up_instructions = get_follow_up_instructions(len(context.turns))
    logger.debug(f"[CONVERSATION_DEBUG] Follow-up instructions added for turn {len(context.turns)}")

    # All tools now use standardized 'prompt' field
    original_prompt = arguments.get("prompt", "")
    logger.debug("[CONVERSATION_DEBUG] Extracting user input from 'prompt' field")
    logger.debug(f"[CONVERSATION_DEBUG] User input length: {len(original_prompt)} chars")

    # Merge original context with new prompt and follow-up instructions
    if conversation_history:
        enhanced_prompt = (
            f"{conversation_history}\n\n=== NEW USER INPUT ===\n{original_prompt}\n\n{follow_up_instructions}"
        )
    else:
        enhanced_prompt = f"{original_prompt}\n\n{follow_up_instructions}"

    # Update arguments with enhanced context and remaining token budget
    enhanced_arguments = arguments.copy()

    # Store the enhanced prompt in the prompt field
    enhanced_arguments["prompt"] = enhanced_prompt
    logger.debug("[CONVERSATION_DEBUG] Storing enhanced prompt in 'prompt' field")

    # Calculate remaining token budget based on current model
    # (model_context was already created above for history building)
    token_allocation = model_context.calculate_token_allocation()

    # Calculate remaining tokens for files/new content
    # History has already consumed some of the content budget
    remaining_tokens = token_allocation.content_tokens - conversation_tokens
    enhanced_arguments["_remaining_tokens"] = max(0, remaining_tokens)  # Ensure non-negative
    enhanced_arguments["_model_context"] = model_context  # Pass context for use in tools

    logger.debug("[CONVERSATION_DEBUG] Token budget calculation:")
    logger.debug(f"[CONVERSATION_DEBUG]   Model: {model_context.model_name}")
    logger.debug(f"[CONVERSATION_DEBUG]   Total capacity: {token_allocation.total_tokens:,}")
    logger.debug(f"[CONVERSATION_DEBUG]   Content allocation: {token_allocation.content_tokens:,}")
    logger.debug(f"[CONVERSATION_DEBUG]   Conversation tokens: {conversation_tokens:,}")
    logger.debug(f"[CONVERSATION_DEBUG]   Remaining tokens: {remaining_tokens:,}")

    # Merge original context parameters (files, etc.) with new request
    if context.initial_context:
        logger.debug(f"[CONVERSATION_DEBUG] Merging initial context with {len(context.initial_context)} parameters")
        for key, value in context.initial_context.items():
            if key not in enhanced_arguments and key not in ["temperature", "thinking_mode", "model"]:
                enhanced_arguments[key] = value
                logger.debug(f"[CONVERSATION_DEBUG] Merged initial context param: {key}")

    logger.info(f"Reconstructed context for thread {continuation_id} (turn {len(context.turns)})")
    logger.debug(f"[CONVERSATION_DEBUG] Final enhanced arguments keys: {list(enhanced_arguments.keys())}")

    # Debug log files in the enhanced arguments for file tracking
    if "files" in enhanced_arguments:
        logger.debug(f"[CONVERSATION_DEBUG] Final files in enhanced arguments: {enhanced_arguments['files']}")

    # Log to activity file for monitoring
    try:
        mcp_activity_logger = logging.getLogger("mcp_activity")
        mcp_activity_logger.info(
            f"CONVERSATION_CONTINUATION: Thread {continuation_id} turn {len(context.turns)} - {len(context.turns)} previous turns loaded"
        )
    except Exception:
        pass

    return enhanced_arguments


async def handle_get_version() -> list[TextContent]:
    """
    Get comprehensive version and configuration information about the server.

    Provides details about the server version, configuration settings,
    available tools, and runtime environment. Useful for debugging and
    understanding the server's capabilities.

    Returns:
        Formatted text with version and configuration details
    """
    # Import thinking mode here to avoid circular imports
    from config import DEFAULT_THINKING_MODE_THINKDEEP

    # Gather comprehensive server information
    uptime = datetime.now(timezone.utc) - SERVER_START_TIME
    version_info = {
        "version": __version__,
        "updated": __updated__,
        "author": __author__,
        "default_model": DEFAULT_MODEL,
        "default_thinking_mode_thinkdeep": DEFAULT_THINKING_MODE_THINKDEEP,
        "max_context_tokens": f"{MAX_CONTEXT_TOKENS:,}",
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "server_started": SERVER_START_TIME.astimezone().isoformat(),
        "uptime_seconds": int(uptime.total_seconds()),
        "available_tools": list(TOOLS.keys()) + ["get_version"],
    }

    # Format the information in a human-readable way
    text = f"""Zen MCP Server v{__version__}
Updated: {__updated__}
Author: {__author__}

Configuration:
- Default Model: {DEFAULT_MODEL}
- Default Thinking Mode (ThinkDeep): {DEFAULT_THINKING_MODE_THINKDEEP}
- Max Context: {MAX_CONTEXT_TOKENS:,} tokens
- Python: {version_info["python_version"]}
- Started: {version_info["server_started"]}
- Uptime: {version_info["uptime_seconds"]} seconds

Available Tools:
{chr(10).join(f"  - {tool}" for tool in version_info["available_tools"])}

For updates, visit: https://github.com/BeehiveInnovations/zen-mcp-server"""

    # Create standardized tool output
    tool_output = ToolOutput(status="success", content=text, content_type="text", metadata={"tool_name": "get_version"})

    return [TextContent(type="text", text=tool_output.model_dump_json())]


async def main():
    """
    Main entry point for the MCP server.

    Initializes the Gemini API configuration and starts the server using
    stdio transport. The server will continue running until the client
    disconnects or an error occurs.

    The server communicates via standard input/output streams using the
    MCP protocol's JSON-RPC message format.
    """
    # Validate and configure providers based on available API keys
    configure_providers()

    # Log startup message for Docker log monitoring
    logger.info("Zen MCP Server starting up...")
    logger.info(f"Log level: {log_level}")

    # Log current model mode
    from config import IS_AUTO_MODE

    if IS_AUTO_MODE:
        logger.info("Model mode: AUTO (Claude will select the best model for each task)")
    else:
        logger.info(f"Model mode: Fixed model '{DEFAULT_MODEL}'")

    # Import here to avoid circular imports
    from config import DEFAULT_THINKING_MODE_THINKDEEP

    logger.info(f"Default thinking mode (ThinkDeep): {DEFAULT_THINKING_MODE_THINKDEEP}")

    logger.info(f"Available tools: {list(TOOLS.keys())}")
    logger.info("Server ready - waiting for tool requests...")

    # Run the server using stdio transport (standard input/output)
    # This allows the server to be launched by MCP clients as a subprocess
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="zen",
                server_version=__version__,
                capabilities=ServerCapabilities(tools=ToolsCapability()),  # Advertise tool support capability
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
