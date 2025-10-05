# tools/games/game_utils.py

import random
from typing import List, Tuple, Dict

# Difficulty configurations
DIFFICULTY_CONFIG = {
    "Easy": {
        "bit_min": 4,
        "bit_max": 6,
        "decimal_max": 63,
        "points": 10,
        "description": "4-6 bits (0-63)"
    },
    "Medium": {
        "bit_min": 7,
        "bit_max": 10,
        "decimal_max": 1023,
        "points": 20,
        "description": "7-10 bits (64-1023)"
    },
    "Hard": {
        "bit_min": 11,
        "bit_max": 14,
        "decimal_max": 16383,
        "points": 30,
        "description": "11-14 bits (1024-16383)"
    },
    "Expert": {
        "bit_min": 15,
        "bit_max": 16,
        "decimal_max": 65535,
        "points": 50,
        "description": "15-16 bits (16384-65535)"
    }
}

def generate_random_number(difficulty: str) -> Tuple[int, str]:
    """
    Generate a random number based on difficulty level.
    Returns (decimal_value, binary_string)
    """
    config = DIFFICULTY_CONFIG[difficulty]
    bit_length = random.randint(config["bit_min"], config["bit_max"])

    # Generate random number with specific bit length
    # Ensure MSB is 1 to guarantee the bit length
    min_val = 1 << (bit_length - 1)  # 2^(n-1)
    max_val = (1 << bit_length) - 1  # 2^n - 1

    decimal_val = random.randint(min_val, max_val)
    binary_str = bin(decimal_val)[2:]  # Remove '0b' prefix

    return decimal_val, binary_str

def generate_distractors_decimal(correct: int, count: int = 3) -> List[int]:
    """Generate plausible wrong answers for binary→decimal conversion"""
    distractors = set()

    # Strategy 1: Off-by-one errors
    distractors.add(correct + 1)
    distractors.add(correct - 1)

    # Strategy 2: Bit flip errors (flip random bit)
    bit_length = correct.bit_length()
    for i in range(min(3, bit_length)):
        distractors.add(correct ^ (1 << random.randint(0, bit_length - 1)))

    # Strategy 3: Magnitude errors
    distractors.add(correct * 2)
    distractors.add(correct // 2)
    if correct > 10:
        distractors.add(correct + random.randint(5, 15))
        distractors.add(correct - random.randint(5, 15))

    # Remove negative numbers and the correct answer
    distractors = {d for d in distractors if d >= 0 and d != correct}

    # Select random subset
    if len(distractors) < count:
        # Add more random numbers in similar range
        while len(distractors) < count:
            noise = random.randint(-50, 50)
            candidate = max(0, correct + noise)
            if candidate != correct:
                distractors.add(candidate)

    return random.sample(list(distractors), min(count, len(distractors)))

def generate_distractors_binary(correct: str, count: int = 3) -> List[str]:
    """Generate plausible wrong answers for decimal→binary conversion"""
    distractors = set()
    correct_int = int(correct, 2)
    bit_length = len(correct)

    # Strategy 1: Flip random bits
    for _ in range(5):
        flipped = correct_int ^ (1 << random.randint(0, bit_length - 1))
        distractors.add(bin(flipped)[2:].zfill(bit_length))

    # Strategy 2: Off-by-one in decimal
    distractors.add(bin(correct_int + 1)[2:].zfill(bit_length))
    distractors.add(bin(max(0, correct_int - 1))[2:].zfill(bit_length))

    # Strategy 3: Swap adjacent bits
    temp = list(correct)
    if len(temp) > 1:
        idx = random.randint(0, len(temp) - 2)
        temp[idx], temp[idx + 1] = temp[idx + 1], temp[idx]
        distractors.add(''.join(temp))

    # Remove correct answer
    distractors.discard(correct)

    # Ensure all have same length (for visual consistency)
    distractors = {d.zfill(bit_length) for d in distractors if d}

    return random.sample(list(distractors), min(count, len(distractors)))

def calculate_score(base_points: int, answer_time: float, streak: int) -> int:
    """
    Calculate score for an answer.
    - Base points from difficulty
    - Speed bonus if < 3 seconds
    - Streak multiplier
    """
    score = base_points

    # Speed bonus
    if answer_time < 3.0:
        score += 5

    # Streak multiplier
    if streak >= 10:
        score = int(score * 2.0)
    elif streak >= 5:
        score = int(score * 1.5)

    return score

def format_time(seconds: float) -> str:
    """Format time in seconds to readable string"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    else:
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins}m {secs:.1f}s"

def get_performance_rating(accuracy: float) -> Tuple[str, str]:
    """
    Get performance rating based on accuracy.
    Returns (emoji, message)
    """
    if accuracy >= 95:
        return "🏆", "Perfect! Master of Binary!"
    elif accuracy >= 85:
        return "🌟", "Excellent! Binary Expert!"
    elif accuracy >= 75:
        return "🎯", "Great! Strong Performance!"
    elif accuracy >= 60:
        return "👍", "Good! Keep Practicing!"
    elif accuracy >= 40:
        return "📚", "Not Bad! Room for Improvement!"
    else:
        return "💪", "Keep Learning! You'll Get There!"
