
import os
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
from openai import OpenAI
from tools.nba_tools import TOOLS_SCHEMA, AVAILABLE_TOOLS
from tools.log_context import slog, Timer

class BaseAgent:
    def __init__(self, name: str, system_prompt: str, model: str = "gpt-4o", base_url: str = None, temperature: float = 0.5, api_key: str = None, max_completion_tokens: int = 128000):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.temperature = temperature
        self.max_completion_tokens = max_completion_tokens
        self.client = OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url
        )
        
    def _execute_tool_calls(self, tool_calls) -> List[Dict[str, Any]]:
        results = []
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            slog.info(
                "agent.tool_call.start",
                agent=self.name,
                tool=function_name,
                args=function_args,
            )
            
            timer = Timer()
            if function_name in AVAILABLE_TOOLS:
                tool_function = AVAILABLE_TOOLS[function_name]
                try:
                    with timer:
                        response = tool_function(**function_args)
                    slog.info(
                        "agent.tool_call.ok",
                        agent=self.name,
                        tool=function_name,
                        latency_ms=timer.elapsed_ms,
                        response_len=len(str(response)),
                    )
                except Exception as e:
                    timer.stop()
                    response = f"Error executing {function_name}: {str(e)}"
                    slog.error(
                        "agent.tool_call.error",
                        agent=self.name,
                        tool=function_name,
                        latency_ms=timer.elapsed_ms,
                        error=str(e),
                    )
            else:
                response = f"Error: Tool {function_name} not found."
                slog.warning(
                    "agent.tool_call.not_found",
                    agent=self.name,
                    tool=function_name,
                )
            
            results.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": function_name,
                "content": str(response)
            })
        return results

    def chat(self, history: List[Dict[str, Any]]) -> str:
        """
        Non-streaming chat. Used internally for tool-call loops.
        Returns the final text response after all tool calls are resolved.
        """
        messages = [{"role": "system", "content": self.system_prompt}] + history
        turn_timer = Timer()
        tool_call_rounds = 0
        
        while True:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOLS_SCHEMA,
                tool_choice="auto",
                temperature=self.temperature,
                max_completion_tokens=self.max_completion_tokens
            )
            
            message = completion.choices[0].message
            
            if message.tool_calls:
                tool_call_rounds += 1
                messages.append(message)
                tool_results = self._execute_tool_calls(message.tool_calls)
                messages.extend(tool_results)
            else:
                turn_timer.stop()
                slog.info(
                    "agent.chat.complete",
                    agent=self.name,
                    model=self.model,
                    latency_ms=turn_timer.elapsed_ms,
                    tool_call_rounds=tool_call_rounds,
                    response_len=len(message.content or ""),
                )
                return message.content

    def chat_stream(self, history: List[Dict[str, Any]]):
        """
        Streaming chat generator. Yields text chunks as they arrive.
        Handles tool calls internally (non-streaming) then streams the final response.
        
        Usage:
            for chunk in agent.chat_stream(history):
                # chunk is a string fragment
        """
        messages = [{"role": "system", "content": self.system_prompt}] + history
        turn_timer = Timer()
        tool_call_rounds = 0
        
        # First, resolve any tool calls (non-streaming, since tool results must be complete)
        while True:
            # Check if the model wants tool calls first (non-streaming probe)
            probe = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOLS_SCHEMA,
                tool_choice="auto",
                temperature=self.temperature,
                max_completion_tokens=self.max_completion_tokens
            )
            
            probe_msg = probe.choices[0].message
            
            if probe_msg.tool_calls:
                tool_call_rounds += 1
                # Handle tool calls non-streaming
                messages.append(probe_msg)
                tool_results = self._execute_tool_calls(probe_msg.tool_calls)
                messages.extend(tool_results)
                # Loop to check for more tool calls
            else:
                # No more tool calls — now stream the final text response
                slog.info(
                    "agent.stream.final_start",
                    agent=self.name,
                    model=self.model,
                    tool_call_rounds=tool_call_rounds,
                )
                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOLS_SCHEMA,
                    stream=True,
                    temperature=self.temperature,
                    max_completion_tokens=self.max_completion_tokens
                )
                
                total_chars = 0
                for event in stream:
                    if event.choices and event.choices[0].delta.content:
                        chunk = event.choices[0].delta.content
                        total_chars += len(chunk)
                        yield chunk
                
                turn_timer.stop()
                slog.info(
                    "agent.stream.complete",
                    agent=self.name,
                    model=self.model,
                    latency_ms=turn_timer.elapsed_ms,
                    tool_call_rounds=tool_call_rounds,
                    response_len=total_chars,
                )
                return
