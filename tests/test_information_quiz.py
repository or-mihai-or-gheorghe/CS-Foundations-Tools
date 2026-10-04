"""Question bank parsing, scoring and the signed-in-only round of the information quiz."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from streamlit.testing.v1 import AppTest

from tools.games import information_quiz as quiz

HEADER = "id,type,topic,question,correct,wrong_1,wrong_2,wrong_3,explanation"
ROWS = [
    "q1,calcul,entropie,Cât face 2 + 2?,4,3,5,22,Adunare simplă.",
    "q2,teorie,unități,Câți biți are un octet?,8,4,16,10,Un octet are 8 biți.",
    "q3,calcul,x,Cât face 3 × 3?,9,6,12,33,Înmulțire simplă.",
]
BANK = "\n".join([HEADER, *ROWS]) + "\n"
STUDENT = {"uid": "ana_stud_ase_ro", "email": "ana@stud.ase.ro", "display_name": "Ana", "is_authenticated": True}
SCRIPT = "from tools.games import information_quiz\ninformation_quiz.render()\n"


class QuestionBank(unittest.TestCase):
    def test_parses_comma_semicolon_bom_and_quoted_fields(self):
        quoted = 'q4,teorie,x,"Unu, doi sau trei?",trei,unu,doi,patru,'
        for text in (BANK + quoted, "﻿" + BANK, BANK.replace(",", ";")):
            questions = quiz.parse_bank(text)
            self.assertEqual(questions[0], {"id": "q1", "question": "Cât face 2 + 2?", "correct": "4",
                                            "wrong": ["3", "5", "22"], "explanation": "Adunare simplă."})
        self.assertEqual(quiz.parse_bank(BANK + quoted)[-1]["question"], "Unu, doi sau trei?")
        self.assertEqual(quiz.parse_bank(BANK + quoted)[-1]["explanation"], "")

    def test_rejects_invalid_banks_naming_the_rows(self):
        cases = {
            BANK.replace(",wrong_3", ""): "wrong_3",
            BANK + ROWS[0] + "\n": "q1: id duplicat",
            BANK + "q9,x,x,Întrebare?,da,DA,nu,poate\n": "q9: variante identice",
            BANK + "q9,x,x,Întrebare?,da,,nu,poate\n": "q9: câmp gol",
            HEADER + "\n": "nicio întrebare",
        }
        for text, message in cases.items():
            with self.assertRaises(quiz.QuestionBankError) as error:
                quiz.parse_bank(text)
            self.assertIn(message, str(error.exception))

    def test_loads_the_local_file_then_the_secret_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bank.csv"
            path.write_text(BANK, encoding="utf-8-sig")
            with mock.patch.object(quiz, "BANK_PATH", path), mock.patch.object(quiz, "_secret_bank", return_value=None):
                questions, error = quiz.load_bank()
                self.assertEqual((len(questions), error), (3, None))

            missing = Path(tmp) / "missing.csv"
            with mock.patch.object(quiz, "BANK_PATH", missing), mock.patch.object(quiz, "_secret_bank", return_value=BANK):
                self.assertEqual(len(quiz.load_bank()[0]), 3)
            with mock.patch.object(quiz, "BANK_PATH", missing), mock.patch.object(quiz, "_secret_bank", return_value=None):
                self.assertEqual(quiz.load_bank(), ([], "Banca de întrebări nu este configurată."))

    def test_reads_excel_exports_saved_as_cp1250(self):
        excel = BANK.replace("ț", "ţ").replace("ș", "ş").replace(",", ";")  # cedilla letters, semicolons
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bank.csv"
            path.write_bytes(excel.encode("cp1250"))
            with mock.patch.object(quiz, "BANK_PATH", path):
                questions, error = quiz.load_bank()
        self.assertIsNone(error)
        self.assertEqual(questions[1]["question"], "Câţi biţi are un octet?")

    def test_markdown_from_the_bank_is_shown_literally(self):
        self.assertEqual(quiz._md("1. a_b *c* [d]"), "1\\. a\\_b \\*c\\* \\[d\\]")
        self.assertEqual([quiz._md(t) for t in ("+ 1 bit", "- x", "0.25", "1 bit")],
                         ["\\+ 1 bit", "\\- x", "0.25", "1 bit"])


class Scoring(unittest.TestCase):
    def setUp(self):
        self.game = quiz.new_game(quiz.parse_bank(BANK))
        self.game.update(active=True, start_time=0.0)
        quiz.next_question(self.game)

    def answer(self, correct, seconds=10.0, skip=False):
        self.game["question_start_time"] = 1000.0 - seconds
        question = self.game["current"]
        choice = None if skip else question["correct"] if correct else question["wrong"][0]
        with mock.patch.object(quiz, "_now", return_value=1000.0):
            quiz.score_answer(self.game, choice)
            quiz.next_question(self.game)
        return self.game["history"][-1]["points"]

    def test_points_bonus_streak_penalty_and_skip(self):
        self.assertEqual(self.answer(True, seconds=1.0), 25)          # speed bonus
        self.assertEqual([self.answer(True) for _ in range(4)], [20, 20, 20, 30])  # ×1.5 from the 5th in a row
        self.assertEqual(self.game["best_streak"], 5)
        self.assertEqual(self.answer(False), -10)
        self.assertEqual(self.game["streak"], 0)
        self.assertEqual(self.answer(True, skip=True), 0)
        self.assertEqual((self.game["score"], self.game["correct_count"], self.game["wrong_count"],
                          self.game["skipped_count"], self.game["total_count"]), (105, 5, 1, 1, 7))

    def test_score_never_goes_below_zero(self):
        self.assertEqual([self.answer(False) for _ in range(2)], [0, 0])
        self.answer(True)
        self.assertEqual((self.answer(False), self.game["score"]), (-10, 10))

    def test_each_pass_asks_every_question_once_with_shuffled_options(self):
        for _ in range(20):
            game = quiz.new_game(quiz.parse_bank(BANK))
            asked = []
            for _ in range(6):
                quiz.next_question(game)
                current = game["current"]
                self.assertEqual(sorted(current["options"]), sorted([current["correct"], *current["wrong"]]))
                asked.append(current["id"])
            self.assertEqual(sorted(asked[:3]), ["q1", "q2", "q3"])
            self.assertEqual(sorted(asked[3:]), ["q1", "q2", "q3"])
            self.assertNotEqual(asked[2], asked[3])


class QuizUI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        path = Path(self.tmp.name) / "bank.csv"
        path.write_text(BANK, encoding="utf-8-sig")
        self.record = mock.Mock()
        self.save = mock.Mock(return_value=True)
        # A frozen clock keeps the speed bonus deterministic; tests move start_time to end the round
        for name, value in (("BANK_PATH", path), ("_record_game_played", self.record),
                            ("_save_to_leaderboard", self.save), ("_now", mock.Mock(return_value=1_000_000.0))):
            patcher = mock.patch.object(quiz, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_as(self, user, app=None):
        with mock.patch.object(quiz, "_signed_in_user", return_value=user):
            app = (app or AppTest.from_string(SCRIPT, default_timeout=30)).run()
        self.assertEqual([e.message for e in app.exception], [])
        return app

    def click(self, app, key, user=STUDENT):
        with mock.patch.object(quiz, "_signed_in_user", return_value=user):
            app.button(key=key).click().run()
        self.assertEqual([e.message for e in app.exception], [])
        return app

    def test_anonymous_players_see_the_lock_and_no_question(self):
        app = self.run_as(None)
        self.assertIn("autentificați", app.warning[0].value)
        self.assertEqual(len(app.button), 0)
        self.assertFalse(app.session_state["quiz_game"]["active"])

    def test_signed_in_round_scores_and_saves_once(self):
        app = self.run_as(STUDENT)
        self.click(app, "quiz_start")
        game = app.session_state["quiz_game"]
        self.assertTrue(game["active"])
        self.assertEqual(len([b for b in app.button if b.key.startswith("quiz_option_")]), 4)

        correct = game["current"]["options"].index(game["current"]["correct"])
        self.click(app, f"quiz_option_0_{correct}")
        # Keys belong to the question, so a late click on the previous one cannot answer this one
        self.assertTrue(all(b.key.startswith("quiz_option_1_") for b in app.button if b.key.startswith("quiz_option_")))
        current = app.session_state["quiz_game"]["current"]
        wrong = next(i for i, option in enumerate(current["options"]) if option != current["correct"])
        self.click(app, f"quiz_option_1_{wrong}")
        self.click(app, "quiz_skip_2")
        game = app.session_state["quiz_game"]
        self.assertEqual((game["score"], game["correct_count"], game["wrong_count"], game["skipped_count"]),
                         (15, 1, 1, 1))

        game["start_time"] -= quiz.DURATION + 5  # time is up
        app.session_state["quiz_game"] = game
        self.run_as(STUDENT, app)
        self.assertEqual(app.title[0].value, "🏁 Runda s-a încheiat!")
        self.assertTrue(any("Adunare" in c.value or "octet" in c.value or "Înmulțire" in c.value for c in app.caption))
        self.record.assert_called_once_with()
        self.save.assert_called_once()
        uid, data = self.save.call_args.args
        self.assertEqual(uid, STUDENT["uid"])
        self.assertEqual((data["results"]["score"], data["results"]["total_count"], data["results"]["skipped_count"]),
                         (15, 3, 1))
        self.assertEqual([h["outcome"] for h in data["history"]], ["correct", "wrong", "skipped"])

        self.run_as(STUDENT, app)  # reruns of the results screen do not save again
        self.save.assert_called_once()
        self.click(app, "quiz_home")
        self.assertEqual(app.title[0].value, f"🧠 {quiz.GAME_DISPLAY_NAME}")

    def test_round_without_answers_returns_to_the_rules_with_a_notice(self):
        app = self.run_as(STUDENT)
        self.click(app, "quiz_start")
        game = app.session_state["quiz_game"]
        game["start_time"] -= quiz.DURATION + 5
        app.session_state["quiz_game"] = game
        self.run_as(STUDENT, app)
        self.assertIn("fără niciun răspuns", app.info[0].value)
        self.record.assert_not_called()
        self.save.assert_not_called()

    def test_round_of_another_account_is_discarded(self):
        app = self.run_as(STUDENT)
        self.click(app, "quiz_start")
        other = {**STUDENT, "uid": "ion_stud_ase_ro", "email": "ion@stud.ase.ro"}
        self.run_as(other, app)
        self.assertFalse(app.session_state["quiz_game"]["active"])
        self.assertEqual(app.title[0].value, f"🧠 {quiz.GAME_DISPLAY_NAME}")
        self.save.assert_not_called()

    def test_invalid_bank_is_reported_instead_of_starting(self):
        quiz.BANK_PATH.write_text(BANK + ROWS[0] + "\n", encoding="utf-8")
        app = self.run_as(STUDENT)
        self.assertIn("q1: id duplicat", app.error[0].value)
        self.assertEqual(len(app.button), 0)


@unittest.skipUnless(importlib.util.find_spec("firebase_admin"), "firebase-admin is not installed")
class GamesHubCard(unittest.TestCase):
    def test_quiz_card_is_locked_for_anonymous_players(self):
        app = AppTest.from_file("pages/games_hub.py", default_timeout=30)
        app.secrets["firebase"] = {"use_mock_auth": True}
        # AppTest has no st.user without [auth] secrets, so the hub's sign-in bar is stubbed
        with mock.patch("components.streamlit_auth.render_auth_ui"), \
                mock.patch.object(quiz, "_signed_in_user", return_value=None):
            app.run()
        self.assertEqual([e.message for e in app.exception], [])
        play = app.button(key=f"play_{quiz.GAME_DISPLAY_NAME}")
        self.assertTrue(play.disabled)
        self.assertFalse(app.button(key="play_Binary Speed Challenge").disabled)
        self.assertTrue(any("@ase.ro" in c.value for c in app.caption))


if __name__ == "__main__":
    unittest.main()
