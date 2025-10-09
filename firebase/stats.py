# firebase/stats.py
"""
Global game statistics tracking
Tracks all games played (authenticated and anonymous)
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
from .config import get_database_reference, is_mock_mode
import logging

logger = logging.getLogger(__name__)


def record_game_played(game_slug: str, authenticated: bool = False):
    """
    Record a game played in global stats

    Args:
        game_slug: Game identifier
        authenticated: Whether the game was played by authenticated user
    """
    try:
        if is_mock_mode():
            _record_game_mock(game_slug, authenticated)
        else:
            _record_game_firebase(game_slug, authenticated)

        return True

    except Exception as e:
        logger.error(f"Failed to record game stats: {e}")
        return False


def _record_game_firebase(game_slug: str, authenticated: bool):
    """Record game in Firebase"""
    # Get stats reference
    stats_ref = get_database_reference("/stats/games")
    stats = stats_ref.get() or {}

    # Initialize if needed
    if game_slug not in stats:
        stats[game_slug] = {
            "total_games": 0,
            "authenticated_games": 0,
            "anonymous_games": 0,
            "recent_games": []  # List of timestamps
        }

    # Update counts
    stats[game_slug]["total_games"] += 1
    if authenticated:
        stats[game_slug]["authenticated_games"] += 1
    else:
        stats[game_slug]["anonymous_games"] += 1

    # Add timestamp to recent games
    timestamp = datetime.utcnow().isoformat()
    recent = stats[game_slug].get("recent_games", [])
    recent.append(timestamp)

    # Keep only last 1000 games (to prevent unbounded growth)
    if len(recent) > 1000:
        recent = recent[-1000:]

    stats[game_slug]["recent_games"] = recent

    # Update last played
    stats[game_slug]["last_played"] = timestamp

    # Save back to Firebase
    stats_ref.set(stats)


def _record_game_mock(game_slug: str, authenticated: bool):
    """Record game in mock database"""
    from .mock_auth import get_mock_database

    mock_db = get_mock_database()

    if "stats" not in mock_db:
        mock_db["stats"] = {"games": {}}

    if game_slug not in mock_db["stats"]["games"]:
        mock_db["stats"]["games"][game_slug] = {
            "total_games": 0,
            "authenticated_games": 0,
            "anonymous_games": 0,
            "recent_games": []
        }

    # Update counts
    mock_db["stats"]["games"][game_slug]["total_games"] += 1
    if authenticated:
        mock_db["stats"]["games"][game_slug]["authenticated_games"] += 1
    else:
        mock_db["stats"]["games"][game_slug]["anonymous_games"] += 1

    # Add timestamp
    timestamp = datetime.utcnow().isoformat()
    mock_db["stats"]["games"][game_slug]["recent_games"].append(timestamp)
    mock_db["stats"]["games"][game_slug]["last_played"] = timestamp


def get_global_stats() -> Dict:
    """
    Get global game statistics

    Returns:
        Dict: Global statistics including all-time and recent counts
    """
    try:
        if is_mock_mode():
            return _get_stats_mock()
        else:
            return _get_stats_firebase()

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {}


def _get_stats_firebase() -> Dict:
    """Get stats from Firebase"""
    stats_ref = get_database_reference("/stats/games")
    stats = stats_ref.get() or {}

    return _process_stats(stats)


def _get_stats_mock() -> Dict:
    """Get stats from mock database"""
    from .mock_auth import get_mock_database

    mock_db = get_mock_database()
    stats = mock_db.get("stats", {}).get("games", {})

    return _process_stats(stats)


def _process_stats(raw_stats: Dict) -> Dict:
    """
    Process raw stats and calculate aggregates

    Args:
        raw_stats: Raw stats from database

    Returns:
        Dict: Processed statistics with aggregates
    """
    # Calculate aggregates
    total_all_games = 0
    total_authenticated = 0
    total_anonymous = 0
    recent_7_days = 0

    # Calculate 7 days ago
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    per_game_stats = {}

    for game_slug, game_stats in raw_stats.items():
        total_all_games += game_stats.get("total_games", 0)
        total_authenticated += game_stats.get("authenticated_games", 0)
        total_anonymous += game_stats.get("anonymous_games", 0)

        # Count recent games (last 7 days)
        recent_games = game_stats.get("recent_games", [])
        recent_count = 0

        for timestamp_str in recent_games:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                if timestamp >= seven_days_ago:
                    recent_count += 1
            except:
                pass

        recent_7_days += recent_count

        # Per-game stats
        per_game_stats[game_slug] = {
            "total_games": game_stats.get("total_games", 0),
            "authenticated_games": game_stats.get("authenticated_games", 0),
            "anonymous_games": game_stats.get("anonymous_games", 0),
            "recent_7_days": recent_count,
            "last_played": game_stats.get("last_played", "Never")
        }

    return {
        "global": {
            "total_all_games": total_all_games,
            "total_authenticated": total_authenticated,
            "total_anonymous": total_anonymous,
            "recent_7_days": recent_7_days
        },
        "by_game": per_game_stats
    }
