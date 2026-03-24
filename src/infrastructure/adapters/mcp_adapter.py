import asyncio
import threading
import logging
from typing import List
from contextlib import AsyncExitStack

# Set up logging for MCP Adapter
logger = logging.getLogger(__name__)

class SyncSQLiteMCP:
    """
    A synchronous wrapper around the asynchronous Model Context Protocol (MCP)
    SQLite server using an isolated background event loop.
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.tools: List[Any] = []
        
        # We start a dedicated background thread with its own asyncio loop
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._start_loop, daemon=True)
        self._ready_event = threading.Event()
        
        logger.info("[mcp] Starting SQLite MCP Server thread for db: %s", db_path)
        self._thread.start()
        
        # Wait until tools are loaded or timeout occurs
        if not self._ready_event.wait(timeout=15.0):
            logger.error("[mcp] Timeout waiting for MCP tools to load")
            
    def _start_loop(self):
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._init_mcp())
        except Exception as e:
            logger.error("[mcp] Fatal error in MCP loop: %s", e)
        finally:
            self._ready_event.set()
            
        # Keep the event loop running to service tool invocations
        self._loop.run_forever()
        
    async def _init_mcp(self):
        try:
            from mcp import StdioServerParameters
            from mcp.client.stdio import stdio_client
            from mcp.client.session import ClientSession
            from langchain_mcp_adapters.tools import load_mcp_tools
            
            self.server_params = StdioServerParameters(
                command="mcp-server-sqlite", 
                args=["--db-path", self.db_path]
            )
            
            self.stack = AsyncExitStack()
            transport = await self.stack.enter_async_context(stdio_client(self.server_params))
            self.session = await self.stack.enter_async_context(ClientSession(transport[0], transport[1]))
            await self.session.initialize()
            
            # Load the asynchronous tools from the server
            async_tools = await load_mcp_tools(self.session)
            logger.info("[mcp] Loaded %d MCP tools: %s", len(async_tools), [t.name for t in async_tools])
            
            # Wrap them into synchronous LangChain tools
            for at in async_tools:
                # We only want read-only tools or all of them. Exposing all for maximum capability.
                self.tools.append(self._make_sync_tool(at))
                
        except Exception as e:
            logger.error("[mcp] Failed to initialize MCP Session: %s", e)
            
    def _make_sync_tool(self, async_tool):
        from langchain_core.tools import StructuredTool
        
        def sync_func(*args, **kwargs):
            # Normalise args for LangChain
            if args:
                call_args = args[0] if isinstance(args[0], dict) else args
            else:
                call_args = kwargs
                
            # Submit to the background event loop
            future = asyncio.run_coroutine_threadsafe(
                async_tool.ainvoke(call_args), 
                self._loop
            )
            return future.result()
            
        return StructuredTool(
            name=async_tool.name,
            description=async_tool.description,
            args_schema=async_tool.args_schema,
            func=sync_func,
        )
