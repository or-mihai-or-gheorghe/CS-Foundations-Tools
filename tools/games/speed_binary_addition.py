# tools/games/speed_binary_addition.py

import streamlit as st
import time
import random
import re
from typing import Optional
from datetime import datetime
from .game_utils import (
    ADDITION_DIFFICULTY_CONFIG,
    generate_addition_operand,
    calculate_binary_addition_with_carries,
    format_carry_visualization,
    generate_addition_distractors,
    calculate_score,
    format_time,
    get_performance_rating
)

# Game identification constants
GAME_SLUG = "speed_binary_addition"
GAME_DISPLAY_NAME = "Speed Binary Addition"

# ========================= JavaScript Timer Component =========================

def render_compact_timer(start_time: float, duration: int = 60) -> None:
    """Render compact JavaScript timer with progress bar"""
    html = f"""
    <div id="compact-timer">
        <div id="timer-bar">
            <div id="timer-fill"></div>
            <div id="timer-text">⏱️ {duration}s</div>
        </div>
    </div>
    <script>
        const startTime = {start_time};
        const duration = {duration};

        function updateTimer() {{
            const now = Date.now() / 1000;
            const elapsed = now - startTime;
            const remaining = Math.max(0, duration - elapsed);

            const timerText = document.getElementById('timer-text');
            const timerFill = document.getElementById('timer-fill');

            if (timerText && timerFill) {{
                timerText.innerText = '⏱️ ' + remaining.toFixed(1) + 's';

                const progress = (remaining / duration) * 100;
                timerFill.style.width = progress + '%';

                // Color warnings
                if (remaining < 10) {{
                    timerFill.style.backgroundColor = '#ff4444';
                    timerText.style.color = '#ff4444';
                }} else if (remaining < 30) {{
                    timerFill.style.backgroundColor = '#ffa726';
                }}

                if (remaining > 0) {{
                    requestAnimationFrame(updateTimer);
                }} else {{
                    timerText.innerText = '⏱️ TIME UP!';
                    timerText.style.color = '#ff4444';
                }}
            }}
        }}

        updateTimer();
    </script>
    <style>
        #compact-timer {{
            margin-bottom: 12px;
        }}

        #timer-bar {{
            position: relative;
            height: 36px;
            background: #f0f0f0;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        #timer-fill {{
            position: absolute;
            height: 100%;
            background: #4CAF50;
            transition: width 0.1s linear, background-color 0.3s;
        }}

        #timer-text {{
            position: absolute;
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            font-weight: bold;
            color: #333;
            font-family: 'Courier New', monospace;
            z-index: 1;
        }}
    </style>
    """
    st.components.v1.html(html, height=50)

# ========================= Game State Management =========================

def init_game_state():
    """Initialize game state in session_state"""
    if 'addition_game' not in st.session_state:
        st.session_state.addition_game = {
            'active': False,
            'difficulty': None,
            'input_type': None,
            'start_time': None,
            'duration': 60,
            'current_question': None,
            'question_start_time': None,
            'score': 0,
            'streak': 0,
            'best_streak': 0,
            'correct_count': 0,
            'total_count': 0,
            'history': [],
            'last_result': None,
            'result_saved': False,
            'last_decimal_question': -10  # Track when last decimal question was shown
        }

def reset_game():
    """Reset game state"""
    st.session_state.addition_game = {
        'active': False,
        'difficulty': None,
        'input_type': None,
        'start_time': None,
        'duration': 60,
        'current_question': None,
        'question_start_time': None,
        'score': 0,
        'streak': 0,
        'best_streak': 0,
        'correct_count': 0,
        'total_count': 0,
        'history': [],
        'last_result': None,
        'result_saved': False,
        'last_decimal_question': -10
    }

def is_game_active() -> bool:
    """Check if game is still active (within time limit + grace period)"""
    game = st.session_state.addition_game
    if not game['active'] or game['start_time'] is None:
        return False

    elapsed = time.time() - game['start_time']
    # Add 2-second grace period
    return elapsed < (game['duration'] + 2)

# ========================= Question Generation =========================

def generate_question():
    """Generate a new addition question (binary+binary or binary+decimal)"""
    game = st.session_state.addition_game
    difficulty = game['difficulty']

    # Generate two random operands (ensure both > 0)
    operand_a_dec, operand_a_bin = generate_addition_operand(difficulty)
    operand_b_dec, operand_b_bin = generate_addition_operand(difficulty)

    # Ensure no zero operands
    while operand_a_dec == 0:
        operand_a_dec, operand_a_bin = generate_addition_operand(difficulty)
    while operand_b_dec == 0:
        operand_b_dec, operand_b_bin = generate_addition_operand(difficulty)

    # Calculate result with carry tracking
    result_dec, carry_positions = calculate_binary_addition_with_carries(operand_a_dec, operand_b_dec)
    result_bin = bin(result_dec)[2:]

    # Determine question type: only show decimal if at least 5 questions since last decimal
    # Also avoid showing 1 in base 10 (trivial and confusing)
    questions_since_decimal = game['total_count'] - game['last_decimal_question']
    can_show_decimal = questions_since_decimal >= 5 and operand_b_dec > 1

    if can_show_decimal and random.random() < 0.25:
        # Show binary+decimal question
        question_type = 'binary_decimal'
        game['last_decimal_question'] = game['total_count']
    else:
        # Show binary+binary question
        question_type = 'binary_binary'

    if question_type == 'binary_binary':
        # Both operands shown in binary
        display_question = f"`{operand_a_bin}` + `{operand_b_bin}` = ?"
        question_text = f"{operand_a_bin} + {operand_b_bin}"
    else:
        # Second operand shown in decimal with subscript
        display_question = f"`{operand_a_bin}` + {operand_b_dec}<sub>10</sub> = ?"
        question_text = f"{operand_a_bin} + {operand_b_dec}₁₀"

    # Generate multiple choice options if needed
    choices = None
    if game['input_type'] == 'Multiple Choice':
        distractors = generate_addition_distractors(result_bin, operand_a_dec, operand_b_dec, count=3)
        choices = [result_bin] + distractors
        random.shuffle(choices)

    game['current_question'] = {
        'type': question_type,
        'operand_a_dec': operand_a_dec,
        'operand_a_bin': operand_a_bin,
        'operand_b_dec': operand_b_dec,
        'operand_b_bin': operand_b_bin,
        'result_dec': result_dec,
        'result_bin': result_bin,
        'carry_positions': carry_positions,
        'display_question': display_question,
        'question_text': question_text,
        'choices': choices
    }
    game['question_start_time'] = time.time()

# ========================= Answer Checking =========================

def check_answer(user_answer: str) -> bool:
    """Check if user answer is correct and update game state"""
    game = st.session_state.addition_game
    question = game['current_question']

    # Normalize answers
    correct_answer = question['result_bin'].strip()
    user_answer = user_answer.strip()

    is_correct = (user_answer == correct_answer)

    # Calculate answer time
    answer_time = time.time() - game['question_start_time']

    # Update stats
    game['total_count'] += 1

    if is_correct:
        game['correct_count'] += 1
        game['streak'] += 1
        game['best_streak'] = max(game['best_streak'], game['streak'])

        # Calculate score
        base_points = ADDITION_DIFFICULTY_CONFIG[game['difficulty']]['points']
        points = calculate_score(base_points, answer_time, game['streak'])
        game['score'] += points

        # Record history
        game['history'].append({
            'correct': True,
            'time': answer_time,
            'points': points,
            'question_text': question['question_text'],
            'operand_a_bin': question['operand_a_bin'],
            'operand_b_bin': question['operand_b_bin'],
            'operand_a_dec': question['operand_a_dec'],
            'operand_b_dec': question['operand_b_dec'],
            'result_bin': question['result_bin'],
            'carry_positions': question['carry_positions'],
            'user_answer': user_answer
        })

        # Store result for display
        game['last_result'] = {
            'is_correct': True,
            'message': '✅ Correct!',
            'correct_answer': correct_answer
        }
    else:
        game['streak'] = 0

        # Penalty only for Expert mode in Multiple Choice
        penalty = 0
        if game['difficulty'] == 'Expert' and game['input_type'] == 'Multiple Choice':
            penalty = -10
            game['score'] = max(0, game['score'] + penalty)

        game['history'].append({
            'correct': False,
            'time': answer_time,
            'points': penalty,
            'question_text': question['question_text'],
            'operand_a_bin': question['operand_a_bin'],
            'operand_b_bin': question['operand_b_bin'],
            'operand_a_dec': question['operand_a_dec'],
            'operand_b_dec': question['operand_b_dec'],
            'result_bin': question['result_bin'],
            'carry_positions': question['carry_positions'],
            'user_answer': user_answer
        })

        # Store result for display
        penalty_text = f' ({penalty} points)' if penalty < 0 else ''
        game['last_result'] = {
            'is_correct': False,
            'message': f'❌ Wrong! Correct answer: `{correct_answer}`{penalty_text}',
            'correct_answer': correct_answer
        }

    return is_correct

# ========================= UI Components =========================

def render_setup_screen():
    """Render game setup screen"""
    st.title("🎮 Speed Binary Addition")

    # Show previous score if exists
    game = st.session_state.addition_game
    if game['total_count'] > 0:
        accuracy = (game['correct_count'] / game['total_count'] * 100)
        st.info(f"🏆 Previous Score: **{game['score']} points** | Accuracy: **{accuracy:.0f}%**")

    st.markdown("""
    ### How to Play
    Add binary numbers as fast as you can in **60 seconds**!

    - Choose difficulty level and input type
    - Questions mix binary+binary and binary+decimal problems
    - Earn points for correct answers
    - Build streaks for bonus multipliers
    - Answer quickly for speed bonuses!
    """)

    col1, col2 = st.columns(2)

    with col1:
        difficulty = st.radio(
            "**Difficulty**",
            ["Easy", "Advanced", "Expert"],
            help="Higher difficulty = larger numbers, more points"
        )

    with col2:
        input_type = st.radio(
            "**Input Type**",
            ["Multiple Choice", "Direct Input"],
            help="Direct input is faster but more challenging"
        )

    # Show difficulty info
    config = ADDITION_DIFFICULTY_CONFIG[difficulty]
    st.info(f"**{difficulty}**: {config['description']} • {config['points']} points per correct answer")

    # Show Expert mode warning
    if difficulty == "Expert":
        st.markdown('<p style="color: #ff4444; font-weight: bold;">⚠️ Expert Mode: Wrong answers in Multiple Choice = -10 points</p>', unsafe_allow_html=True)

    if st.button("🚀 Start Game", type="primary", use_container_width=True):
        game = st.session_state.addition_game
        game['difficulty'] = difficulty
        game['input_type'] = input_type
        game['active'] = True
        game['start_time'] = time.time()
        generate_question()
        st.rerun()

def render_game_screen():
    """Render active game screen"""
    game = st.session_state.addition_game

    # Check if time is up
    if not is_game_active():
        game['active'] = False
        st.rerun()
        return

    # Display timer
    render_compact_timer(game['start_time'], game['duration'])

    # Display stats in one line
    streak_display = f"🔥 {game['streak']}" if game['streak'] > 0 else ""
    stats_text = f"💰 <b>{game['score']} pts</b> | 📝 <b>Q{game['total_count'] + 1}</b>"
    if streak_display:
        stats_text += f" | {streak_display}"

    st.markdown(f"<div style='text-align: center; font-size: 16px; margin-bottom: 10px;'>{stats_text}</div>", unsafe_allow_html=True)

    # Display last answer result
    if game['last_result']:
        if game['last_result']['is_correct']:
            st.success(game['last_result']['message'])
        else:
            st.error(game['last_result']['message'])

    # Display current question
    question = game['current_question']
    # Convert markdown backticks to HTML
    display_question = re.sub(
        r'`([^`]+)`',
        r'<code style="background: #f0f0f0; padding: 4px 8px; border-radius: 4px; font-family: monospace; font-size: 18px;">\1</code>',
        question['display_question']
    )
    st.markdown(f"<h2 style='text-align: center; margin: 20px 0;'>{display_question}</h2>", unsafe_allow_html=True)

    # Input based on type
    if game['input_type'] == 'Multiple Choice':
        # Multiple choice buttons (2 columns)
        cols = st.columns(2)

        for idx, choice in enumerate(question['choices']):
            col = cols[idx % 2]
            if col.button(choice, key=f"choice_{idx}", use_container_width=True):
                check_answer(choice)

                # Generate next question immediately
                if is_game_active():
                    generate_question()
                    st.rerun()
                else:
                    game['active'] = False
                    st.rerun()
    else:
        # Direct input
        with st.form(key='answer_form', clear_on_submit=True):
            user_answer = st.text_input(
                "Enter binary result:",
                key='answer_input',
                placeholder="e.g., 10101"
            )

            submitted = st.form_submit_button("Submit", type="primary", use_container_width=True)

            if submitted and user_answer:
                # Validate binary input (only 0s and 1s)
                if re.match(r'^[01]+$', user_answer):
                    check_answer(user_answer)

                    if is_game_active():
                        generate_question()
                        st.rerun()
                    else:
                        game['active'] = False
                        st.rerun()
                else:
                    st.error("❌ Invalid input! Please enter only 0s and 1s.")

        # Auto-focus JavaScript
        st.components.v1.html("""
            <script>
                setTimeout(function() {
                    const inputs = window.parent.document.querySelectorAll('input[type="text"]');
                    if (inputs.length > 0) {
                        inputs[inputs.length - 1].focus();
                    }
                }, 100);
            </script>
        """, height=0)

    # Quit button
    st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("❌ End Game", type="secondary", use_container_width=True):
            game['active'] = False
            st.rerun()

def _save_game_result_to_db(game: dict, accuracy: float, avg_time: float):
    """Save game result to Firebase database if user is authenticated"""
    try:
        from firebase import get_current_user, save_game_result, record_game_played

        user = get_current_user()
        is_authenticated = user and user.get('is_authenticated')

        # Record global stats
        record_game_played(GAME_SLUG, authenticated=is_authenticated)

        if is_authenticated:
            # Check if already saved
            if 'result_saved' in game and game['result_saved']:
                return

            # Prepare game data
            game_data = {
                "game_slug": GAME_SLUG,
                "game_type": GAME_DISPLAY_NAME,
                "timestamp": datetime.utcnow().isoformat(),
                "user_email": user.get('email', ''),
                "user_display_name": user.get('display_name', ''),
                "settings": {
                    "difficulty": game['difficulty'],
                    "input_type": game['input_type'],
                    "duration": game['duration']
                },
                "results": {
                    "score": game['score'],
                    "accuracy": round(accuracy, 1),
                    "correct_count": game['correct_count'],
                    "total_count": game['total_count'],
                    "best_streak": game['best_streak'],
                    "avg_time": round(avg_time, 2)
                },
                "history": game['history']
            }

            # Save to database
            user_uid = user.get('uid')
            success = save_game_result(user_uid, GAME_SLUG, game_data)

            if success:
                st.success("✅ **Score saved to leaderboard!**")
                game['result_saved'] = True
            else:
                st.warning("⚠️ Failed to save score. Please try again.")
        else:
            st.info("💡 **Sign in to save your score and appear on the leaderboard!**")

    except Exception as e:
        st.error(f"❌ Error saving result: {str(e)}")

def render_results_screen():
    """Render game over / results screen"""
    game = st.session_state.addition_game

    st.title("🏁 Game Over!")

    # Calculate final stats
    accuracy = (game['correct_count'] / game['total_count'] * 100) if game['total_count'] > 0 else 0
    avg_time = sum(h['time'] for h in game['history']) / len(game['history']) if game['history'] else 0
    emoji, message = get_performance_rating(accuracy)

    st.markdown(f"## {emoji} {message}")

    # Save to database
    _save_game_result_to_db(game, accuracy, avg_time)

    # Display final stats
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Final Score", game['score'])
    with col2:
        st.metric("Accuracy", f"{accuracy:.1f}%")
    with col3:
        st.metric("Best Streak", game['best_streak'])

    col4, col5, col6 = st.columns(3)

    with col4:
        st.metric("Correct", game['correct_count'])
    with col5:
        st.metric("Wrong", game['total_count'] - game['correct_count'])
    with col6:
        st.metric("Avg Time", f"{avg_time:.1f}s")

    # Show detailed history with carry visualization
    if game['history']:
        with st.expander("📊 Answer History", expanded=False):
            for idx, entry in enumerate(reversed(game['history']), 1):
                status = "✅" if entry['correct'] else "❌"

                # Format the question display
                q_num = len(game['history']) - idx + 1

                # Build carry visualization
                carry_viz = format_carry_visualization(
                    entry['operand_a_bin'],
                    entry['operand_b_bin'],
                    entry['result_bin'],
                    entry['carry_positions']
                )

                # Display entry
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    # Show carry markers if there are any
                    if carry_viz.strip():
                        st.markdown(f"{status} **Q{q_num}:** `{entry['question_text']}`")
                        st.caption(f"Carries: `{carry_viz}`")
                    else:
                        st.markdown(f"{status} **Q{q_num}:** `{entry['question_text']}`")

                    if entry['correct']:
                        st.markdown(f"Your answer: `{entry['user_answer']}` ✓")
                    else:
                        st.markdown(f"Your answer: `{entry['user_answer']}` → Correct: `{entry['result_bin']}`")

                with col_b:
                    points_display = f"+{entry['points']} pts" if entry['correct'] else (f"{entry['points']} pts" if entry['points'] < 0 else "0 pts")
                    st.caption(f"{entry['time']:.1f}s • {points_display}")

    # Action buttons
    col_retry, col_new = st.columns(2)

    with col_retry:
        if st.button("🔄 Play Again (Same Settings)", type="primary", use_container_width=True):
            difficulty = game['difficulty']
            input_type = game['input_type']
            reset_game()
            game = st.session_state.addition_game
            game['difficulty'] = difficulty
            game['input_type'] = input_type
            game['active'] = True
            game['start_time'] = time.time()
            generate_question()
            st.rerun()

    with col_new:
        if st.button("🎮 New Game (Change Settings)", use_container_width=True):
            reset_game()
            st.rerun()

# ========================= Main Render Function =========================

def render():
    """Main render function called by app.py"""
    init_game_state()

    game = st.session_state.addition_game

    if not game['active'] and game['total_count'] == 0:
        # Setup screen
        render_setup_screen()
    elif game['active']:
        # Active game screen
        render_game_screen()
    else:
        # Results screen
        render_results_screen()
