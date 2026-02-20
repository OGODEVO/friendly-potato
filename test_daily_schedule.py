import asyncio
from tools.nba_tools import get_daily_schedule

async def test():
    print('Testing get_daily_schedule()...')
    try:
        res = get_daily_schedule()
        # Print just the first 500 characters so it doesn't flood the terminal
        print(res[:500] + '...' if len(str(res)) > 500 else res)
    except Exception as e:
        print('Error:', type(e), e)

asyncio.run(test())
