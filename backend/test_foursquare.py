"""Test rapide Foursquare API"""
import asyncio, sys, os, urllib.request, urllib.parse, urllib.error, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

async def main():
    key = os.environ.get("FOURSQUARE_API_KEY", "")
    print(f"Key: {key[:15]}... ({len(key)} chars)")
    params = urllib.parse.urlencode({"query": "restaurant", "near": "London, UK", "limit": 3, "fields": "name,location"})
    url = f"https://api.foursquare.com/v3/places/search?{params}"
    for label, auth in [("No prefix", key), ("Bearer", f"Bearer {key}")]:
        print(f"
Trying [{label}]...")
        try:
            req = urllib.request.Request(url, headers={"Authorization": auth, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode())
                results = data.get("results", [])
                print(f"  SUCCESS! {len(results)} results")
                for p in results[:2]:
                    print(f"    - {p.get('name')} | {p.get('location',{}).get('formatted_address','')}")
                return
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code}: {e.read().decode()[:200]}")
        except Exception as e:
            print(f"  ERROR: {e}")
    print("
--- Testing Overpass ---")
    from app.services.overpass_service import search_venues
    venues = await search_venues(lat=51.514, lng=-0.085, radius_meters=1000, activity="drinks")
    print(f"Overpass: {len(venues)} venues")
    for v in venues[:3]:
        print(f"  - {v['name']} | {v.get('address','')}")

asyncio.run(main())
