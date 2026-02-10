
import os
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
from openai import OpenAI
from tools.nba_tools import TOOLS_SCHEMA, AVAILABLE_TOOLS
import logging

logger = logging.getLogger(__name__)

class BaseAgent:
    def __init__(self, name: str, system_prompt: str, model: str = "gpt-4o", base_url: str = None, temperature: float = 0.5):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.temperature = temperature
        self.max_completion_tokens = 128000
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=base_url
        )
        
    def _execute_tool_calls(self, tool_calls) -> List[Dict[str, Any]]:
        results = []
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            logger.info(f"{self.name} calling tool: {function_name} with args: {function_args}")
            
            if function_name in AVAILABLE_TOOLS:
                tool_function = AVAILABLE_TOOLS[function_name]
                try:
                    response = tool_function(**function_args)
                except Exception as e:
                    response = f"Error executing {function_name}: {str(e)}"
            else:
                response = f"Error: Tool {function_name} not found."
            
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
                messages.append(message)
                tool_results = self._execute_tool_calls(message.tool_calls)
                messages.extend(tool_results)
            else:
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
                # Handle tool calls non-streaming
                messages.append(probe_msg)
                tool_results = self._execute_tool_calls(probe_msg.tool_calls)
                messages.extend(tool_results)
                # Loop to check for more tool calls
            else:
                # No more tool calls — now stream the final text response
                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOLS_SCHEMA,
                    stream=True,
                    temperature=self.temperature,
                    max_completion_tokens=self.max_completion_tokens
                )
                
                for event in stream:
                    if event.choices and event.choices[0].delta.content:
                        yield event.choices[0].delta.content
                
                return
