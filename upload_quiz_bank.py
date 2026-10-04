#!/usr/bin/env python3
"""
Upload the quiz question bank to Firebase, so the deployed app can load it.

The CSV (data/quiz_informatia.csv) is gitignored; run this script after every change to it.
It validates the whole file first and then replaces the bank in the database in one write.

Usage: python upload_quiz_bank.py [--check] [path/to/bank.csv]
       --check validates the file without uploading it
"""

import sys
from pathlib import Path

from firebase.config import get_database_reference, is_mock_mode
from tools.games.information_quiz import BANK_PATH, DB_PATH, QuestionBankError, bank_to_db, parse_bank, read_bank_file

check_only = "--check" in sys.argv[1:]
paths = [arg for arg in sys.argv[1:] if arg != "--check"]
path = Path(paths[0]) if paths else BANK_PATH

print(f"📤 {'Checking' if check_only else 'Uploading'} the quiz question bank from {path}...")
print()

text = read_bank_file(path)
if text is None:
    print(f"❌ File not found: {path}")
    sys.exit(1)

try:
    questions = parse_bank(text)
except QuestionBankError as e:
    print(f"❌ {e}")
    sys.exit(1)

if check_only:
    print(f"✅ {len(questions)} valid questions (nothing uploaded)")
    sys.exit(0)

if is_mock_mode():
    print("⚠️  Running in mock mode - no changes will be made to real Firebase")
    print("   Set use_mock_auth = false in secrets.toml to upload to production")
    sys.exit(1)

try:
    get_database_reference(DB_PATH).set(bank_to_db(questions))
except Exception as e:
    print(f"❌ Error: {str(e)}")
    sys.exit(1)

print(f"✅ Uploaded {len(questions)} questions to /{DB_PATH}")
print("   The app picks up the new bank within 5 minutes (cache).")
