#!/usr/bin/env python3
"""
Test script for booking functionality in elabFTW API.

This script tests the booking endpoints before integrating them into the MCP server.
Run this to verify your API credentials and that booking works as expected.
"""

import os
from datetime import datetime, timedelta

import httpx
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("ELABFTW_API_URL", "")
API_KEY = os.getenv("ELABFTW_API_KEY", "")
VERIFY_SSL = os.getenv("ELABFTW_VERIFY_SSL", "false").lower() == "true"

headers = {
    "Authorization": API_KEY,
    "Content-Type": "application/json",
}


def test_list_events():
    """Test listing existing bookings."""
    print("\n" + "=" * 60)
    print("TEST 1: List existing bookings")
    print("=" * 60)

    with httpx.Client(headers=headers, verify=VERIFY_SSL, timeout=30.0) as client:
        response = client.get(f"{API_BASE_URL}/events", params={"limit": 10})

        if response.status_code == 200:
            events = response.json()
            print(f"✓ Found {len(events)} bookings")

            if events:
                print("\nFirst booking:")
                event = events[0]
                print(f"  ID: {event.get('id')}")
                print(f"  Title: {event.get('title')}")
                print(
                    f"  Item: {event.get('item_title')} (ID: {event.get('items_id')})"
                )
                print(f"  Start: {event.get('start')}")
                print(f"  End: {event.get('end')}")
                print(f"  User: {event.get('fullname')}")
                print(f"  Duration: {event.get('event_duration_minutes')} minutes")
            else:
                print("  No existing bookings found")

            return True
        else:
            print(f"✗ Failed: {response.status_code} - {response.text}")
            return False


def test_get_bookable_items():
    """Test finding items that can be booked."""
    print("\n" + "=" * 60)
    print("TEST 2: Find bookable items")
    print("=" * 60)

    with httpx.Client(headers=headers, verify=VERIFY_SSL, timeout=30.0) as client:
        response = client.get(f"{API_BASE_URL}/items", params={"limit": 50})

        if response.status_code == 200:
            items = response.json()
            bookable = [item for item in items if item.get("is_bookable") == 1]

            print(
                f"✓ Found {len(bookable)} bookable items out of {len(items)} total items"
            )

            if bookable:
                print("\nBookable items:")
                for item in bookable[:5]:  # Show first 5
                    print(f"  - ID {item['id']}: {item.get('title')}")
                    print(f"    Category: {item.get('category_title')}")
                    print(f"    Can book: {item.get('canbook')}")

                    # Get full details for first item
                    if item == bookable[0]:
                        detail_response = client.get(
                            f"{API_BASE_URL}/items/{item['id']}"
                        )
                        if detail_response.status_code == 200:
                            details = detail_response.json()
                            print(f"    Booking settings:")
                            print(
                                f"      - Max duration: {details.get('book_max_minutes') or 'unlimited'} minutes"
                            )
                            print(
                                f"      - Can overlap: {bool(details.get('book_can_overlap'))}"
                            )
                            print(
                                f"      - Is cancellable: {bool(details.get('book_is_cancellable'))}"
                            )

                return bookable[0]["id"] if bookable else None
            else:
                print("  No bookable items found!")
                print("  You may need to enable booking on some items in elabFTW")
                return None
        else:
            print(f"✗ Failed: {response.status_code} - {response.text}")
            return None


def test_create_booking(item_id):
    """Test creating a new booking."""
    if not item_id:
        print("\n⚠ Skipping create booking test - no bookable items found")
        return None

    print("\n" + "=" * 60)
    print("TEST 3: Create a new booking")
    print("=" * 60)

    # Create booking for tomorrow, 2 hours
    tomorrow = datetime.now() + timedelta(days=1)
    start = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=2)

    booking_data = {
        "item": item_id,
        "start": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "end": end.strftime("%Y-%m-%dT%H:%M:%S"),
        "title": "Test booking from API script",
    }

    print(f"Creating booking for item {item_id}")
    print(f"  Start: {booking_data['start']}")
    print(f"  End: {booking_data['end']}")

    with httpx.Client(headers=headers, verify=VERIFY_SSL, timeout=30.0) as client:
        response = client.post(f"{API_BASE_URL}/events", json=booking_data)

        if response.status_code in (200, 201):
            print("✓ Booking created successfully!")

            # Try to get the event ID from Location header
            location = response.headers.get("location", "")
            if location:
                event_id = int(location.split("/")[-1])
                print(f"  Event ID: {event_id}")

                # Get full details
                detail_response = client.get(f"{API_BASE_URL}/events/{event_id}")
                if detail_response.status_code == 200:
                    event = detail_response.json()
                    print(f"  Title: {event.get('title')}")
                    print(f"  User: {event.get('fullname')}")

                return event_id
            else:
                print("  (Could not retrieve event ID from response)")
                return None
        else:
            print(f"✗ Failed: {response.status_code} - {response.text}")
            return None


def test_update_booking(event_id):
    """Test updating a booking."""
    if not event_id:
        print("\n⚠ Skipping update booking test - no event created")
        return False

    print("\n" + "=" * 60)
    print("TEST 4: Update booking")
    print("=" * 60)

    update_data = {
        "title": "Test booking - UPDATED",
    }

    print(f"Updating booking {event_id}")
    print(f"  New title: {update_data['title']}")

    with httpx.Client(headers=headers, verify=VERIFY_SSL, timeout=30.0) as client:
        response = client.patch(f"{API_BASE_URL}/events/{event_id}", json=update_data)

        if response.status_code == 200:
            print("✓ Booking updated successfully!")
            return True
        else:
            print(f"✗ Failed: {response.status_code} - {response.text}")
            return False


def test_delete_booking(event_id):
    """Test deleting a booking."""
    if not event_id:
        print("\n⚠ Skipping delete booking test - no event created")
        return False

    print("\n" + "=" * 60)
    print("TEST 5: Delete/cancel booking")
    print("=" * 60)

    print(f"Deleting booking {event_id}")

    with httpx.Client(headers=headers, verify=VERIFY_SSL, timeout=30.0) as client:
        response = client.delete(f"{API_BASE_URL}/events/{event_id}")

        if response.status_code in (200, 204):
            print("✓ Booking deleted successfully!")
            return True
        else:
            print(f"✗ Failed: {response.status_code} - {response.text}")
            return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("elabFTW Booking API Test Suite")
    print("=" * 60)
    print(f"API URL: {API_BASE_URL}")
    print(f"SSL Verify: {VERIFY_SSL}")

    if not API_KEY:
        print("\n✗ Error: ELABFTW_API_KEY not set!")
        return

    # Test 1: List existing bookings
    test_list_events()

    # Test 2: Find bookable items
    bookable_item_id = test_get_bookable_items()

    # Test 3-5: Create, update, delete (only if we have a bookable item)
    if bookable_item_id:
        event_id = test_create_booking(bookable_item_id)

        if event_id:
            test_update_booking(event_id)

            # Ask before deleting
            print("\n" + "-" * 60)
            response = input("Delete the test booking? (y/n): ")
            if response.lower() == "y":
                test_delete_booking(event_id)
            else:
                print(f"Test booking {event_id} left in system for manual inspection")
    else:
        print("\n" + "=" * 60)
        print("⚠ WARNING: No bookable items found!")
        print("=" * 60)
        print("To enable booking on items:")
        print("1. Go to your elabFTW instance")
        print("2. Open a database item (equipment, setup, etc.)")
        print("3. Click 'Edit' → 'Advanced'")
        print("4. Enable 'Can be booked'")
        print("5. Set booking parameters (max duration, overlaps, etc.)")
        print("6. Save and re-run this test")

    print("\n" + "=" * 60)
    print("Testing complete!")
    print("=" * 60)
    print("\nIf all tests passed, you can safely integrate the booking")
    print("functionality into your MCP server using booking_implementation.py")


if __name__ == "__main__":
    main()
