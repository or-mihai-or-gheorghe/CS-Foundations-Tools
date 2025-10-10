# CS Foundations Tools

An interactive educational web application designed to help computer science students visualize and understand fundamental concepts in computing. Built at Bucharest University of Economic Studies and freely available for students and educators worldwide.

**Live Demo:** [https://cs-fundamentals.streamlit.app/](https://cs-fundamentals.streamlit.app/)

## Overview

This application provides hands-on, interactive tools for learning low-level computing concepts including binary arithmetic, floating-point representation, error correction codes, and digital logic. Each tool includes step-by-step explanations and visual representations to enhance understanding.

## Features

### Binary Operations & Conversions (7 tools)
- **Decimal to Binary** - Convert decimal numbers to binary with detailed steps
- **Binary to Decimal** - Convert binary numbers to decimal
- **Gray Code Converter** - Convert between binary and Gray code with verification
- **Multi-Format Converter** - Convert between binary, octal, decimal, and hexadecimal
- **Raw Unsigned Arithmetic** - Perform addition and subtraction on unsigned binary numbers
- **2's Complement Arithmetic** - Binary arithmetic with signed numbers
- **BCD Arithmetic** - Binary-coded decimal addition and subtraction

### Floating Point Operations (4 tools)
- **IEEE 754 Converter** - Convert decimal numbers to IEEE 754 single/double precision with verification
- **Decimal Converter** - Convert IEEE 754 binary back to decimal
- **Special Values Explorer** - Explore special floating-point values (infinity, NaN, denormals)
- **FP Arithmetic** - Floating-point addition and subtraction with precision analysis

### Error Detecting & Correcting Codes (4 tools)
- **Hamming Encode** - Generate Hamming codes using parity-check matrix formulation
- **Hamming Decode & Correct** - Detect and correct single-bit errors in Hamming codes
- **CRC Encode** - Cyclic redundancy check encoding with polynomial division
- **CRC Decode** - CRC error detection

### Logic Operations (1 tool)
- **K-Map Minimizer (BETA)** - Karnaugh map-based Boolean expression minimization (up to 5 variables)
  - Supports multiple expression syntaxes
  - Visual Gray-code ordered K-maps with torus wrapping
  - Prime implicant selection and SOP minimization

### Games Hub (3 games)
Interactive timed games to practice and master binary operations with competitive leaderboards.

- **Binary Speed Challenge** - Convert binary and decimal numbers at lightning speed
  - Multiple difficulty levels (Easy to Expert)
  - Direct input or multiple choice modes
  - Streak multipliers and speed bonuses

- **Speed Binary Addition** - Add binary numbers under time pressure
  - Mix of binary+binary and binary+decimal problems
  - Three difficulty levels (Easy, Advanced, Expert)
  - Carry propagation visualization in results
  - Direct input or multiple choice modes

- **Speed Hex Conversion** - Convert between binary and hexadecimal formats
  - Binary→Hex, Hex→Binary, and Mixed conversion modes
  - Three difficulty levels (Easy, Advanced, Expert)
  - Case-insensitive input for user convenience
  - Direct input or multiple choice modes

**Leaderboard & Statistics:**
- Sign in with @ase.ro Google account to save scores
- Global and per-game leaderboards with filtering
- Real-time rankings and performance analytics
- Detailed game statistics (total plays, average scores, trends)
- Anonymous play supported (results not saved)

## Installation

### Prerequisites
- Python 3.7 or higher
- pip package manager

### Setup

1. Clone the repository:
```bash
git clone https://github.com/or-mihai-or-gheorghe/CS-Foundations-Tools.git
cd CS-Foundations-Tools
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
streamlit run app.py
```

4. Open your browser to `http://localhost:8501`

## Usage

1. Launch the application
2. Select a tool category from the sidebar
3. Choose a specific tool using the radio buttons
4. Enter your input values
5. Click the conversion/calculation button
6. Review the step-by-step explanation and results

Each tool provides:
- Interactive input fields
- Detailed step-by-step explanations
- Visual representations where applicable
- Verification of results
- Mathematical foundations

## Project Structure

```
CS-Foundations-Tools/
├── app.py                  # Main Streamlit application
├── pages/                  # Page modules
│   ├── foundations.py      # Educational tools page
│   └── games_hub.py        # Games and leaderboard page
├── tools/                  # Tool modules
│   ├── __init__.py
│   ├── binary_to_decimal.py
│   ├── gray_code_converter.py
│   ├── floating_point.py
│   ├── hamming_encode.py
│   ├── logic_kmap_sop.py
│   └── games/              # Game modules
│       ├── binary_speed_challenge.py
│       ├── speed_binary_addition.py
│       ├── speed_hex_conversion.py
│       └── game_utils.py
├── firebase/               # Firebase integration
│   ├── auth.py             # Authentication (Google OAuth + mock)
│   ├── database.py         # Realtime Database operations
│   ├── config.py           # Firebase configuration
│   └── mock_auth.py        # Local development mock auth
├── components/             # Reusable UI components
│   ├── auth_ui.py          # Sign-in/sign-out interface
│   ├── streamlit_auth.py   # Streamlit native OAuth integration
│   ├── leaderboard.py      # Leaderboard display
│   └── game_stats.py       # Global and per-game statistics
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Technologies

- **Streamlit** - Web application framework
- **NumPy** - Numerical computing for matrix operations
- **Firebase** - Authentication and Realtime Database for leaderboards
- **Python 3** - Core programming language

## Educational Context

This application is designed for students and educators studying:
- Computer Architecture
- Digital Logic Design
- Computer Organization
- Data Representation
- Error Detection and Correction
- Boolean Algebra

## Key Implementation Highlights

### Gray Code Converter
- Implements XOR-based conversion algorithm
- Verifies single-bit change property
- Supports both decimal and binary input

### Hamming Code Tools
- Uses formal H-matrix construction (MSB-at-top convention)
- Shows row-equation solving with mathematical notation
- Includes syndrome calculation and verification

### K-Map Minimizer
- Accepts multiple Boolean expression notations
- Uses prime implicant enumeration with set cover algorithm
- Renders visual K-maps with colored overlapping groups
- Supports torus wrapping for edge adjacency

### IEEE 754 Converter
- Demonstrates complete conversion process
- Shows precision loss analysis
- Converts results back for verification

## Firebase Setup (for Leaderboard Feature)

The leaderboard system uses Firebase Realtime Database with Google Authentication restricted to `@ase.ro` domain.

### Local Development (Mock Mode)

For local testing without Firebase:

1. Create `.streamlit/secrets.toml`:
```toml
[firebase]
use_mock_auth = true
api_key = "mock"
auth_domain = "mock"
database_url = "mock"
project_id = "mock"
storage_bucket = "mock"
messaging_sender_id = "mock"
app_id = "mock"
allowed_test_emails = ["test@ase.ro", "student@ase.ro"]
```

2. Sign in with any email from `allowed_test_emails` to test locally

### Production Setup

1. **Create Firebase Project:**
   - Go to [Firebase Console](https://console.firebase.google.com/)
   - Create new project: `cs-foundations-tools`
   - Disable Google Analytics (optional)

2. **Enable Authentication:**
   - Navigate to **Authentication** → **Get Started**
   - Click **Sign-in method** tab
   - Enable **Google** provider
   - Add authorized domain: `cs-fundamentals.streamlit.app`

3. **Enable Realtime Database:**
   - Navigate to **Realtime Database** → **Create Database**
   - Choose location: `europe-west1` (or closest to your users)
   - Start in **locked mode**

4. **Set Security Rules:**
   - Go to **Realtime Database** → **Rules** tab
   - Replace with:
```json
{
  "rules": {
    "users": {
      "$uid": {
        ".read": "auth != null",
        ".write": "auth.uid === $uid"
      }
    },
    "games": {
      "$game_slug": {
        ".read": "auth != null",
        "$game_id": {
          ".write": "auth != null && !data.exists() && newData.child('user_uid').val() === auth.uid"
        }
      }
    },
    "leaderboard": {
      ".read": true,
      ".write": false
    }
  }
}
```
   - Click **Publish**

5. **Get Configuration:**
   - Go to **Project Settings** (gear icon) → **General**
   - Under "Your apps" → Click **Web app** (`</>`)
   - Register app: `CS Foundations Tools`
   - Copy the `firebaseConfig` object

6. **Get Service Account Key:**
   - Go to **Project Settings** → **Service accounts**
   - Click **Generate new private key**
   - Download JSON file (keep it secure!)

7. **Configure Streamlit Secrets:**

For **Streamlit Cloud** (production):
   - Go to app settings → Secrets
   - Add:
```toml
[firebase]
use_mock_auth = false

# From firebaseConfig
api_key = "AIza..."
auth_domain = "your-project.firebaseapp.com"
database_url = "https://your-project-default-rtdb.firebaseio.com"
project_id = "your-project-id"
storage_bucket = "your-project.appspot.com"
messaging_sender_id = "123456789"
app_id = "1:123456789:web:abcdef..."

# From service account JSON
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "firebase-adminsdk-...@your-project.iam.gserviceaccount.com"
client_id = "..."
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
```

**Important:** Never commit the service account JSON or secrets to git! The `.gitignore` already excludes `.streamlit/secrets.toml`.

## Contributing

This is an educational project. Contributions, suggestions, and bug reports are welcome!

## License

This project is open source and available for educational purposes.

## About

Developed at the Faculty of Economic Cybernetics, Statistics and Informatics, Bucharest University of Economic Studies. Freely available for students and educators worldwide.

**Live Application:** [https://cs-fundamentals.streamlit.app/](https://cs-fundamentals.streamlit.app/)
