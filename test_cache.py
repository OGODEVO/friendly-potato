import httpx
import os
import time
from dotenv import load_dotenv

load_dotenv()
BASE_URL = os.getenv("RSC_BASE_URL", "https://rest.datafeeds.rolling-insights.com/api/v1")
RSC_TOKEN = os.getenv("RSC_TOKEN")

params = {"RSC_token": RSC_TOKEN, "game_id": "20260219-15-27", "t": int(time.time())}
res = httpx.get(f"{BASE_URL}/live/2026-02-19/NBA", params=params)
print(res.status_code)
print(res.text[:300])
