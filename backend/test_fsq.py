import asyncio
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


async def test_foursquare():
    key = os.environ.get("FOURSQUARE_API_KEY", "")
    print("Key:", key[:20], "len=", len(key))

    params = urllib.parse.urlencode({
        "query": "restaurant",
        "near": "London, UK",
        "limit": "3",
        "fields": "name,location",
    })
    url = "https://api.foursquare.com/v3/places/search?" + params

    for label, auth in [("No prefix", key), ("Bearer", "Bearer " + key)]:
        print("\nTrying [" + label + "]...")
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", auth)
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())
                results = data.get("results", [])
                print("  SUCCESS! " + str(len(results)) + " results")
                for p in results[:2]:
                    loc = p.get("location", {})
                    print("    - " + p.get("name", "?") + " | " + loc.get("formatted_address", ""))
                return
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:300]
            print("  HTTP " + str(e.code) + ": " + body)
        except Exception as e:
            print("  ERROR: " + str(e))


async def test_overpass():
    print("\n--- Testing Overpass (no key) ---")
    from app.services.overpass_service import search_venues
    venues = await search_venues(lat=51.514, lng=-0.085, radius_meters=1000, activity="drinks")
    print("Overpass: " + str(len(venues)) + " venues")
    for v in venues[:3]:
        print("  - " + v["name"] + " | " + v.get("address", ""))


async def main():
    await test_foursquare()
    await test_overpass()


asyncio.run(main())
