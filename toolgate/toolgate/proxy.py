"""MCP proxy server with dynamic tool gating."""

import asyncio
import sys
import time
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, CallToolResult

from toolgate.config import ToolGateConfig
from toolgate.index import ToolIndex
from toolgate.gating import GatingEngine
from toolgate.metrics import MetricsCollector
from toolgate.schemas import MCPTool, ToolStub


class ToolGateProxy:
    """MCP proxy server with semantic tool filtering."""

    def __init__(self, config: ToolGateConfig):
        self.config = config
        self.config.expand_paths()

        # Initialize components
        self.index = ToolIndex(config.index)
        self.gating = GatingEngine(config.gating)
        self.metrics = MetricsCollector(config.metrics)

        # MCP server
        self.server = Server("toolgate")

        # Upstream client sessions
        self.upstream_sessions: Dict[str, ClientSession] = {}

        # Cache for full tool schemas (lazy loading)
        self.schema_cache: Dict[str, MCPTool] = {}

        # Last user message for query embedding
        self.last_user_message: Optional[str] = None

        # Register handlers
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register MCP protocol handlers."""

        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """Handle tools/list request with semantic filtering."""
            start_time = time.time()

            try:
                # Use last user message as query, or empty string
                query = self.last_user_message or ""

                # Get all available tool names
                all_tools = self.index.get_all_tool_names()

                if not query or not all_tools:
                    # No query or no tools: return all as stubs
                    return await self._create_tool_stubs(all_tools)

                # Search index for relevant tools
                tool_names, scores = self.index.search(
                    query,
                    k=self.config.gating.top_k * 2  # Search more, filter later
                )

                # Apply gating rules
                gating_result = self.gating.apply_gating(scores, all_tools)
                selected_tools = gating_result.tools

                # Create stubs (phase 1: no inputSchema)
                stubs = await self._create_tool_stubs(selected_tools)

                # Record metrics
                latency_ms = (time.time() - start_time) * 1000
                all_full_tools = self.index.get_all_tools()
                tokens_saved = self.metrics.calculate_tokens_saved(
                    all_full_tools,
                    selected_tools
                )

                self.metrics.record(
                    event_type="list_tools",
                    tools_returned=len(selected_tools),
                    tokens_saved=tokens_saved,
                    latency_ms=latency_ms,
                    query_text=query,
                    metadata={
                        "total_tools": len(all_tools),
                        "boosted": gating_result.boosted,
                        "forced_include": gating_result.forced_include,
                    }
                )

                return stubs

            except Exception as e:
                # Fallback: return all tools on error
                all_tools = self.index.get_all_tool_names()
                return await self._create_tool_stubs(all_tools)

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tools/call request with JIT schema loading."""
            start_time = time.time()

            try:
                # Get indexed tool
                indexed_tool = self.index.get_tool(name)
                if not indexed_tool:
                    return [TextContent(
                        type="text",
                        text=f"Error: Tool '{name}' not found"
                    )]

                # Record tool call in session history
                self.gating.record_tool_call(name)

                # Get upstream session
                server_name = indexed_tool.server_name
                session = self.upstream_sessions.get(server_name)

                if not session:
                    return [TextContent(
                        type="text",
                        text=f"Error: Upstream server '{server_name}' not connected"
                    )]

                # Forward call to upstream server
                result = await session.call_tool(name, arguments)

                # Record metrics
                latency_ms = (time.time() - start_time) * 1000
                self.metrics.record(
                    event_type="call_tool",
                    tool_name=name,
                    latency_ms=latency_ms,
                )

                return result.content

            except Exception as e:
                return [TextContent(
                    type="text",
                    text=f"Error calling tool '{name}': {str(e)}"
                )]

    async def _create_tool_stubs(self, tool_names: List[str]) -> List[Tool]:
        """Create truncated tool stubs for phase 1 (listTools)."""
        stubs = []
        for name in tool_names:
            indexed_tool = self.index.get_tool(name)
            if indexed_tool:
                stub = ToolStub.from_tool(
                    indexed_tool.full_tool,
                    max_desc_len=self.config.gating.description_max_length
                )
                # Convert to MCP Tool type (without inputSchema)
                tool = Tool(
                    name=stub.name,
                    description=stub.description,
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    }
                )
                stubs.append(tool)
        return stubs

    async def _connect_upstream_servers(self) -> None:
        """Connect to all upstream MCP servers and build index."""
        start_time = time.time()

        all_tools = []
        all_server_names = []

        for server_config in self.config.upstream_servers:
            try:
                # Create stdio client
                server_params = StdioServerParameters(
                    command=server_config.command,
                    args=server_config.args,
                    env=server_config.env,
                )

                # Connect
                read, write = await stdio_client(server_params)
                session = ClientSession(read, write)
                await session.__aenter__()

                # Initialize
                await session.initialize()

                # List tools
                tools_response = await session.list_tools()

                # Convert to MCPTool objects
                for tool in tools_response.tools:
                    mcp_tool = MCPTool(
                        name=tool.name,
                        description=tool.description,
                        inputSchema=tool.inputSchema,
                    )
                    all_tools.append(mcp_tool)
                    all_server_names.append(server_config.name)

                # Store session
                self.upstream_sessions[server_config.name] = session

            except Exception as e:
                # Log error but continue with other servers
                print(f"Warning: Failed to connect to {server_config.name}: {e}",
                      file=sys.stderr)

        if not all_tools:
            raise RuntimeError("No tools available from upstream servers")

        # Build index
        self.index.build_index(all_tools, all_server_names)

        # Record metrics
        latency_ms = (time.time() - start_time) * 1000
        self.metrics.record(
            event_type="index_build",
            tools_returned=len(all_tools),
            latency_ms=latency_ms,
            metadata={
                "num_servers": len(self.upstream_sessions),
                "index_size": self.index.size,
            }
        )

    async def _cleanup(self) -> None:
        """Cleanup upstream sessions."""
        for session in self.upstream_sessions.values():
            try:
                await session.__aexit__(None, None, None)
            except Exception:
                pass

    async def run(self) -> None:
        """Run the proxy server."""
        try:
            # Connect to upstream servers and build index
            await self._connect_upstream_servers()

            # Run MCP server on stdio
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options()
                )

        finally:
            await self._cleanup()


async def run_proxy(config: ToolGateConfig) -> None:
    """Run the ToolGate proxy server."""
    proxy = ToolGateProxy(config)
    await proxy.run()
