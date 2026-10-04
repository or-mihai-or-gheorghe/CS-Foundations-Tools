# tools/games/information_quiz.py

import csv
import html
import io
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import streamlit as st

from .binary_speed_challenge import render_compact_timer
from .game_utils import calculate_score

# Game identification constants
GAME_SLUG = "information_quiz"
GAME_DISPLAY_NAME = "Test grilă: Informația"

# The question bank stays out of the public repository: a local CSV, or its content in Streamlit secrets
QUESTION_BANK = "quiz_informatia"
BANK_PATH = Path(__file__).resolve().parents[2] / "data" / f"{QUESTION_BANK}.csv"
REQUIRED_COLUMNS = ("id", "question", "correct", "wrong_1", "wrong_2", "wrong_3")

DURATION = 60        # seconds per round, as in the other speed games
BASE_POINTS = 20     # per correct answer, before the speed bonus and the streak multiplier
WRONG_PENALTY = 10   # with four options, guessing loses points on average (the score never drops below 0)

# ========================= Question Bank =========================

class QuestionBankError(ValueError):
    """The question bank is malformed."""


def parse_bank(text: str) -> List[Dict]:
    """Parse and validate the CSV question bank (comma or semicolon separated, optional BOM)."""
    text = text.lstrip("﻿")
    header = text.split("\n", 1)[0]
    delimiter = ";" if header.count(";") > header.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
    if missing:
        raise QuestionBankError(f"Banca de întrebări nu are coloanele: {', '.join(missing)}.")

    questions, problems, seen = [], [], set()
    for line, row in enumerate(reader, start=2):
        row = {key: (value or "").strip() for key, value in row.items() if key}
        qid = row.get("id") or f"rândul {line}"
        options = [row.get(column, "") for column in ("correct", "wrong_1", "wrong_2", "wrong_3")]

        if any(not row.get(column) for column in REQUIRED_COLUMNS):
            problems.append(f"{qid}: câmp gol")
        elif len({option.casefold() for option in options}) < 4:
            problems.append(f"{qid}: variante identice")
        elif qid in seen:
            problems.append(f"{qid}: id duplicat")
        else:
            seen.add(qid)
            questions.append({
                "id": qid,
                "question": row["question"],
                "correct": options[0],
                "wrong": options[1:],
                "explanation": row.get("explanation", ""),
            })

    if problems:
        raise QuestionBankError("Banca de întrebări are erori: " + "; ".join(problems) + ".")
    if not questions:
        raise QuestionBankError("Banca de întrebări nu conține nicio întrebare.")
    return questions


def _secret_bank() -> Optional[str]:
    """CSV content pasted into the Streamlit secrets, for deployments without the local file."""
    try:
        return st.secrets["quiz"]["csv"]
    except Exception:
        return None


def _read_bank_file() -> Optional[str]:
    """The local CSV; Excel on Romanian Windows saves CSV files as cp1250 rather than UTF-8."""
    if not BANK_PATH.exists():
        return None
    data = BANK_PATH.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1250", errors="replace")


def load_bank() -> Tuple[List[Dict], Optional[str]]:
    """Return (questions, error message); the error explains why the quiz cannot start."""
    try:
        text = _read_bank_file() or _secret_bank()
    except OSError:
        return [], "Banca de întrebări nu poate fi citită."
    if not text:
        return [], "Banca de întrebări nu este configurată."
    try:
        return parse_bank(text), None
    except QuestionBankError as error:
        return [], str(error)

# ========================= Access =========================

def _signed_in_user() -> Optional[Dict]:
    """The signed-in @ase.ro user, or None: the quiz is reserved for students with an account."""
    from components.streamlit_auth import validate_ase_domain
    from firebase import get_current_user

    user = get_current_user()
    if user and user.get("is_authenticated") and validate_ase_domain(user.get("email", "")):
        return user
    return None


def unavailable_reason() -> Optional[str]:
    """Why the quiz cannot be played right now (shown on the Games Hub card), or None."""
    if _signed_in_user() is None:
        return "🔒 Doar pentru utilizatorii autentificați cu un cont @ase.ro."
    return load_bank()[1]

# ========================= Game State =========================

def _now() -> float:
    return time.time()


def new_game(questions: Optional[List[Dict]] = None) -> Dict:
    """A fresh round; the questions are loaded once, when the round starts."""
    return {
        "active": False,
        "start_time": None,
        "duration": DURATION,
        "bank": questions or [],
        "queue": [],
        "current": None,
        "question_start_time": None,
        "score": 0,
        "streak": 0,
        "best_streak": 0,
        "correct_count": 0,
        "wrong_count": 0,
        "skipped_count": 0,
        "total_count": 0,
        "history": [],
        "last_result": None,
        "result_saved": False,
        "stats_recorded": False,
    }


def init_game_state():
    if "quiz_game" not in st.session_state:
        st.session_state.quiz_game = new_game()


def is_game_active(game: Dict) -> bool:
    """Check if the round is still running (time limit plus a 2-second grace period)"""
    if not game["active"] or game["start_time"] is None:
        return False
    return _now() - game["start_time"] < game["duration"] + 2


def next_question(game: Dict) -> None:
    """Draw the next question: each question once per pass through the bank, options shuffled."""
    if not game["queue"]:
        ids = [question["id"] for question in game["bank"]]
        random.shuffle(ids)
        previous = game["current"]["id"] if game["current"] else None
        if len(ids) > 1 and ids[0] == previous:
            ids.append(ids.pop(0))  # a new pass never starts with the question just asked
        game["queue"] = ids

    qid = game["queue"].pop(0)
    question = next(q for q in game["bank"] if q["id"] == qid)
    options = [question["correct"], *question["wrong"]]
    random.shuffle(options)
    game["current"] = {**question, "options": options}
    game["question_start_time"] = _now()


def score_answer(game: Dict, choice: Optional[str]) -> None:
    """Score the current question; choice=None means the player skipped it."""
    question = game["current"]
    answer_time = _now() - game["question_start_time"]
    game["total_count"] += 1

    if choice == question["correct"]:
        game["correct_count"] += 1
        game["streak"] += 1
        game["best_streak"] = max(game["best_streak"], game["streak"])
        points = calculate_score(BASE_POINTS, answer_time, game["streak"])
        outcome = "correct"
    elif choice is None:
        game["streak"] = 0
        game["skipped_count"] += 1
        points = 0
        outcome = "skipped"
    else:
        game["streak"] = 0
        game["wrong_count"] += 1
        points = -min(WRONG_PENALTY, game["score"])  # the score never goes below 0
        outcome = "wrong"

    game["score"] += points
    game["history"].append({
        "question_id": question["id"],
        "question": question["question"],
        "outcome": outcome,
        "time": answer_time,
        "points": points,
        "user_answer": choice,
        "correct_answer": question["correct"],
        "explanation": question["explanation"],
    })
    game["last_result"] = {"outcome": outcome, "points": points, "correct_answer": question["correct"]}

# ========================= UI Components =========================

def _md(text: str) -> str:
    """Escape Markdown so question text from the bank is shown literally."""
    text = re.sub(r"([\\`*_\[\]$~#<>|])", r"\\\1", text)
    text = re.sub(r"^(\d+)([.)])(?=\s)", r"\1\\\2", text)  # "1. " would start a numbered list
    return re.sub(r"^([-+])(?=\s)", r"\\\1", text)          # "- " or "+ " would start a bullet list


def _points(n: int) -> str:
    """Romanian numeral agreement: 1 punct, 5 puncte, 25 de puncte, 105 puncte"""
    if abs(n) == 1:
        return f"{n} punct"
    rest = abs(n) % 100
    return f"{n} de puncte" if rest >= 20 or (rest == 0 and n != 0) else f"{n} puncte"


def _rating(accuracy: float) -> Tuple[str, str]:
    if accuracy >= 90:
        return "🏆", "Excelent!"
    if accuracy >= 75:
        return "🌟", "Foarte bine!"
    if accuracy >= 60:
        return "👍", "Bine!"
    if accuracy >= 40:
        return "📚", "Mai recitește materia și încearcă din nou!"
    return "💪", "Continuă să exersezi!"


def _start_round(questions: List[Dict], user: Dict) -> None:
    game = new_game(questions)
    game["player"] = user.get("uid")
    game["active"] = True
    game["start_time"] = _now()
    next_question(game)
    st.session_state.quiz_game = game


def render_setup_screen(user: Dict):
    """Render the rules and the start button"""
    st.title(f"🧠 {GAME_DISPLAY_NAME}")

    if st.session_state.quiz_game["start_time"] is not None:
        st.info("⏱️ Runda s-a încheiat fără niciun răspuns.")

    questions, error = load_bank()
    if error:
        st.error(error)
        return

    st.markdown(f"""
    ### Cum se joacă
    Răspunde corect la cât mai multe întrebări în **{DURATION} de secunde**!

    - **{_points(BASE_POINTS)}** pentru un răspuns corect, plus **5** dacă răspunzi în mai puțin de 3 secunde
    - Răspunsurile corecte la rând aduc multiplicator: **×1.5** de la 5, **×2** de la 10
    - Un răspuns greșit costă **{_points(WRONG_PENALTY)}** și întrerupe seria; „Sari peste” doar întrerupe seria
    """)
    st.caption(f"Întrebări în bancă: {len(questions)}, în ordine aleatorie.")

    if st.button("🚀 Începe", key="quiz_start", type="primary", width="stretch"):
        _start_round(questions, user)
        st.rerun()


def _render_last_result(result: Optional[Dict]) -> None:
    if not result:
        return
    correct = _md(result["correct_answer"])
    if result["outcome"] == "correct":
        st.success(f"✅ Corect! (+{_points(result['points'])})")
    elif result["outcome"] == "skipped":
        st.warning(f"⏭️ Sărită. Răspunsul corect: {correct}")
    else:
        penalty = f" ({_points(result['points'])})" if result["points"] else ""
        st.error(f"❌ Greșit! Răspunsul corect: {correct}{penalty}")


def _answer_and_continue(choice: Optional[str]) -> None:
    game = st.session_state.quiz_game
    score_answer(game, choice)
    if is_game_active(game):
        next_question(game)
    else:
        game["active"] = False
    st.rerun()


def render_game_screen():
    """Render the active round"""
    game = st.session_state.quiz_game

    # Check if time is up (before any click is scored)
    if not is_game_active(game):
        game["active"] = False
        st.rerun()
        return

    render_compact_timer(game["start_time"], game["duration"])

    stats_text = f"💰 <b>{_points(game['score'])}</b> | 📝 <b>Întrebarea {game['total_count'] + 1}</b>"
    if game["streak"] > 0:
        stats_text += f" | 🔥 {game['streak']}"
    st.markdown(f"<div style='text-align: center; font-size: 16px; margin-bottom: 10px;'>{stats_text}</div>",
                unsafe_allow_html=True)

    _render_last_result(game["last_result"])

    question = game["current"]
    # A styled block rather than a heading, so Streamlit adds no anchor link next to the question
    st.markdown(f"<div style='text-align: center; font-size: 1.5rem; font-weight: 600; margin: 16px 0;'>"
                f"{html.escape(question['question'])}</div>", unsafe_allow_html=True)

    cols = st.columns(2)
    for idx, option in enumerate(question["options"]):
        if cols[idx % 2].button(_md(option), key=f"quiz_option_{game['total_count']}_{idx}", width="stretch"):
            _answer_and_continue(option)

    if st.button("⏭️ Sari peste", key=f"quiz_skip_{game['total_count']}", width="stretch"):
        _answer_and_continue(None)

    # Quit button (bottom, less prominent)
    st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("❌ Termină runda", key="quiz_end", width="stretch"):
            game["active"] = False
            st.rerun()


def _record_game_played() -> None:
    from firebase import record_game_played
    record_game_played(GAME_SLUG, authenticated=True)


def _save_to_leaderboard(user_uid: str, game_data: Dict) -> bool:
    from firebase import save_game_result
    return save_game_result(user_uid, GAME_SLUG, game_data)


def _save_result(game: Dict, user: Dict, accuracy: float, avg_time: float) -> None:
    """Save the round once: global stats and the player's leaderboard entry"""
    if game["result_saved"]:
        return

    game_data = {
        "game_slug": GAME_SLUG,
        "game_type": GAME_DISPLAY_NAME,
        "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "user_email": user.get("email", ""),
        "user_display_name": user.get("display_name", ""),
        "settings": {
            "difficulty": "Standard",
            "duration": game["duration"],
            "question_bank": QUESTION_BANK,
        },
        "results": {
            "score": game["score"],
            "accuracy": round(accuracy, 1),
            "correct_count": game["correct_count"],
            "total_count": game["total_count"],
            "skipped_count": game["skipped_count"],
            "best_streak": game["best_streak"],
            "avg_time": round(avg_time, 2),
        },
        "history": [
            {key: entry[key] for key in ("question_id", "outcome", "time", "points", "user_answer", "correct_answer")}
            for entry in game["history"]
        ],
    }

    try:
        if not game["stats_recorded"]:
            _record_game_played()
            game["stats_recorded"] = True

        if _save_to_leaderboard(user.get("uid"), game_data):
            game["result_saved"] = True
            st.success("✅ **Scorul a fost salvat în clasament!**")
        else:
            st.warning("⚠️ Scorul nu a putut fi salvat.")
    except Exception as e:
        st.error(f"❌ Eroare la salvarea rezultatului: {str(e)}")


def render_results_screen(user: Dict):
    """Render the end of round: score, saving and the answer history with explanations"""
    game = st.session_state.quiz_game

    st.title("🏁 Runda s-a încheiat!")

    accuracy = game["correct_count"] / game["total_count"] * 100 if game["total_count"] else 0
    avg_time = sum(h["time"] for h in game["history"]) / len(game["history"]) if game["history"] else 0
    emoji, message = _rating(accuracy)
    st.markdown(f"## {emoji} {message}")

    _save_result(game, user, accuracy, avg_time)

    col1, col2, col3 = st.columns(3)
    col1.metric("Scor", game["score"])
    col2.metric("Acuratețe", f"{accuracy:.1f}%")
    col3.metric("Cea mai bună serie", game["best_streak"])

    col4, col5, col6, col7 = st.columns(4)
    col4.metric("Corecte", game["correct_count"])
    col5.metric("Greșite", game["wrong_count"])
    col6.metric("Sărite", game["skipped_count"])
    col7.metric("Timp mediu", f"{avg_time:.1f}s")

    if game["history"]:
        with st.expander("📊 Răspunsurile tale", expanded=True):
            icons = {"correct": "✅", "wrong": "❌", "skipped": "⏭️"}
            for idx, entry in enumerate(game["history"], 1):
                answer = "sărită" if entry["user_answer"] is None else _md(entry["user_answer"])
                line = f"{icons[entry['outcome']]} **{idx}.** {_md(entry['question'])} → {answer}"
                if entry["outcome"] != "correct":
                    line += f" (corect: **{_md(entry['correct_answer'])}**)"
                st.markdown(line)
                if entry["explanation"]:
                    st.caption(_md(entry["explanation"]))

    col_retry, col_new = st.columns(2)
    with col_retry:
        if st.button("🔄 Joacă din nou", key="quiz_retry", type="primary", width="stretch"):
            questions, error = load_bank()
            if error:
                st.error(error)
            else:
                _start_round(questions, user)
                st.rerun()
    with col_new:
        if st.button("🏠 Ecranul de start", key="quiz_home", width="stretch"):
            st.session_state.quiz_game = new_game()
            st.rerun()

# ========================= Main Render Function =========================

def render():
    """Main render function called by the Games Hub"""
    init_game_state()

    user = _signed_in_user()
    if user is None:
        st.title(f"🧠 {GAME_DISPLAY_NAME}")
        st.warning("🔒 Testul grilă este disponibil doar pentru utilizatorii autentificați cu un cont @ase.ro. "
                   "Autentifică-te din pagina Games Hub.")
        return

    game = st.session_state.quiz_game
    if game.get("player") not in (None, user.get("uid")):
        # Another account signed in on this browser: the previous player's round is discarded
        game = st.session_state.quiz_game = new_game()

    if not game["active"] and game["total_count"] == 0:
        render_setup_screen(user)
    elif game["active"]:
        render_game_screen()
    else:
        render_results_screen(user)
