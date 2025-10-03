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
├── tools/                  # Tool modules
│   ├── __init__.py
│   ├── binary_to_decimal.py
│   ├── decimal_to_binary.py
│   ├── gray_code_converter.py
│   ├── multi_format_converter.py
│   ├── raw_binary_arithmetic.py
│   ├── twos_complement_arithmetic.py
│   ├── bcd_arithmetic.py
│   ├── floating_point.py
│   ├── decimal_converter.py
│   ├── special_values.py
│   ├── fp_arithmetic.py
│   ├── hamming_encode.py
│   ├── hamming_decode.py
│   ├── crc_encode.py
│   ├── crc_decode.py
│   └── logic_kmap_sop.py
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Technologies

- **Streamlit** - Web application framework
- **NumPy** - Numerical computing for matrix operations
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

## Contributing

This is an educational project. Contributions, suggestions, and bug reports are welcome!

## License

This project is open source and available for educational purposes.

## About

Developed at the Faculty of Economic Cybernetics, Statistics and Informatics, Bucharest University of Economic Studies. Freely available for students and educators worldwide.

**Live Application:** [https://cs-fundamentals.streamlit.app/](https://cs-fundamentals.streamlit.app/)
