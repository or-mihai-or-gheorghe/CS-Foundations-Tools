# firebase/__init__.py
"""
Firebase integration module for CS Foundations Tools
Handles authentication, database operations, and configuration
"""

from .config import get_firebase_config, is_mock_mode
from .auth import sign_in, sign_out, get_current_user, validate_ase_email
from .database import (
    save_game_result,
    get_leaderboard,
    get_user_stats,
    get_user_game_history
)

__all__ = [
    'get_firebase_config',
    'is_mock_mode',
    'sign_in',
    'sign_out',
    'get_current_user',
    'validate_ase_email',
    'save_game_result',
    'get_leaderboard',
    'get_user_stats',
    'get_user_game_history'
]
