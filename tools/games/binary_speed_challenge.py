# tools/games/binary_speed_challenge.py

import streamlit as st
import time
import random
from typing import Optional
from .game_utils import (
    DIFFICULTY_CONFIG,
    generate_random_number,
    generate_distractors_decimal,
    generate_distractors_binary,
    calculate_score,
    format_time,
    get_performance_rating
)

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
    if 'binary_game' not in st.session_state:
        st.session_state.binary_game = {
            'active': False,
            'mode': None,
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
            'last_result': None,  # Store last answer result for display
            'asked_numbers': set()  # Track numbers already asked
        }

def reset_game():
    """Reset game state"""
    st.session_state.binary_game = {
        'active': False,
        'mode': None,
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
        'asked_numbers': set()
    }

def is_game_active() -> bool:
    """Check if game is still active (within time limit + grace period)"""
    game = st.session_state.binary_game
    if not game['active'] or game['start_time'] is None:
        return False

    elapsed = time.time() - game['start_time']
    # Add 2-second grace period to prevent timer lock issue
    return elapsed < (game['duration'] + 2)

def generate_question():
    """Generate a new question based on game settings"""
    game = st.session_state.binary_game

    # Generate unique number (avoid duplicates)
    max_attempts = 50
    for _ in range(max_attempts):
        decimal_val, binary_str = generate_random_number(game['difficulty'])
        if decimal_val not in game['asked_numbers']:
            break

    # Add to asked numbers
    game['asked_numbers'].add(decimal_val)

    # Determine question type based on mode
    if game['mode'] == 'Mixed':
        # Alternate between Binary→Decimal and Decimal→Binary
        question_type = 'binary_to_decimal' if game['total_count'] % 2 == 0 else 'decimal_to_binary'
    elif game['mode'] == 'Binary → Decimal':
        question_type = 'binary_to_decimal'
    else:  # Decimal → Binary
        question_type = 'decimal_to_binary'

    if question_type == 'binary_to_decimal':
        question = {
            'type': 'binary_to_decimal',
            'question': binary_str,
            'answer': str(decimal_val),
            'display_question': f"Binary: `{binary_str}`",
            'choices': None
        }

        if game['input_type'] == 'Multiple Choice':
            distractors = generate_distractors_decimal(decimal_val, 3)
            choices = [str(decimal_val)] + [str(d) for d in distractors]
            random.shuffle(choices)
            question['choices'] = choices

    else:  # decimal_to_binary
        question = {
            'type': 'decimal_to_binary',
            'question': str(decimal_val),
            'answer': binary_str,
            'display_question': f"Decimal: `{decimal_val}`",
            'choices': None
        }

        if game['input_type'] == 'Multiple Choice':
            distractors = generate_distractors_binary(binary_str, 3)
            choices = [binary_str] + distractors
            random.shuffle(choices)
            question['choices'] = choices

    game['current_question'] = question
    game['question_start_time'] = time.time()

def check_answer(user_answer: str, is_skip: bool = False) -> bool:
    """Check if user answer is correct and update game state"""
    game = st.session_state.binary_game
    question = game['current_question']

    # Normalize answers for comparison
    correct_answer = question['answer'].strip()
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
        base_points = DIFFICULTY_CONFIG[game['difficulty']]['points']
        points = calculate_score(base_points, answer_time, game['streak'])
        game['score'] += points

        # Record history
        game['history'].append({
            'correct': True,
            'time': answer_time,
            'points': points,
            'question': question['display_question'],
            'user_answer': user_answer,
            'correct_answer': correct_answer
        })

        # Store result for display
        game['last_result'] = {
            'is_correct': True,
            'message': '✅ Correct!',
            'correct_answer': correct_answer
        }
    else:
        game['streak'] = 0

        # Penalty only for Expert mode in Multiple Choice (and not if skipped)
        penalty = 0
        if game['difficulty'] == 'Expert' and game['input_type'] == 'Multiple Choice' and not is_skip:
            penalty = -10
            game['score'] = max(0, game['score'] + penalty)  # Don't go below 0

        game['history'].append({
            'correct': False,
            'time': answer_time,
            'points': penalty,
            'question': question['display_question'],
            'user_answer': user_answer if not is_skip else "SKIPPED",
            'correct_answer': correct_answer
        })

        # Store result for display
        if is_skip:
            game['last_result'] = {
                'is_correct': False,
                'message': f'⏭️ Skipped! Correct answer: `{correct_answer}`',
                'correct_answer': correct_answer
            }
        else:
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
    st.title("🎮 Binary Speed Challenge")

    # Show current score if there's a previous game
    game = st.session_state.binary_game
    if game['total_count'] > 0:
        st.info(f"🏆 Previous Score: **{game['score']} points** | Accuracy: **{(game['correct_count']/game['total_count']*100):.0f}%**")

    st.markdown("""
    ### How to Play
    Convert as many numbers as possible in **60 seconds**!

    - Choose your game mode and difficulty level
    - Earn points for correct answers
    - Build streaks for bonus multipliers
    - Answer quickly for speed bonuses!
    """)

    col1, col2 = st.columns(2)

    with col1:
        mode = st.radio(
            "**Game Mode**",
            ["Binary → Decimal", "Decimal → Binary", "Mixed"],
            help="Choose conversion direction (Mixed alternates between both)"
        )

    with col2:
        difficulty = st.radio(
            "**Difficulty**",
            ["Easy", "Medium", "Hard", "Expert"],
            help="Higher difficulty = more points per question"
        )

    # Show difficulty info
    config = DIFFICULTY_CONFIG[difficulty]
    st.info(f"**{difficulty}**: {config['description']} • {config['points']} points per correct answer")

    # Show Expert mode warning
    if difficulty == "Expert":
        st.markdown('<p style="color: #ff4444; font-weight: bold;">⚠️ Expert Mode: Wrong answers in Multiple Choice = -10 points</p>', unsafe_allow_html=True)

    input_type = st.radio(
        "**Input Type**",
        ["Direct Input", "Multiple Choice"],
        horizontal=True,
        help="Direct input is faster but more challenging"
    )

    if st.button("🚀 Start Game", type="primary", use_container_width=True):
        game = st.session_state.binary_game
        game['mode'] = mode
        game['difficulty'] = difficulty
        game['input_type'] = input_type
        game['active'] = True
        game['start_time'] = time.time()
        generate_question()
        st.rerun()

def render_game_screen():
    """Render active game screen"""
    game = st.session_state.binary_game

    # Check if time is up
    if not is_game_active():
        game['active'] = False
        st.rerun()
        return

    # Display compact timer
    render_compact_timer(game['start_time'], game['duration'])

    # Display compact stats in one line
    streak_display = f"🔥 {game['streak']}" if game['streak'] > 0 else ""
    stats_text = f"💰 <b>{game['score']} pts</b> | 📝 <b>Q{game['total_count']}</b>"
    if streak_display:
        stats_text += f" | {streak_display}"

    st.markdown(f"<div style='text-align: center; font-size: 16px; margin-bottom: 10px;'>{stats_text}</div>", unsafe_allow_html=True)

    # Display last answer result if available (compact version)
    if game['last_result']:
        if game['last_result']['is_correct']:
            st.success(game['last_result']['message'])
        else:
            if '⏭️' in game['last_result']['message']:
                st.warning(game['last_result']['message'])
            else:
                st.error(game['last_result']['message'])

    # Display current question (larger for mobile)
    question = game['current_question']
    # Convert markdown backticks to HTML code tags for proper rendering
    import re
    display_question = re.sub(r'`([^`]+)`', r'<code style="background: #f0f0f0; padding: 4px 8px; border-radius: 4px; font-family: monospace;">\1</code>', question['display_question'])
    st.markdown(f"<h2 style='text-align: center; margin: 20px 0;'>{display_question}</h2>", unsafe_allow_html=True)

    # Input based on type
    if game['input_type'] == 'Multiple Choice':
        # Multiple choice buttons (responsive: 2 cols on desktop, stacks on mobile)
        cols = st.columns(2)

        for idx, choice in enumerate(question['choices']):
            col = cols[idx % 2]
            # Larger buttons with better mobile touch targets
            if col.button(choice, key=f"choice_{idx}", use_container_width=True):
                check_answer(choice)

                # Generate next question immediately
                if is_game_active():
                    generate_question()
                    st.rerun()
                else:
                    game['active'] = False
                    st.rerun()

        # Skip button for Expert mode
        if game['difficulty'] == 'Expert':
            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
            if st.button("⏭️ Skip Question", key="skip_btn", use_container_width=True, type="secondary"):
                check_answer("", is_skip=True)

                if is_game_active():
                    generate_question()
                    st.rerun()
                else:
                    game['active'] = False
                    st.rerun()
    else:
        # Direct input with auto-focus
        with st.form(key='answer_form', clear_on_submit=True):
            if question['type'] == 'binary_to_decimal':
                user_answer = st.text_input("Enter decimal number:", key='answer_input')
            else:
                user_answer = st.text_input("Enter binary number:", key='answer_input')

            submitted = st.form_submit_button("Submit", type="primary", use_container_width=True)

            if submitted and user_answer:
                check_answer(user_answer)

                # Generate next question immediately
                if is_game_active():
                    generate_question()
                    st.rerun()
                else:
                    game['active'] = False
                    st.rerun()

        # Auto-focus JavaScript for input field
        st.components.v1.html("""
            <script>
                // Auto-focus the input field after page load
                window.parent.document.addEventListener('DOMContentLoaded', function() {
                    setTimeout(function() {
                        const inputs = window.parent.document.querySelectorAll('input[type="text"]');
                        if (inputs.length > 0) {
                            inputs[inputs.length - 1].focus();
                        }
                    }, 100);
                });

                // Also try to focus immediately
                setTimeout(function() {
                    const inputs = window.parent.document.querySelectorAll('input[type="text"]');
                    if (inputs.length > 0) {
                        inputs[inputs.length - 1].focus();
                    }
                }, 100);
            </script>
        """, height=0)

    # Quit button (bottom, less prominent)
    st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("❌ End Game", type="secondary", use_container_width=True):
            game['active'] = False
            st.rerun()

def render_results_screen():
    """Render game over / results screen"""
    game = st.session_state.binary_game

    st.title("🏁 Game Over!")

    # Calculate final stats
    accuracy = (game['correct_count'] / game['total_count'] * 100) if game['total_count'] > 0 else 0
    emoji, message = get_performance_rating(accuracy)

    st.markdown(f"## {emoji} {message}")

    # Display final stats
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Final Score", game['score'], help="Total points earned")
    with col2:
        st.metric("Accuracy", f"{accuracy:.1f}%", help="Percentage of correct answers")
    with col3:
        st.metric("Best Streak", game['best_streak'], help="Longest consecutive correct answers")

    col4, col5, col6 = st.columns(3)

    with col4:
        st.metric("Correct", game['correct_count'])
    with col5:
        st.metric("Wrong", game['total_count'] - game['correct_count'])
    with col6:
        avg_time = sum(h['time'] for h in game['history']) / len(game['history']) if game['history'] else 0
        st.metric("Avg Time", f"{avg_time:.1f}s")

    # Show detailed history
    if game['history']:
        with st.expander("📊 Answer History", expanded=False):
            for idx, entry in enumerate(reversed(game['history']), 1):
                status = "✅" if entry['correct'] else "❌"
                result_text = "✓" if entry['correct'] else f"(Correct: `{entry['correct_answer']}`)"
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown(
                        f"{status} **Q{len(game['history']) - idx + 1}:** {entry['question']} "
                        f"→ Your answer: `{entry['user_answer']}` "
                        f"{result_text}"
                    )
                with col_b:
                    points_display = f"+{entry['points']} pts" if entry['correct'] else "0 pts"
                    st.caption(f"{entry['time']:.1f}s • {points_display}")

    # Action buttons
    col_retry, col_new = st.columns(2)

    with col_retry:
        if st.button("🔄 Play Again (Same Settings)", type="primary", use_container_width=True):
            # Keep settings, reset stats
            mode = game['mode']
            difficulty = game['difficulty']
            input_type = game['input_type']
            reset_game()
            game = st.session_state.binary_game
            game['mode'] = mode
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

    game = st.session_state.binary_game

    if not game['active'] and game['total_count'] == 0:
        # Setup screen
        render_setup_screen()
    elif game['active']:
        # Active game screen
        render_game_screen()
    else:
        # Results screen
        render_results_screen()
