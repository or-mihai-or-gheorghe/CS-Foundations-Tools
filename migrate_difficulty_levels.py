#!/usr/bin/env python3
"""
Migration script to update difficulty levels in Firebase database.

Old system (4 levels): Easy, Medium, Hard, Expert
New system (3 levels): Easy, Advanced, Expert

Migration mapping:
- Easy → Easy (no change)
- Medium → Advanced (rename)
- Hard → Expert (merge into Expert)
- Expert → Expert (keep as is)

This script updates the 'binary_speed_challenge' game records in Firebase.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from firebase.config import get_firebase_app
from firebase.database import get_database
import firebase_admin
from firebase_admin import db
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Difficulty mapping
DIFFICULTY_MAPPING = {
    "Easy": "Easy",
    "Medium": "Advanced",
    "Hard": "Expert",
    "Expert": "Expert"
}

def migrate_game_results():
    """
    Migrate all Binary Speed Challenge game results to new difficulty levels.

    Updates:
    - games/binary_speed_challenge/*/settings/difficulty
    - Preserves all other data
    """
    try:
        # Initialize Firebase
        app = get_firebase_app()
        database = get_database()

        logger.info("Starting difficulty level migration for Binary Speed Challenge")

        # Get reference to games
        games_ref = db.reference('games/binary_speed_challenge', app=app)

        # Fetch all games
        all_games = games_ref.get()

        if not all_games:
            logger.info("No games found in database")
            return

        total_games = len(all_games)
        updated_count = 0
        skipped_count = 0

        logger.info(f"Found {total_games} games to process")

        # Process each game
        for game_id, game_data in all_games.items():
            try:
                # Check if game has settings and difficulty
                if not isinstance(game_data, dict):
                    logger.warning(f"Skipping game {game_id}: invalid data structure")
                    skipped_count += 1
                    continue

                settings = game_data.get('settings', {})
                current_difficulty = settings.get('difficulty')

                if not current_difficulty:
                    logger.warning(f"Skipping game {game_id}: no difficulty field")
                    skipped_count += 1
                    continue

                # Check if migration needed
                if current_difficulty in DIFFICULTY_MAPPING:
                    new_difficulty = DIFFICULTY_MAPPING[current_difficulty]

                    if current_difficulty != new_difficulty:
                        # Update difficulty
                        games_ref.child(game_id).child('settings').update({
                            'difficulty': new_difficulty
                        })

                        logger.info(f"✓ Game {game_id[:8]}...: {current_difficulty} → {new_difficulty}")
                        updated_count += 1
                    else:
                        # No change needed
                        skipped_count += 1
                else:
                    logger.warning(f"Skipping game {game_id}: unknown difficulty '{current_difficulty}'")
                    skipped_count += 1

            except Exception as e:
                logger.error(f"Error processing game {game_id}: {str(e)}")
                skipped_count += 1

        # Summary
        logger.info("=" * 60)
        logger.info("Migration completed!")
        logger.info(f"Total games: {total_games}")
        logger.info(f"Updated: {updated_count}")
        logger.info(f"Skipped: {skipped_count}")
        logger.info("=" * 60)

        # Show mapping summary
        logger.info("\nDifficulty mapping applied:")
        for old, new in DIFFICULTY_MAPPING.items():
            arrow = "→" if old != new else "="
            logger.info(f"  {old} {arrow} {new}")

    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        raise


def migrate_leaderboard():
    """
    Migrate leaderboard entries to new difficulty levels.

    Note: Leaderboard entries are denormalized, so we update them separately.
    """
    try:
        app = get_firebase_app()

        logger.info("\nMigrating leaderboard entries...")

        # Get reference to leaderboard
        leaderboard_ref = db.reference('leaderboard/binary_speed_challenge', app=app)

        # Fetch all leaderboard entries
        all_entries = leaderboard_ref.get()

        if not all_entries:
            logger.info("No leaderboard entries found")
            return

        total_entries = len(all_entries)
        updated_count = 0
        skipped_count = 0

        logger.info(f"Found {total_entries} leaderboard entries to process")

        # Process each entry
        for entry_id, entry_data in all_entries.items():
            try:
                if not isinstance(entry_data, dict):
                    logger.warning(f"Skipping entry {entry_id}: invalid data structure")
                    skipped_count += 1
                    continue

                current_difficulty = entry_data.get('difficulty')

                if not current_difficulty:
                    logger.warning(f"Skipping entry {entry_id}: no difficulty field")
                    skipped_count += 1
                    continue

                # Check if migration needed
                if current_difficulty in DIFFICULTY_MAPPING:
                    new_difficulty = DIFFICULTY_MAPPING[current_difficulty]

                    if current_difficulty != new_difficulty:
                        # Update difficulty
                        leaderboard_ref.child(entry_id).update({
                            'difficulty': new_difficulty
                        })

                        logger.info(f"✓ Leaderboard {entry_id[:8]}...: {current_difficulty} → {new_difficulty}")
                        updated_count += 1
                    else:
                        skipped_count += 1
                else:
                    logger.warning(f"Skipping entry {entry_id}: unknown difficulty '{current_difficulty}'")
                    skipped_count += 1

            except Exception as e:
                logger.error(f"Error processing leaderboard entry {entry_id}: {str(e)}")
                skipped_count += 1

        logger.info(f"\nLeaderboard migration: {updated_count} updated, {skipped_count} skipped")

    except Exception as e:
        logger.error(f"Leaderboard migration failed: {str(e)}")
        # Don't raise - leaderboard migration is optional


def main():
    """Run migration"""
    print("=" * 60)
    print("Binary Speed Challenge - Difficulty Level Migration")
    print("=" * 60)
    print()
    print("This script will update difficulty levels:")
    print("  Easy   → Easy")
    print("  Medium → Advanced")
    print("  Hard   → Expert")
    print("  Expert → Expert (unchanged)")
    print()

    response = input("Proceed with migration? (yes/no): ").strip().lower()

    if response != 'yes':
        print("Migration cancelled.")
        return

    print("\nStarting migration...\n")

    try:
        # Migrate game results
        migrate_game_results()

        # Migrate leaderboard (if exists)
        migrate_leaderboard()

        print("\n✅ Migration completed successfully!")

    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
