import asyncio
import json
import time

from agents.base_agent import BaseAgent

# A dummy tool callback to see the order of execution
def dummy_callback(name, args):
    print(f"Callback trigger: {name}")

class DummyMessage:
    def __init__(self):
        self.tool_calls = [
            type('obj', (object,), {'id': 'call_1', 'function': type('obj', (object,), {'name': 'get_live_vs_season_context', 'arguments': '{"team_name": "Lakers"}'})}),
            type('obj', (object,), {'id': 'call_2', 'function': type('obj', (object,), {'name': 'get_nba_news', 'arguments': '{"team_name": "Lakers"}'})})
        ]

async def main():
    agent = BaseAgent(name="TestAgent", system_prompt="test", api_key="dummy")
    
    print("Testing concurrent execute_tool_calls...")
    start_time = time.time()
    
    # We just need to pass the dummy tool_calls explicitly 
    results = agent._execute_tool_calls(DummyMessage().tool_calls, tool_callback=dummy_callback)
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"\nCompleted in {duration:.2f} seconds.")
    print("Results length:", len(results))
    print("Result 1 name:", results[0]["name"])
    print("Result 2 name:", results[1]["name"])
    
if __name__ == "__main__":
    asyncio.run(main())
