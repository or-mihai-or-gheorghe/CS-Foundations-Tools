#!/usr/bin/env python3
"""
Fix empty display names and emails in Firebase database
Extracts email from UID and generates display name
"""

from firebase.config import get_database_reference, is_mock_mode

print("🔧 Fixing empty display names in Firebase...")
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

    def extract_email_from_uid(uid):
        """Convert uid back to email (uid is email with @ and . replaced by _)"""
        # Try to reconstruct email
        parts = uid.split('_')

        # Common patterns:
        # mihai_gheorghe_csie_ase_ro -> mihai.gheorghe@csie.ase.ro
        # student_ase_ro -> student@ase.ro

        if len(parts) >= 3 and parts[-2] == 'ase' and parts[-1] == 'ro':
            # Likely an ase.ro email
            name_parts = parts[:-3]  # Remove domain parts
            domain_parts = parts[-3:]  # Get domain parts

            name = '.'.join(name_parts)
            domain = '.'.join(domain_parts)
            return f"{name}@{domain}"

        return None

    def fix_entry(path, uid, entry):
        """Fix a single leaderboard entry"""
        display_name = entry.get('display_name', '')
        email = entry.get('email', '')

        if not display_name or not email:
            # Extract email from UID
            extracted_email = extract_email_from_uid(uid)

            if extracted_email:
                if not email:
                    entry['email'] = extracted_email

                if not display_name:
                    # Generate display name from email
                    name_part = extracted_email.split('@')[0]
                    display_name = name_part.replace('.', ' ').title()
                    entry['display_name'] = display_name

                print(f"  Fixed {uid}:")
                print(f"    Email: {extracted_email}")
                print(f"    Display: {display_name}")

                # Update in Firebase
                entry_ref = get_database_reference(path)
                entry_ref.set(entry)

                return True

        return False

    fixed_count = 0

    # Process each game's leaderboard
    for game_slug, game_data in leaderboard_data.items():
        if game_slug == 'global':
            continue  # Process separately

        print(f"\nProcessing {game_slug}...")

        # Process all_time leaderboard
        if 'all_time' in game_data:
            for uid, entry in game_data['all_time'].items():
                if fix_entry(f"/leaderboard/{game_slug}/all_time/{uid}", uid, entry):
                    fixed_count += 1

        # Process by_difficulty leaderboard
        if 'by_difficulty' in game_data:
            for difficulty, diff_data in game_data['by_difficulty'].items():
                for uid, entry in diff_data.items():
                    if fix_entry(f"/leaderboard/{game_slug}/by_difficulty/{difficulty}/{uid}", uid, entry):
                        fixed_count += 1

    # Process global leaderboard
    if 'global' in leaderboard_data and 'all_time' in leaderboard_data['global']:
        print(f"\nProcessing global leaderboard...")

        for uid, entry in leaderboard_data['global']['all_time'].items():
            if fix_entry(f"/leaderboard/global/all_time/{uid}", uid, entry):
                fixed_count += 1

    print()
    print(f"✅ Fixed {fixed_count} entries with missing data")

    if fixed_count == 0:
        print("   No issues found - all entries have display names and emails!")

except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
