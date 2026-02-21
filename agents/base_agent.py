
import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Dict, Any, Optional, AsyncGenerator
from openai import OpenAI
from tools.nba_tools import TOOLS_SCHEMA, AVAILABLE_TOOLS
from tools.log_context import slog, Timer

def _get_live_context_str() -> str:
    now_ct = datetime.now(ZoneInfo("America/Chicago"))
    return f"Current Date/Time (US Central): {now_ct.strftime('%Y-%m-%d %I:%M %p')}\nUse this exact time to determine if a game is 'live', 'upcoming', or 'finished'."

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
        
    def _execute_tool_calls(self, tool_calls, tool_callback=None) -> List[Dict[str, Any]]:
        from concurrent.futures import ThreadPoolExecutor
        results = [None] * len(tool_calls)

        def _run_tool(index: int, tool_call):
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            slog.info(
                "agent.tool_call.start",
                agent=self.name,
                tool=function_name,
                args=function_args,
            )
            
            timer = Timer()
            
            if tool_callback:
                try:
                    tool_callback(function_name, function_args)
                except Exception as e:
                    slog.warning("agent.tool_callback.failed", error=str(e))
                
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
            
            results[index] = {
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": function_name,
                "content": str(response)
            }

        with ThreadPoolExecutor(max_workers=5) as executor:
            for i, tc in enumerate(tool_calls):
                executor.submit(_run_tool, i, tc)
        return results

    def chat(self, history: List[Dict[str, Any]], tool_callback=None) -> str:
        """
        Non-streaming chat. Used internally for tool-call loops.
        Returns the final text response after all tool calls are resolved.
        """
        system_content = self.system_prompt.format(current_time=_get_live_context_str())
        messages = [{"role": "system", "content": system_content}] + history
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
                tool_results = self._execute_tool_calls(message.tool_calls, tool_callback=tool_callback)
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

    def chat_stream(self, history: List[Dict[str, Any]], tool_callback=None):
        """
        Streaming chat generator. Yields text chunks as they arrive.
        Handles tool calls internally (non-streaming) then streams the final response.
        
        Usage:
            for chunk in agent.chat_stream(history):
                # chunk is a string fragment
        """
        system_content = self.system_prompt.format(current_time=_get_live_context_str())
        messages = [{"role": "system", "content": system_content}] + history
        turn_timer = Timer()
        tool_call_rounds = 0
        
        while True:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOLS_SCHEMA,
                stream=True,
                temperature=self.temperature,
                max_completion_tokens=self.max_completion_tokens
            )
            
            tool_calls_dict = {}
            is_tool_call = False
            total_chars = 0
            
            for event in stream:
                if not event.choices:
                    continue
                delta = event.choices[0].delta
                
                if delta.tool_calls:
                    is_tool_call = True
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_dict:
                            tool_calls_dict[idx] = {
                                "id": tc.id,
                                "function": {"name": "", "arguments": ""}
                            }
                        if tc.id:
                            tool_calls_dict[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_dict[idx]["function"]["name"] += tc.function.name
                            if tc.function.arguments:
                                tool_calls_dict[idx]["function"]["arguments"] += tc.function.arguments
                elif delta.content:
                    chunk = delta.content
                    total_chars += len(chunk)
                    yield chunk

            if is_tool_call:
                tool_call_rounds += 1
                class DummyObj: pass
                constructed_calls = []
                for idx in sorted(tool_calls_dict.keys()):
                    call_data = tool_calls_dict[idx]
                    obj = DummyObj()
                    obj.id = call_data["id"]
                    obj.function = DummyObj()
                    obj.function.name = call_data["function"]["name"]
                    obj.function.arguments = call_data["function"]["arguments"]
                    constructed_calls.append(obj)
                    
                assistant_message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {
                                "name": c.function.name,
                                "arguments": c.function.arguments
                            }
                        } for c in constructed_calls
                    ]
                }
                messages.append(assistant_message)
                
                tool_results = self._execute_tool_calls(constructed_calls, tool_callback=tool_callback)
                messages.extend(tool_results)
            else:
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
