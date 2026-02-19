#!/usr/bin/env python3
"""
Script to explore elabFTW API endpoints and discover booking functionality.

This helps identify what endpoints are available for implementing new features.
"""

import os

import httpx
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("ELABFTW_API_URL", "https://your-server.example.com/api/v2")
API_KEY = os.getenv("ELABFTW_API_KEY", "")
VERIFY_SSL = os.getenv("ELABFTW_VERIFY_SSL", "false").lower() == "true"

headers = {
    "Authorization": API_KEY,
    "Content-Type": "application/json",
}


def explore_endpoint(
    client: httpx.Client, endpoint: str, method: str = "GET", params: dict = None
):
    """Try an endpoint and report what we find."""
    try:
        url = f"{API_BASE_URL}/{endpoint}"
        if method == "GET":
            response = client.get(url, params=params or {})
        elif method == "OPTIONS":
            response = client.options(url)

        response.raise_for_status()

        print(f"\n✓ {method} /{endpoint}")
        print(f"  Status: {response.status_code}")

        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            if isinstance(data, list):
                print(f"  Returns: List with {len(data)} items")
                if len(data) > 0:
                    print(f"  First item keys: {list(data[0].keys())}")
            elif isinstance(data, dict):
                print(f"  Returns: Dict with keys: {list(data.keys())}")

        return True
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print(f"\n✗ {method} /{endpoint} - Not Found (404)")
        elif e.response.status_code == 403:
            print(
                f"\n⚠ {method} /{endpoint} - Forbidden (403) - Might exist but need permissions"
            )
        else:
            print(f"\n✗ {method} /{endpoint} - Error {e.response.status_code}")
        return False
    except Exception as e:
        print(f"\n✗ {method} /{endpoint} - Error: {str(e)}")
        return False


def main():
    """Explore elabFTW API for booking and other endpoints."""

    if not API_KEY:
        print("Error: ELABFTW_API_KEY not set!")
        return

    print(f"Exploring elabFTW API at: {API_BASE_URL}")
    print(f"SSL Verification: {VERIFY_SSL}")
    print("=" * 60)

    with httpx.Client(headers=headers, verify=VERIFY_SSL, timeout=30.0) as client:
        # Known working endpoints (for reference)
        print("\n### KNOWN WORKING ENDPOINTS ###")
        explore_endpoint(client, "experiments", params={"limit": 1})
        explore_endpoint(client, "items", params={"limit": 1})
        explore_endpoint(client, "experiments_templates", params={"limit": 1})
        explore_endpoint(client, "teams/1/experiments_categories")
        explore_endpoint(client, "teams/1/items_types")

        # Potential booking-related endpoints
        print("\n\n### EXPLORING BOOKING-RELATED ENDPOINTS ###")
        booking_endpoints = [
            "bookings",
            "bookable",
            "scheduler",
            "schedule",
            "reservations",
            "events",
            "calendar",
            "items_bookings",
            "experiments_bookings",
        ]

        for endpoint in booking_endpoints:
            explore_endpoint(client, endpoint, params={"limit": 1})

        # Check if items have booking info
        print("\n\n### CHECKING ITEM STRUCTURE FOR BOOKING DATA ###")
        try:
            # Get first item to see its structure
            response = client.get(f"{API_BASE_URL}/items", params={"limit": 1})
            if response.status_code == 200:
                items = response.json()
                if items and len(items) > 0:
                    item_id = items[0]["id"]
                    # Get full item details
                    item_response = client.get(f"{API_BASE_URL}/items/{item_id}")
                    if item_response.status_code == 200:
                        item = item_response.json()
                        print(f"\nFull item {item_id} structure:")
                        print(f"Keys: {list(item.keys())}")

                        # Look for booking-related fields
                        booking_fields = [
                            k
                            for k in item.keys()
                            if any(
                                term in k.lower()
                                for term in [
                                    "book",
                                    "schedul",
                                    "reserv",
                                    "event",
                                    "calendar",
                                ]
                            )
                        ]
                        if booking_fields:
                            print(f"Booking-related fields found: {booking_fields}")
                            for field in booking_fields:
                                print(f"  {field}: {item[field]}")
                        else:
                            print("No obvious booking fields in item structure")
        except Exception as e:
            print(f"Error exploring item structure: {e}")

        # Try team-level endpoints
        print("\n\n### EXPLORING TEAM-LEVEL ENDPOINTS ###")
        team_endpoints = [
            "teams/1/bookings",
            "teams/1/scheduler",
            "teams/1/events",
        ]

        for endpoint in team_endpoints:
            explore_endpoint(client, endpoint)

        # Try with a specific item (if bookable items exist)
        print("\n\n### CHECKING ITEM-SPECIFIC BOOKING ENDPOINTS ###")
        # Try to find a bookable item by searching for common setup names
        try:
            response = client.get(
                f"{API_BASE_URL}/items", params={"q": "setup", "limit": 5}
            )
            if response.status_code == 200:
                items = response.json()
                if items and len(items) > 0:
                    for item in items[:2]:  # Check first 2 items
                        item_id = item["id"]
                        print(
                            f"\nTrying booking endpoints for item {item_id} ({item.get('title', 'untitled')}):"
                        )
                        explore_endpoint(client, f"items/{item_id}/bookings")
                        explore_endpoint(client, f"items/{item_id}/schedule")
                        explore_endpoint(client, f"items/{item_id}/events")
        except Exception as e:
            print(f"Error exploring item-specific endpoints: {e}")

        # Check API info endpoint
        print("\n\n### CHECKING API INFO ###")
        explore_endpoint(client, "info")
        explore_endpoint(client, "")  # Root endpoint

    print("\n\n" + "=" * 60)
    print("Exploration complete!")
    print("\nNext steps:")
    print("1. Check the elabFTW documentation at https://doc.elabftw.net/")
    print("2. Look at the Swagger UI at your elabFTW instance: <your-server>/api/v2/")
    print("3. Check elabFTW source code: https://github.com/elabftw/elabftw")
    print("4. If booking is a plugin/extension, check your elabFTW extensions")


if __name__ == "__main__":
    main()
