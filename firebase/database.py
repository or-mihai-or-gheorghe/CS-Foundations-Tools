# firebase/database.py
"""
Firebase Realtime Database operations
Handles saving game results, updating leaderboards, and querying data
Supports both real Firebase and mock database for local development
"""

import streamlit as st
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import uuid
from .config import is_mock_mode, get_database_reference
from .mock_auth import get_mock_database, save_to_mock_database, get_from_mock_database

logger = logging.getLogger(__name__)


def save_game_result(user_uid: str, game_slug: str, game_data: Dict) -> bool:
    """
    Save a game result to the database

    Args:
        user_uid: User's unique ID
        game_slug: Game identifier (e.g., "binary_speed_challenge")
        game_data: Game data including settings, results, and history

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Generate unique game ID
        game_id = f"{game_slug}_{user_uid}_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"

        # Prepare data for saving
        data_to_save = {
            "user_uid": user_uid,
            "game_id": game_id,
            **game_data,
            "timestamp": game_data.get("timestamp", datetime.utcnow().isoformat())
        }

        if is_mock_mode():
            # Save to mock database
            path = f"games/{game_slug}/{game_id}"
            success = save_to_mock_database(path, data_to_save)

            if success:
                # Also update user stats and leaderboard in mock mode
                _update_user_stats_mock(user_uid, game_slug, game_data)
                _update_leaderboard_mock(user_uid, game_slug, game_data)

            logger.info(f"Mock database: saved game {game_id} for user {user_uid}")
            return success

        else:
            # Save to real Firebase
            db_ref = get_database_reference(f"games/{game_slug}/{game_id}")
            db_ref.set(data_to_save)

            # Update user stats and leaderboard
            update_user_stats(user_uid, game_slug, game_data)
            update_leaderboard(user_uid, game_slug, game_data)

            logger.info(f"Firebase: saved game {game_id} for user {user_uid}")
            return True

    except Exception as e:
        logger.error(f"Failed to save game result: {e}")
        return False


def update_user_stats(user_uid: str, game_slug: str, game_result: Dict) -> bool:
    """
    Update user statistics

    Args:
        user_uid: User's unique ID
        game_slug: Game identifier
        game_result: Game result data

    Returns:
        bool: True if successful
    """
    try:
        if is_mock_mode():
            return _update_user_stats_mock(user_uid, game_slug, game_result)

        # Get current user stats
        user_ref = get_database_reference(f"users/{user_uid}")
        current_stats = user_ref.get() or {}

        # Update stats
        results = game_result.get("results", {})

        current_stats["total_games"] = current_stats.get("total_games", 0) + 1
        current_stats["total_score"] = current_stats.get("total_score", 0) + results.get("score", 0)
        current_stats["last_played"] = datetime.utcnow().isoformat()

        # Per-game stats
        if "games_breakdown" not in current_stats:
            current_stats["games_breakdown"] = {}

        current_stats["games_breakdown"][game_slug] = current_stats["games_breakdown"].get(game_slug, 0) + 1

        # Save updated stats
        user_ref.set(current_stats)

        logger.info(f"Updated user stats for {user_uid}")
        return True

    except Exception as e:
        logger.error(f"Failed to update user stats: {e}")
        return False


def _update_user_stats_mock(user_uid: str, game_slug: str, game_result: Dict) -> bool:
    """Mock version of update_user_stats"""
    try:
        mock_db = get_mock_database()

        if "users" not in mock_db:
            mock_db["users"] = {}

        if user_uid not in mock_db["users"]:
            mock_db["users"][user_uid] = {
                "total_games": 0,
                "total_score": 0,
                "games_breakdown": {}
            }

        user_stats = mock_db["users"][user_uid]
        results = game_result.get("results", {})

        user_stats["total_games"] += 1
        user_stats["total_score"] += results.get("score", 0)
        user_stats["last_played"] = datetime.utcnow().isoformat()
        user_stats["games_breakdown"][game_slug] = user_stats["games_breakdown"].get(game_slug, 0) + 1

        return True

    except Exception as e:
        logger.error(f"Mock: failed to update user stats: {e}")
        return False


def update_leaderboard(user_uid: str, game_slug: str, game_result: Dict) -> bool:
    """
    Update leaderboard entries

    Args:
        user_uid: User's unique ID
        game_slug: Game identifier
        game_result: Game result data

    Returns:
        bool: True if successful
    """
    try:
        if is_mock_mode():
            return _update_leaderboard_mock(user_uid, game_slug, game_result)

        results = game_result.get("results", {})
        settings = game_result.get("settings", {})
        difficulty = settings.get("difficulty", "Unknown")

        # Update game-specific leaderboard
        leaderboard_ref = get_database_reference(f"leaderboard/{game_slug}/all_time/{user_uid}")
        current_data = leaderboard_ref.get() or {}

        # Calculate aggregated stats
        total_score = current_data.get("total_score", 0) + results.get("score", 0)
        games_played = current_data.get("games_played", 0) + 1
        total_correct = current_data.get("total_correct", 0) + results.get("correct_count", 0)
        total_questions = current_data.get("total_questions", 0) + results.get("total_count", 0)
        avg_accuracy = (total_correct / total_questions * 100) if total_questions > 0 else 0
        best_single_score = max(current_data.get("best_single_score", 0), results.get("score", 0))
        best_streak = max(current_data.get("best_streak", 0), results.get("best_streak", 0))

        # Get user info - use get_current_user to support both auth methods
        from .auth import get_current_user as get_user
        user_data = get_user() or {}

        leaderboard_entry = {
            "email": user_data.get("email", ""),
            "display_name": user_data.get("display_name", "Unknown"),
            "total_score": total_score,
            "games_played": games_played,
            "best_single_score": best_single_score,
            "avg_accuracy": round(avg_accuracy, 1),
            "best_streak": best_streak,
            "last_updated": datetime.utcnow().isoformat()
        }

        leaderboard_ref.set(leaderboard_entry)

        # Update difficulty-specific leaderboard
        diff_ref = get_database_reference(f"leaderboard/{game_slug}/by_difficulty/{difficulty}/{user_uid}")
        diff_ref.set(leaderboard_entry)

        # Update global leaderboard (reuse user_data from above)
        global_ref = get_database_reference(f"leaderboard/global/all_time/{user_uid}")
        global_data = global_ref.get() or {}

        global_data["email"] = user_data.get("email", "")
        global_data["display_name"] = user_data.get("display_name", "Unknown")
        global_data["total_score_all_games"] = global_data.get("total_score_all_games", 0) + results.get("score", 0)
        global_data["total_games_all_types"] = global_data.get("total_games_all_types", 0) + 1

        if "games_breakdown" not in global_data:
            global_data["games_breakdown"] = {}

        global_data["games_breakdown"][game_slug] = global_data["games_breakdown"].get(game_slug, 0) + 1
        global_data["last_updated"] = datetime.utcnow().isoformat()

        global_ref.set(global_data)

        logger.info(f"Updated leaderboard for {user_uid} in {game_slug}")
        return True

    except Exception as e:
        logger.error(f"Failed to update leaderboard: {e}")
        return False


def _update_leaderboard_mock(user_uid: str, game_slug: str, game_result: Dict) -> bool:
    """Mock version of update_leaderboard"""
    try:
        mock_db = get_mock_database()
        results = game_result.get("results", {})
        settings = game_result.get("settings", {})
        difficulty = settings.get("difficulty", "Unknown")

        # Ensure structure exists
        if game_slug not in mock_db["leaderboard"]:
            mock_db["leaderboard"][game_slug] = {
                "all_time": {},
                "by_difficulty": {"Easy": {}, "Medium": {}, "Hard": {}, "Expert": {}},
                "monthly": {}
            }

        # Update game-specific leaderboard
        leaderboard = mock_db["leaderboard"][game_slug]["all_time"]

        if user_uid not in leaderboard:
            leaderboard[user_uid] = {
                "total_score": 0,
                "games_played": 0,
                "total_correct": 0,
                "total_questions": 0,
                "best_single_score": 0,
                "best_streak": 0
            }

        entry = leaderboard[user_uid]
        entry["total_score"] += results.get("score", 0)
        entry["games_played"] += 1
        entry["total_correct"] += results.get("correct_count", 0)
        entry["total_questions"] += results.get("total_count", 0)
        entry["avg_accuracy"] = round((entry["total_correct"] / entry["total_questions"] * 100) if entry["total_questions"] > 0 else 0, 1)
        entry["best_single_score"] = max(entry["best_single_score"], results.get("score", 0))
        entry["best_streak"] = max(entry["best_streak"], results.get("best_streak", 0))

        # Get user info - use get_current_user to support both auth methods
        from .auth import get_current_user as get_user
        user_data = get_user() or {}
        entry["email"] = user_data.get("email", "")
        entry["display_name"] = user_data.get("display_name", "Unknown")

        # Update difficulty-specific
        mock_db["leaderboard"][game_slug]["by_difficulty"][difficulty][user_uid] = entry.copy()

        # Update global
        if "global" not in mock_db["leaderboard"]:
            mock_db["leaderboard"]["global"] = {"all_time": {}}

        global_lb = mock_db["leaderboard"]["global"]["all_time"]

        if user_uid not in global_lb:
            global_lb[user_uid] = {
                "total_score_all_games": 0,
                "total_games_all_types": 0,
                "games_breakdown": {}
            }

        global_lb[user_uid]["total_score_all_games"] += results.get("score", 0)
        global_lb[user_uid]["total_games_all_types"] += 1
        global_lb[user_uid]["games_breakdown"][game_slug] = global_lb[user_uid]["games_breakdown"].get(game_slug, 0) + 1
        global_lb[user_uid]["email"] = user_data.get("email", "")
        global_lb[user_uid]["display_name"] = user_data.get("display_name", "Unknown")

        return True

    except Exception as e:
        logger.error(f"Mock: failed to update leaderboard: {e}")
        return False


def get_leaderboard(game_slug: Optional[str] = None, filters: Optional[Dict] = None, limit: int = 50) -> List[Dict]:
    """
    Get leaderboard data

    Args:
        game_slug: Game identifier (None for global leaderboard)
        filters: Optional filters (difficulty, date_range, user_search)
        limit: Maximum number of entries to return

    Returns:
        List[Dict]: Leaderboard entries sorted by score
    """
    try:
        if filters is None:
            filters = {}

        if is_mock_mode():
            return _get_leaderboard_mock(game_slug, filters, limit)

        # Determine path
        if game_slug:
            difficulty = filters.get("difficulty")
            if difficulty:
                path = f"leaderboard/{game_slug}/by_difficulty/{difficulty}"
            else:
                path = f"leaderboard/{game_slug}/all_time"
        else:
            path = "leaderboard/global/all_time"

        # Get data
        db_ref = get_database_reference(path)
        data = db_ref.get() or {}

        # Convert to list
        leaderboard = []
        for uid, entry in data.items():
            entry["uid"] = uid
            leaderboard.append(entry)

        # Apply user search filter
        user_search = filters.get("user_search", "").lower()
        if user_search:
            leaderboard = [
                entry for entry in leaderboard
                if user_search in entry.get("email", "").lower() or
                   user_search in entry.get("display_name", "").lower()
            ]

        # Sort by score
        sort_key = "total_score_all_games" if not game_slug else "total_score"
        leaderboard.sort(key=lambda x: x.get(sort_key, 0), reverse=True)

        # Add rank
        for idx, entry in enumerate(leaderboard[:limit], 1):
            entry["rank"] = idx

        return leaderboard[:limit]

    except Exception as e:
        logger.error(f"Failed to get leaderboard: {e}")
        return []


def _get_leaderboard_mock(game_slug: Optional[str], filters: Optional[Dict], limit: int) -> List[Dict]:
    """Mock version of get_leaderboard"""
    try:
        mock_db = get_mock_database()

        if game_slug:
            difficulty = filters.get("difficulty") if filters else None
            if difficulty:
                data = mock_db["leaderboard"].get(game_slug, {}).get("by_difficulty", {}).get(difficulty, {})
            else:
                data = mock_db["leaderboard"].get(game_slug, {}).get("all_time", {})
        else:
            data = mock_db["leaderboard"].get("global", {}).get("all_time", {})

        # Convert to list
        leaderboard = []
        for uid, entry in data.items():
            entry_copy = entry.copy()
            entry_copy["uid"] = uid
            leaderboard.append(entry_copy)

        # Apply user search filter
        if filters and filters.get("user_search"):
            user_search = filters["user_search"].lower()
            leaderboard = [
                entry for entry in leaderboard
                if user_search in entry.get("email", "").lower() or
                   user_search in entry.get("display_name", "").lower()
            ]

        # Sort by score
        sort_key = "total_score_all_games" if not game_slug else "total_score"
        leaderboard.sort(key=lambda x: x.get(sort_key, 0), reverse=True)

        # Add rank
        for idx, entry in enumerate(leaderboard[:limit], 1):
            entry["rank"] = idx

        return leaderboard[:limit]

    except Exception as e:
        logger.error(f"Mock: failed to get leaderboard: {e}")
        return []


def get_user_stats(user_uid: str, game_slug: Optional[str] = None) -> Optional[Dict]:
    """
    Get user statistics

    Args:
        user_uid: User's unique ID
        game_slug: Optional game identifier (None for all games)

    Returns:
        Dict: User statistics
    """
    try:
        if is_mock_mode():
            mock_db = get_mock_database()
            return mock_db.get("users", {}).get(user_uid)

        user_ref = get_database_reference(f"users/{user_uid}")
        return user_ref.get()

    except Exception as e:
        logger.error(f"Failed to get user stats: {e}")
        return None


def get_user_game_history(user_uid: str, game_slug: Optional[str] = None, limit: int = 10) -> List[Dict]:
    """
    Get user's game history

    Args:
        user_uid: User's unique ID
        game_slug: Optional game identifier (None for all games)
        limit: Maximum number of games to return

    Returns:
        List[Dict]: Game history sorted by timestamp (most recent first)
    """
    try:
        if is_mock_mode():
            # Mock implementation
            return []

        # Query games
        if game_slug:
            path = f"games/{game_slug}"
        else:
            path = "games"

        db_ref = get_database_reference(path)
        all_games = db_ref.get() or {}

        # Filter by user
        user_games = []
        for game_id, game_data in all_games.items():
            if isinstance(game_data, dict) and game_data.get("user_uid") == user_uid:
                game_data["game_id"] = game_id
                user_games.append(game_data)

        # Sort by timestamp
        user_games.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return user_games[:limit]

    except Exception as e:
        logger.error(f"Failed to get user game history: {e}")
        return []
