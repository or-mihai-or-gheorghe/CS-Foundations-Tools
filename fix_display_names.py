#!/usr/bin/env python3
"""
Fix corrupted display names in Firebase database
Removes HTML tags and cleans up user display names
"""

from firebase.config import get_database_reference, is_mock_mode
import re

print("🔧 Fixing display names in Firebase...")
print()

if is_mock_mode():
    print("⚠️  Running in mock mode - no changes will be made to real Firebase")
    print("   Set use_mock_auth = false in secrets.toml to fix production data")
    exit(1)

try:
    # Get all leaderboard data
    leaderboard_ref = get_database_reference("/leaderboard")
    leaderboard_data = leaderboard_ref.get()

    if not leaderboard_data:
        print("✅ No leaderboard data found")
        exit(0)

    fixed_count = 0

    # Process each game's leaderboard
    for game_slug, game_data in leaderboard_data.items():
        print(f"\nProcessing {game_slug}...")

        # Process all_time leaderboard
        if 'all_time' in game_data:
            for uid, entry in game_data['all_time'].items():
                display_name = entry.get('display_name', '')

                # Check if display_name contains HTML tags
                if '<' in display_name or '>' in display_name:
                    # Extract just the text content
                    clean_name = re.sub(r'<[^>]+>', '', display_name).strip()

                    # If still empty, use email
                    if not clean_name:
                        email = entry.get('email', '')
                        clean_name = email.split('@')[0] if email else 'Unknown'

                    print(f"  Fixing: '{display_name[:50]}...' -> '{clean_name}'")

                    # Update in database
                    entry_ref = get_database_reference(f"/leaderboard/{game_slug}/all_time/{uid}")
                    entry['display_name'] = clean_name
                    entry_ref.set(entry)

                    fixed_count += 1

        # Process by_difficulty leaderboard
        if 'by_difficulty' in game_data:
            for difficulty, diff_data in game_data['by_difficulty'].items():
                for uid, entry in diff_data.items():
                    display_name = entry.get('display_name', '')

                    if '<' in display_name or '>' in display_name:
                        clean_name = re.sub(r'<[^>]+>', '', display_name).strip()

                        if not clean_name:
                            email = entry.get('email', '')
                            clean_name = email.split('@')[0] if email else 'Unknown'

                        print(f"  Fixing ({difficulty}): '{display_name[:50]}...' -> '{clean_name}'")

                        entry_ref = get_database_reference(f"/leaderboard/{game_slug}/by_difficulty/{difficulty}/{uid}")
                        entry['display_name'] = clean_name
                        entry_ref.set(entry)

                        fixed_count += 1

    # Process global leaderboard
    if 'global' in leaderboard_data and 'all_time' in leaderboard_data['global']:
        print(f"\nProcessing global leaderboard...")

        for uid, entry in leaderboard_data['global']['all_time'].items():
            display_name = entry.get('display_name', '')

            if '<' in display_name or '>' in display_name:
                clean_name = re.sub(r'<[^>]+>', '', display_name).strip()

                if not clean_name:
                    email = entry.get('email', '')
                    clean_name = email.split('@')[0] if email else 'Unknown'

                print(f"  Fixing: '{display_name[:50]}...' -> '{clean_name}'")

                entry_ref = get_database_reference(f"/leaderboard/global/all_time/{uid}")
                entry['display_name'] = clean_name
                entry_ref.set(entry)

                fixed_count += 1

    print()
    print(f"✅ Fixed {fixed_count} corrupted display names")

    if fixed_count == 0:
        print("   No issues found - all display names are clean!")

except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
