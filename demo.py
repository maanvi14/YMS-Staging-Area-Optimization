"""
YMS Staging Optimizer - Demo Script
Tests the system with 8 sample trucks
"""

import asyncio
import httpx
from datetime import datetime, timedelta

API_URL = "http://localhost:8001/optimize"

# 8 trucks with different types, priorities, and constraints
trucks = [
    {
        "truck_id": "TRK-101",
        "truck_type": "dry_van",
        "priority": "high",
        "estimated_arrival": (datetime.now() + timedelta(minutes=5)).isoformat(),
        "cargo_weight": 25000,
        "cargo_hazardous": False,
        "driver_hours_remaining": 8.5
    },
    {
        "truck_id": "TRK-102",
        "truck_type": "tanker",
        "priority": "critical",
        "estimated_arrival": (datetime.now() + timedelta(minutes=10)).isoformat(),
        "cargo_weight": 45000,
        "cargo_hazardous": True,
        "driver_hours_remaining": 6.0
    },
    {
        "truck_id": "TRK-103",
        "truck_type": "refrigerated",
        "priority": "standard",
        "estimated_arrival": (datetime.now() + timedelta(minutes=8)).isoformat(),
        "cargo_weight": 18000,
        "cargo_hazardous": False,
        "driver_hours_remaining": 9.0
    },
    {
        "truck_id": "TRK-104",
        "truck_type": "container",
        "priority": "standard",
        "estimated_arrival": (datetime.now() + timedelta(minutes=15)).isoformat(),
        "cargo_weight": 30000,
        "cargo_hazardous": False,
        "driver_hours_remaining": 7.5
    },
    {
        "truck_id": "TRK-105",
        "truck_type": "flatbed",
        "priority": "low",
        "estimated_arrival": (datetime.now() + timedelta(minutes=20)).isoformat(),
        "cargo_weight": 35000,
        "cargo_hazardous": False,
        "driver_hours_remaining": 10.0
    },
    {
        "truck_id": "TRK-106",
        "truck_type": "oversize",
        "priority": "high",
        "estimated_arrival": (datetime.now() + timedelta(minutes=12)).isoformat(),
        "cargo_weight": 60000,
        "cargo_hazardous": False,
        "driver_hours_remaining": 4.5
    },
    {
        "truck_id": "TRK-107",
        "truck_type": "dry_van",
        "priority": "critical",
        "estimated_arrival": (datetime.now() + timedelta(minutes=3)).isoformat(),
        "cargo_weight": 25000,
        "cargo_hazardous": False,
        "driver_hours_remaining": 5.0
    },
    {
        "truck_id": "TRK-108",
        "truck_type": "refrigerated",
        "priority": "standard",
        "estimated_arrival": (datetime.now() + timedelta(minutes=18)).isoformat(),
        "cargo_weight": 20000,
        "cargo_hazardous": False,
        "driver_hours_remaining": 8.0
    }
]

async def run_demo():
    print("=" * 70)
    print("YMS STAGING AREA OPTIMIZER - DEMO")
    print("=" * 70)
    print(f"\nSending {len(trucks)} trucks to optimizer...\n")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(API_URL, json=trucks)
    
    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return
    
    result = response.json()
    
    print(f"✅ Optimization Complete")
    print(f"📊 Yard Congestion Score: {result['yard_congestion_score']:.1f}/100")
    print(f"⏱️  Total Predicted Delay: {result['total_predicted_delay_minutes']:.1f} minutes")
    print(f"🤖 AI Summary: {result['ai_summary']}")
    print()
    
    if result['recommended_actions']:
        print("⚠️  Recommended Actions:")
        for action in result['recommended_actions']:
            print(f"   • {action}")
        print()
    
    print("-" * 70)
    print("DOCK ASSIGNMENTS:")
    print("-" * 70)
    
    for assignment in result['assignments']:
        print(f"\n🚛 {assignment['truck_id']} → {assignment['assigned_dock']}")
        print(f"   ⏰ Start: {assignment['expected_start']} | End: {assignment['expected_completion']}")
        print(f"   ⏱️  Wait: {assignment['waiting_time_minutes']:.1f} min | Transit: {assignment['route_time_minutes']:.1f} min")
        print(f"   🛣️  Route: {' → '.join(assignment['route'])}")
        print(f"   📏 Distance: {assignment['route_distance_m']}m")
        print(f"   🚦 Congestion: {assignment['congestion_level'].upper()}")
        print(f"   🤖 {assignment['explanation']}")
        if assignment['alerts']:
            print(f"   ⚠️  Alerts: {', '.join(assignment['alerts'])}")
    
    print("\n" + "=" * 70)
    print("DOCK UTILIZATION:")
    print("-" * 70)
    for dock_id, util in result['dock_utilization'].items():
        bar = "█" * int(util / 5) + "░" * (20 - int(util / 5))
        print(f"   {dock_id}: [{bar}] {util:.1f}%")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_demo())

    