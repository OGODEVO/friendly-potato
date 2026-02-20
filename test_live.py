import asyncio
from tools.nba_tools import get_live_vs_season_context

async def test():
    print('Testing get_live_vs_season_context("Houston")...')
    try:
        res = get_live_vs_season_context(team_name="Houston")
        print(res[:1000] + '...' if len(str(res)) > 1000 else res)
    except Exception as e:
        print('Error:', type(e), e)

asyncio.run(test())
