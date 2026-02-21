import asyncio
import time
import yaml

from agents.base_agent import BaseAgent

async def main():
    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    model = config['agents']['agent_1']['model']
    
    agent = BaseAgent(name="TestStreamAgent", system_prompt="Answer perfectly without calling tools for this question.", model=model)
    
    print(f"Testing chat_stream without tools (using {model})...")
    start_time = time.time()
    
    # We will just ask a simple question. It shouldn't trigger tools.
    history = [{"role": "user", "content": "Hello, simply say the word 'Ping'."}]
    
    # Iterate generator
    chunks = []
    first_chunk_time = None
    for chunk in agent.chat_stream(history):
        if not first_chunk_time:
            first_chunk_time = time.time()
        chunks.append(chunk)
        
    end_time = time.time()
    
    if first_chunk_time:
        ttft = first_chunk_time - start_time
        print(f"Time to First Token: {ttft:.2f} seconds")
    else:
        print("No tokens yielded!")
        
    print(f"Total time: {end_time - start_time:.2f} seconds")
    print(f"Response: {''.join(chunks)}")

if __name__ == "__main__":
    asyncio.run(main())
