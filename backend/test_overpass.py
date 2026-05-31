import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


async def main():
    from app.services.overpass_service import search_venues

    # Test 1 : Londres, Shepherd's Bush (midpoint entre Hannover Sq et Ealing)
    print("=== Test Londres (bar/casual) ===")
    venues = await search_venues(lat=51.505, lng=-0.196, radius_meters=1500, activity="drinks", vibe="casual")
    print("Found: " + str(len(venues)) + " venues")
    for v in venues[:5]:
        print("  - " + v["name"] + " | " + v.get("address", "no address") + " | " + v.get("category", ""))

    # Test 2 : Paris, Bastille
    print("\n=== Test Paris (restaurant/festif) ===")
    venues2 = await search_venues(lat=48.853, lng=2.369, radius_meters=1000, activity="dinner", vibe="festive")
    print("Found: " + str(len(venues2)) + " venues")
    for v in venues2[:5]:
        print("  - " + v["name"] + " | " + v.get("address", "no address"))


asyncio.run(main())
