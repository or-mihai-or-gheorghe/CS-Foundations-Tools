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

# ========================= Speed Binary Addition Utilities =========================

# Difficulty config for Speed Binary Addition (3-level system)
ADDITION_DIFFICULTY_CONFIG = {
    "Easy": {
        "bit_min": 1,
        "bit_max": 5,
        "points": 10,
        "description": "1-5 bits"
    },
    "Advanced": {
        "bit_min": 1,
        "bit_max": 8,
        "points": 25,
        "description": "1-8 bits"
    },
    "Expert": {
        "bit_min": 1,
        "bit_max": 12,
        "points": 40,
        "description": "1-12 bits"
    }
}

def generate_addition_operand(difficulty: str) -> Tuple[int, str]:
    """
    Generate a random operand for binary addition based on difficulty.
    Returns (decimal_value, binary_string)
    """
    config = ADDITION_DIFFICULTY_CONFIG[difficulty]
    bit_length = random.randint(config["bit_min"], config["bit_max"])

    # Generate number with the chosen bit length
    if bit_length == 1:
        decimal_val = random.randint(0, 1)
    else:
        # Ensure MSB is 1 to guarantee the bit length (except for 1-bit numbers)
        min_val = 1 << (bit_length - 1)
        max_val = (1 << bit_length) - 1
        decimal_val = random.randint(min_val, max_val)

    binary_str = bin(decimal_val)[2:]
    return decimal_val, binary_str

def calculate_binary_addition_with_carries(a: int, b: int) -> Tuple[int, List[int]]:
    """
    Perform binary addition and track carry positions.

    Args:
        a, b: Decimal integers to add

    Returns:
        (result, carry_positions): Result and list of bit positions where carries occurred
    """
    result = a + b
    carry_positions = []

    # Simulate binary addition to find carries
    carry = 0
    pos = 0

    while a > 0 or b > 0 or carry > 0:
        bit_a = a & 1
        bit_b = b & 1

        # If we have a carry out from this position
        if bit_a + bit_b + carry >= 2:
            carry_positions.append(pos)
            carry = 1
        else:
            carry = 0

        a >>= 1
        b >>= 1
        pos += 1

    return result, carry_positions

def format_carry_visualization(a_bin: str, b_bin: str, result_bin: str, carry_positions: List[int]) -> str:
    """
    Format carry visualization for display in results.

    Args:
        a_bin: First operand in binary (string)
        b_bin: Second operand in binary (string)
        result_bin: Result in binary (string)
        carry_positions: List of bit positions where carries occurred

    Returns:
        String with carry markers (e.g., "  ¹ ¹  ")
    """
    if not carry_positions:
        return ""

    # Find the maximum length needed
    max_len = max(len(a_bin), len(b_bin), len(result_bin))

    # Build carry string from right to left
    carry_str = [' '] * max_len
    for pos in carry_positions:
        # Convert position (from right) to index (from left)
        idx = max_len - 1 - pos
        if 0 <= idx < max_len:
            carry_str[idx] = '¹'

    return ''.join(carry_str)

def generate_addition_distractors(correct_result: str, operand_a: int, operand_b: int, count: int = 3) -> List[str]:
    """
    Generate plausible wrong answers for binary addition.

    Args:
        correct_result: Correct binary result as string
        operand_a, operand_b: The original operands (in decimal)
        count: Number of distractors to generate

    Returns:
        List of distractor binary strings
    """
    distractors = set()
    correct_int = int(correct_result, 2)

    # Strategy 1: Wrong carry propagation (most common error)
    # Add without considering all carries properly
    wrong_carry = operand_a ^ operand_b  # XOR gives addition without carry
    if wrong_carry != correct_int and wrong_carry > 0:
        distractors.add(bin(wrong_carry)[2:])

    # Strategy 2: Off-by-one errors
    if correct_int > 0:
        distractors.add(bin(correct_int - 1)[2:])
    distractors.add(bin(correct_int + 1)[2:])

    # Strategy 3: Bit flip error (flip random bit in correct answer)
    if len(correct_result) > 0:
        for _ in range(3):
            bit_pos = random.randint(0, len(correct_result) - 1)
            temp_list = list(correct_result)
            temp_list[bit_pos] = '0' if temp_list[bit_pos] == '1' else '1'
            distractors.add(''.join(temp_list))

    # Strategy 4: Missing MSB (forgot final carry)
    if len(correct_result) > 1:
        distractors.add(correct_result[1:])

    # Strategy 5: Extra bit error
    distractors.add('1' + correct_result)

    # Remove correct answer and empty strings
    distractors.discard(correct_result)
    distractors = {d for d in distractors if d and d != '0' * len(d)}

    # If we don't have enough, add some random variations
    while len(distractors) < count:
        noise = random.randint(-3, 3)
        candidate = max(1, correct_int + noise)
        if candidate != correct_int:
            distractors.add(bin(candidate)[2:])

    # Return random sample
    return random.sample(list(distractors), min(count, len(distractors)))
