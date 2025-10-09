#!/usr/bin/env python3
"""
Clean up leaderboard entries from invalid email domains
Removes any entries that don't end with @ase.ro or .ase.ro
"""

from firebase.config import get_database_reference, is_mock_mode

def validate_ase_domain(email: str) -> bool:
    """Check if email is valid @ase.ro domain"""
    if not email:
        return False
    email_lower = email.lower()
    return email_lower.endswith(".ase.ro") or email_lower.endswith("@ase.ro")

print("🧹 Cleaning up invalid email domains from leaderboard...")
print()

if is_mock_mode():
    print("⚠️  Running in mock mode - no changes will be made to real Firebase")
    print("   Set use_mock_auth = false in secrets.toml to clean production data")
    exit(1)

try:
    # Get all leaderboard data
    leaderboard_ref = get_database_reference("/leaderboard")
    leaderboard_data = leaderboard_ref.get()

    if not leaderboard_data:
        print("✅ No leaderboard data found")
        exit(0)

    removed_count = 0

    # Process each game's leaderboard
    for game_slug, game_data in leaderboard_data.items():
        if game_slug == 'global':
            continue  # Process separately

        print(f"\nProcessing {game_slug}...")

        # Process all_time leaderboard
        if 'all_time' in game_data:
            for uid, entry in list(game_data['all_time'].items()):
                email = entry.get('email', '')

                if email and not validate_ase_domain(email):
                    print(f"  ⛔ Removing invalid: {email} (uid: {uid})")

                    # Delete from Firebase
                    entry_ref = get_database_reference(f"/leaderboard/{game_slug}/all_time/{uid}")
                    entry_ref.delete()

                    removed_count += 1

        # Process by_difficulty leaderboard
        if 'by_difficulty' in game_data:
            for difficulty, diff_data in game_data['by_difficulty'].items():
                for uid, entry in list(diff_data.items()):
                    email = entry.get('email', '')

                    if email and not validate_ase_domain(email):
                        print(f"  ⛔ Removing invalid ({difficulty}): {email} (uid: {uid})")

                        entry_ref = get_database_reference(f"/leaderboard/{game_slug}/by_difficulty/{difficulty}/{uid}")
                        entry_ref.delete()

                        removed_count += 1

    # Process global leaderboard
    if 'global' in leaderboard_data and 'all_time' in leaderboard_data['global']:
        print(f"\nProcessing global leaderboard...")

        for uid, entry in list(leaderboard_data['global']['all_time'].items()):
            email = entry.get('email', '')

            if email and not validate_ase_domain(email):
                print(f"  ⛔ Removing invalid: {email} (uid: {uid})")

                entry_ref = get_database_reference(f"/leaderboard/global/all_time/{uid}")
                entry_ref.delete()

                removed_count += 1

    print()
    if removed_count > 0:
        print(f"✅ Removed {removed_count} invalid entries")
    else:
        print("✅ No invalid entries found - all emails are valid @ase.ro domains")

except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
