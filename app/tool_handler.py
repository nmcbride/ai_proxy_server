"""
Tool calling handler for MCP integration
"""

import asyncio
import json
import time
from typing import Any, Dict

import httpx
import structlog

from app.config import settings
from app.mcp_client import mcp_manager
from app.profiler import get_profiler

logger = structlog.get_logger()


async def handle_tool_calls(
    initial_response: Dict[str, Any],
    original_request: Dict[str, Any],
    client: httpx.AsyncClient,
    upstream_url: str,
    headers: Dict[str, str],
    proxy_request_id: str,
) -> Dict[str, Any]:
    """
    Handle tool calls by executing MCP tools and sending results back to LLM
    Supports multi-step tool calling (e.g., Context7's resolve-library-id -> get-library-docs)
    """
    overall_start_time = time.time()

    # Get profiler for this request
    profiler = get_profiler(proxy_request_id)

    messages = original_request.get("messages", []).copy()
    current_response = initial_response
    max_tool_rounds = settings.MAX_TOOL_ROUNDS
    tool_round = 0

    while tool_round < max_tool_rounds:
        tool_round += 1

        # Check if current response has tool calls
        if not ("choices" in current_response and current_response["choices"]):
            break

        first_choice = current_response["choices"][0]
        assistant_message = first_choice["message"]
        tool_calls = assistant_message.get("tool_calls", [])

        if not tool_calls:
            # No more tool calls, we're done
            logger.info(
                "No more tool calls, returning final response",
                proxy_request_id=proxy_request_id,
                total_rounds=tool_round - 1,
            )
            break

        logger.info(
            "Processing tool calls",
            proxy_request_id=proxy_request_id,
            round=tool_round,
            tool_count=len(tool_calls),
        )

        # Add the assistant's tool call message to conversation
        messages.append(assistant_message)

        # Execute all tool calls in this round
        tool_results = []
        for tool_call in tool_calls:
            if tool_call.get("type") == "function":
                function_info = tool_call["function"]
                function_name = function_info["name"]
                tool_call_id = tool_call["id"]

                try:
                    # Parse arguments
                    async with profiler.time_phase("Parsing Tool Arguments", tool=function_name) if profiler else None:
                        arguments_str = function_info.get("arguments", "{}")
                        arguments = json.loads(arguments_str) if arguments_str else {}

                    tool_start_time = time.time()

                    logger.info(
                        "Executing tool",
                        proxy_request_id=proxy_request_id,
                        round=tool_round,
                        tool=function_name,
                        arguments=list(arguments.keys()),
                    )

                    # Debug: Log full tool arguments
                    logger.debug(
                        "Tool arguments (full)",
                        proxy_request_id=proxy_request_id,
                        tool=function_name,
                        arguments=arguments
                    )

                    # Call the MCP tool with timeout
                    async with profiler.time_phase("Executing Tool", tool=function_name, round=tool_round) if profiler else None:
                        result = await asyncio.wait_for(
                            mcp_manager.call_tool(function_name, arguments),
                            timeout=settings.TOOL_EXECUTION_TIMEOUT
                        )

                    tool_execution_time = time.time() - tool_start_time

                    # Format result as string (MCP returns content objects)
                    async with profiler.time_phase("Formatting Tool Results", tool=function_name) if profiler else None:
                        if isinstance(result, list) and result:
                            # MCP returns list of content objects
                            result_text = ""
                            for content in result:
                                if hasattr(content, "text"):
                                    result_text += content.text
                                elif isinstance(content, dict) and "text" in content:
                                    result_text += content["text"]
                                else:
                                    result_text += str(content)
                        else:
                            result_text = str(result)

                        tool_results.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": result_text,
                            }
                        )

                    # Debug: Log full tool output
                    logger.debug(
                        "Tool output (full)",
                        proxy_request_id=proxy_request_id,
                        tool=function_name,
                        output=result_text
                    )

                    logger.debug(
                        "MCP tool executed successfully",
                        proxy_request_id=proxy_request_id,
                        round=tool_round,
                        tool=function_name,
                        execution_time_ms=round(tool_execution_time * 1000, 2),
                    )

                except asyncio.TimeoutError:
                    logger.error(
                        "MCP tool execution timeout",
                        proxy_request_id=proxy_request_id,
                        round=tool_round,
                        tool=function_name,
                        timeout=settings.TOOL_EXECUTION_TIMEOUT,
                    )

                    # Add timeout error result
                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": f"Tool {function_name} execution timed out after {settings.TOOL_EXECUTION_TIMEOUT} seconds",
                        }
                    )

                except Exception as e:
                    logger.error(
                        "MCP tool execution failed",
                        proxy_request_id=proxy_request_id,
                        round=tool_round,
                        tool=function_name,
                        error=str(e),
                    )

                    # Add error result
                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": f"Error executing tool {function_name}: {str(e)}",
                        }
                    )

        # Add all tool results to conversation
        messages.extend(tool_results)

        # Create new request payload WITH tools still available for next round
        new_request = original_request.copy()
        new_request["messages"] = messages
        # Keep tools available for multi-step tool calling

        logger.info(
            "Sending tool results back to LLM for next round",
            proxy_request_id=proxy_request_id,
            round=tool_round,
            message_count=len(messages),
        )

        # Make next request with tool results
        async with profiler.time_phase("Preparing Tool Follow-Up", round=tool_round) if profiler else None:
            new_body = json.dumps(new_request).encode()

            # Update headers
            new_headers = headers.copy()
            new_headers["content-length"] = str(len(new_body))

            # Build and send request for tool calling follow-up
            tool_request = client.build_request(
                method="POST",
                url=upstream_url,
                headers=new_headers,
                content=new_body,
            )

        async with profiler.time_phase("Calling Upstream Hybrid Follow-Up", round=tool_round) if profiler else None:
            next_response = await client.send(tool_request)

        # Parse response for next round
        async with profiler.time_phase("Processing Tool Results Response", round=tool_round) if profiler else None:
            current_response = json.loads(next_response.content)

    if tool_round >= max_tool_rounds:
        logger.warning(
            "Max tool rounds reached, stopping",
            proxy_request_id=proxy_request_id,
            max_rounds=settings.MAX_TOOL_ROUNDS,
        )

    overall_execution_time = time.time() - overall_start_time

    logger.debug(
        "Tool calling completed",
        proxy_request_id=proxy_request_id,
        total_rounds=tool_round - 1,
        total_time_ms=round(overall_execution_time * 1000, 2),
    )

    return current_response
