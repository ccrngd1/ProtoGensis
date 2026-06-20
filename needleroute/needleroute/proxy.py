"""MCP proxy server with NeedleRoute."""

import asyncio
import sys
import time
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from needleroute.config import NeedleRouteConfig
from needleroute.index import ToolIndex
from needleroute.router import NeedleRouter
from needleroute.metrics import MetricsCollector
from needleroute.schemas import MCPTool, ToolStub


class NeedleRouteProxy:
    """MCP proxy server with Needle routing."""

    def __init__(self, config: NeedleRouteConfig):
        self.config = config
        self.config.expand_paths()

        # Initialize components
        self.index = ToolIndex(config.toolgate)
        self.router = NeedleRouter(config)
        self.metrics = MetricsCollector(config.metrics)

        # MCP server
        self.server = Server("needleroute")

        # Upstream client sessions
        self.upstream_sessions: Dict[str, ClientSession] = {}

        # Last user message for routing
        self.last_user_message: Optional[str] = None

        # Register handlers
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register MCP protocol handlers."""

        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """
            Handle tools/list request.

            Returns stubs (phase 1: no full inputSchema) after ToolGate filtering.
            """
            start_time = time.time()

            try:
                query = self.last_user_message or ""
                all_tools = self.index.get_all_tool_names()

                if not query or not all_tools:
                    # No query: return all as stubs
                    return await self._create_tool_stubs(all_tools)

                # Search index for relevant tools
                tool_names, scores = self.index.search(
                    query,
                    k=self.config.toolgate.top_k * 2
                )

                # Apply gating rules (done in router)
                # For now, just take top-K from index
                selected_tools = tool_names[:self.config.toolgate.top_k]

                # Create stubs (phase 1)
                stubs = await self._create_tool_stubs(selected_tools)

                # Record metrics
                latency_ms = (time.time() - start_time) * 1000
                self.metrics.record(
                    event_type="list_tools",
                    query=query,
                    latency_ms=latency_ms,
                    metadata={
                        "total_tools": len(all_tools),
                        "filtered_tools": len(selected_tools),
                    }
                )

                return stubs

            except Exception as e:
                print(f"Error in list_tools: {e}", file=sys.stderr)
                # Fallback: return all tools
                all_tools = self.index.get_all_tool_names()
                return await self._create_tool_stubs(all_tools)

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """
            Handle tools/call request.

            Uses NeedleRouter to select best tool, with escalation if needed.
            """
            start_time = time.time()

            try:
                # For actual tool call, we need to route through Needle
                # But we already have the tool name from the agent
                # So we just forward the call to upstream

                # Get indexed tool
                indexed_tool = self.index.get_tool(name)
                if not indexed_tool:
                    return [TextContent(
                        type="text",
                        text=f"Error: Tool '{name}' not found"
                    )]

                # Record tool call
                self.router.record_tool_call(name)

                # Get upstream session
                server_name = indexed_tool.server_name
                session = self.upstream_sessions.get(server_name)

                if not session:
                    return [TextContent(
                        type="text",
                        text=f"Error: Upstream server '{server_name}' not connected"
                    )]

                # Forward call to upstream
                result = await session.call_tool(name, arguments)

                # Record metrics
                latency_ms = (time.time() - start_time) * 1000
                self.metrics.record(
                    event_type="call_tool",
                    selected_tool=name,
                    latency_ms=latency_ms,
                )

                return result.content

            except Exception as e:
                return [TextContent(
                    type="text",
                    text=f"Error calling tool '{name}': {str(e)}"
                )]

    async def _create_tool_stubs(self, tool_names: List[str]) -> List[Tool]:
        """Create truncated tool stubs for phase 1."""
        stubs = []
        for name in tool_names:
            indexed_tool = self.index.get_tool(name)
            if indexed_tool:
                stub = ToolStub.from_tool(
                    indexed_tool.full_tool,
                    max_desc_len=self.config.toolgate.phase1_max_desc
                )
                # Convert to MCP Tool (minimal schema)
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
                    command=server_config.command[0],
                    args=server_config.command[1:] if len(server_config.command) > 1 else [],
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

                print(f"Connected to {server_config.name}: {len(tools_response.tools)} tools", file=sys.stderr)

            except Exception as e:
                print(f"Warning: Failed to connect to {server_config.name}: {e}", file=sys.stderr)

        if not all_tools:
            raise RuntimeError("No tools available from upstream servers")

        # Build index
        print(f"Building index with {len(all_tools)} tools...", file=sys.stderr)
        self.index.build_index(all_tools, all_server_names)

        # Pre-encode tools for Needle
        print("Pre-encoding tools for Needle model...", file=sys.stderr)
        self.router.pre_encode_tools(all_tools)

        # Record metrics
        latency_ms = (time.time() - start_time) * 1000
        self.metrics.record(
            event_type="index_build",
            latency_ms=latency_ms,
            metadata={
                "num_servers": len(self.upstream_sessions),
                "num_tools": len(all_tools),
            }
        )

        print(f"NeedleRoute ready with {len(all_tools)} tools from {len(self.upstream_sessions)} servers", file=sys.stderr)

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


async def run_proxy(config: NeedleRouteConfig) -> None:
    """Run the NeedleRoute proxy server."""
    proxy = NeedleRouteProxy(config)
    await proxy.run()
