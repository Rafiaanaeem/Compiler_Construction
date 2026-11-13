
from dataclasses import dataclass
from pathlib import Path
import sys


# ============================================================
# 1. RESERVED WORDS
# ============================================================

RESERVED_WORDS = {
    "begin": "KEYWORD",
    "finish": "KEYWORD",
    "make": "KEYWORD",
    "set": "KEYWORD",
    "whole": "KEYWORD",
    "decimal": "KEYWORD",
    "text": "KEYWORD",
    "flag": "KEYWORD",
    "show": "KEYWORD",
    "ask": "KEYWORD",
    "when": "KEYWORD",
    "do": "KEYWORD",
    "otherwise": "KEYWORD",
    "while": "KEYWORD",
    "repeat": "KEYWORD",
    "times": "KEYWORD",
    "define": "KEYWORD",
    "give": "KEYWORD",
    "stop": "KEYWORD",
    "switch": "KEYWORD",
    "case": "KEYWORD",
    "default": "KEYWORD",
    "void": "KEYWORD",

    "and": "LOGICAL_OPERATOR",
    "or": "LOGICAL_OPERATOR",
    "not": "LOGICAL_OPERATOR",

    "true": "BOOLEAN_LITERAL",
    "false": "BOOLEAN_LITERAL",
}


# ============================================================
# 2. OPERATORS AND DELIMITERS
# ============================================================

TWO_CHAR_OPERATORS = {
    "==": "RELATIONAL_OPERATOR",
    "!=": "RELATIONAL_OPERATOR",
    ">=": "RELATIONAL_OPERATOR",
    "<=": "RELATIONAL_OPERATOR",
}

ONE_CHAR_TOKENS = {
    "+": "ARITHMETIC_OPERATOR",
    "-": "ARITHMETIC_OPERATOR",
    "*": "ARITHMETIC_OPERATOR",
    "/": "ARITHMETIC_OPERATOR",
    "%": "ARITHMETIC_OPERATOR",

    ">": "RELATIONAL_OPERATOR",
    "<": "RELATIONAL_OPERATOR",

    "=": "ASSIGNMENT_OPERATOR",

    ";": "DELIMITER",
    "(": "DELIMITER",
    ")": "DELIMITER",
    ",": "DELIMITER",
}


# ============================================================
# 3. TOKEN AND ERROR STRUCTURES
# ============================================================

@dataclass
class Token:
    text: str
    token_type: str
    line: int
    column: int


@dataclass
class LexicalError:
    message: str
    text: str
    line: int
    column: int


# ============================================================
# 4. SYNORA SCANNER
# ============================================================

class SynoraScanner:

    def __init__(self, source):

        self.source = source.replace(
            "\r\n", "\n"
        ).replace("\r", "\n")

        self.index = 0
        self.line = 1
        self.column = 1

        self.tokens = []
        self.errors = []

    # --------------------------------------------------------
    # CHARACTER UTILITIES
    # --------------------------------------------------------

    def peek(self, offset=0):

        position = self.index + offset

        if position < len(self.source):
            return self.source[position]

        return ""

    def advance(self):

        if self.index >= len(self.source):
            return ""

        ch = self.source[self.index]

        self.index += 1

        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1

        return ch

    @staticmethod
    def is_letter(ch):

        return bool(ch) and (
            "A" <= ch <= "Z"
            or "a" <= ch <= "z"
        )

    @staticmethod
    def is_digit(ch):

        return bool(ch) and "0" <= ch <= "9"

    def add_token(self, text, token_type, line, column):

        self.tokens.append(
            Token(text, token_type, line, column)
        )

    def add_error(self, message, text, line, column):

        self.errors.append(
            LexicalError(message, text, line, column)
        )

    # --------------------------------------------------------
    # INVALID IDENTIFIER TAIL
    #
    # Collects illegal characters attached to an identifier.
    # --------------------------------------------------------

    def scan_invalid_identifier_tail(self):

        while self.peek():

            ch = self.peek()

            # Stop at whitespace and clear token separators.
            if ch.isspace() or ch in "=;(),":
                break

            # Stop at recognized arithmetic and relational
            # operators so they can be scanned separately.
            if ch in "+-*/><!":
                break

            # Other attached characters are collected as part
            # of the invalid identifier candidate.
            self.advance()

    # --------------------------------------------------------
    # IDENTIFIERS AND RESERVED WORDS
    #
    # Identifier:
    # Letter (Letter | Digit | _)*
    # --------------------------------------------------------

    def scan_identifier(self):

        start = self.index
        start_line = self.line
        start_column = self.column

        # Read valid identifier characters.
        while (
            self.is_letter(self.peek())
            or self.is_digit(self.peek())
            or self.peek() == "_"
        ):
            self.advance()

        # Check whether an invalid character is attached.
        ch = self.peek()

        if ch and not (
            ch.isspace()
            or ch in "=;(),"
            or ch in "+-*/><!#"
        ):

            # Collect the complete invalid candidate.
            self.scan_invalid_identifier_tail()

            text = self.source[start:self.index]

            self.add_error(
                "Invalid identifier",
                text,
                start_line,
                start_column
            )

            return

        # If valid, check whether it is a reserved word.
        text = self.source[start:self.index]

        token_type = RESERVED_WORDS.get(
            text, "IDENTIFIER"
        )

        self.add_token(
            text,
            token_type,
            start_line,
            start_column
        )

    # --------------------------------------------------------
    # INVALID IDENTIFIERS BEGINNING WITH UNDERSCORE
    # --------------------------------------------------------

    def scan_invalid_identifier(self):

        start = self.index
        start_line = self.line
        start_column = self.column

        # Consume the starting underscore.
        self.advance()

        # Consume normal identifier characters.
        while (
            self.is_letter(self.peek())
            or self.is_digit(self.peek())
            or self.peek() == "_"
        ):
            self.advance()

        # Check for additional invalid characters.
        ch = self.peek()

        if ch and not (
            ch.isspace()
            or ch in "=;(),"
            or ch in "+-*/><!#"
        ):
            self.scan_invalid_identifier_tail()

        text = self.source[start:self.index]

        self.add_error(
            "Invalid identifier",
            text,
            start_line,
            start_column
        )

    # --------------------------------------------------------
    # MALFORMED NUMBER HELPER
    # --------------------------------------------------------

    def consume_bad_number_tail(self):

        while True:

            ch = self.peek()

            if (
                self.is_letter(ch)
                or self.is_digit(ch)
                or ch in ("_", ".")
            ):
                self.advance()

            else:
                break

    # --------------------------------------------------------
    # INTEGER AND DECIMAL LITERALS
    #
    # Integer: digit+
    # Decimal: digit+ "." digit+
    # --------------------------------------------------------

    def scan_number(self):

        start = self.index
        start_line = self.line
        start_column = self.column

        while self.is_digit(self.peek()):
            self.advance()

        is_decimal = False
        malformed = False

        if self.peek() == ".":

            is_decimal = True

            self.advance()

            if not self.is_digit(self.peek()):
                malformed = True

            else:

                while self.is_digit(self.peek()):
                    self.advance()

        if (
            self.is_letter(self.peek())
            or self.peek() in ("_", ".")
        ):
            malformed = True

        if malformed:
            self.consume_bad_number_tail()

        text = self.source[start:self.index]

        if malformed:

            self.add_error(
                "Malformed numeric literal",
                text,
                start_line,
                start_column
            )

            return

        token_type = (
            "DECIMAL_LITERAL"
            if is_decimal
            else "INTEGER_LITERAL"
        )

        self.add_token(
            text,
            token_type,
            start_line,
            start_column
        )

    # --------------------------------------------------------
    # DECIMAL BEGINNING WITH A DOT
    #
    # Example: .5 (invalid)
    # --------------------------------------------------------

    def scan_leading_dot_number(self):

        start = self.index
        start_line = self.line
        start_column = self.column

        self.advance()

        while self.is_digit(self.peek()):
            self.advance()

        if (
            self.is_letter(self.peek())
            or self.peek() in ("_", ".")
        ):
            self.consume_bad_number_tail()

        text = self.source[start:self.index]

        self.add_error(
            "Malformed numeric literal: "
            "missing digits before decimal point",
            text,
            start_line,
            start_column
        )

    # --------------------------------------------------------
    # STRING LITERALS
    #
    # Strings use double quotation marks.
    # --------------------------------------------------------

    def scan_string(self):

        start = self.index
        start_line = self.line
        start_column = self.column

        self.advance()

        while self.peek() not in ("", '"', "\n"):
            self.advance()

        if self.peek() == '"':

            self.advance()

            text = self.source[start:self.index]

            self.add_token(
                text,
                "STRING_LITERAL",
                start_line,
                start_column
            )

        else:

            text = self.source[start:self.index]

            self.add_error(
                "Unterminated string literal",
                text,
                start_line,
                start_column
            )

    # --------------------------------------------------------
    # SINGLE-LINE COMMENTS
    #
    # Example: # This is a comment
    # --------------------------------------------------------

    def scan_line_comment(self):

        while self.peek() not in ("", "\n"):
            self.advance()

    # --------------------------------------------------------
    # MULTI-LINE COMMENTS
    #
    # Example:
    # /* This is
    #    a multiline comment */
    # --------------------------------------------------------

    def scan_block_comment(self):

        start = self.index
        start_line = self.line
        start_column = self.column

        self.advance()
        self.advance()

        while self.peek():

            if (
                self.peek() == "*"
                and self.peek(1) == "/"
            ):

                self.advance()
                self.advance()

                return

            self.advance()

        text = self.source[start:self.index]

        self.add_error(
            "Unterminated multiline comment",
            text,
            start_line,
            start_column
        )

    # --------------------------------------------------------
    # MAIN SCANNING METHOD
    # --------------------------------------------------------

    def scan(self):

        while self.peek():

            ch = self.peek()

            # Ignore whitespace.
            if ch.isspace():
                self.advance()
                continue

            start_line = self.line
            start_column = self.column

            # Single-line comments.
            if ch == "#":
                self.scan_line_comment()
                continue

            # Multiline comments.
            if ch == "/" and self.peek(1) == "*":
                self.scan_block_comment()
                continue

            # Unexpected comment terminator.
            if ch == "*" and self.peek(1) == "/":

                self.advance()
                self.advance()

                self.add_error(
                    "Unexpected comment terminator",
                    "*/",
                    start_line,
                    start_column
                )

                continue

            # String literals.
            if ch == '"':
                self.scan_string()
                continue

            # Integer and decimal literals.
            if self.is_digit(ch):
                self.scan_number()
                continue

            # Invalid decimal beginning with a dot.
            if (
                ch == "."
                and self.is_digit(self.peek(1))
            ):
                self.scan_leading_dot_number()
                continue

            # Two-character operators.
            # Longest match is checked first.
            pair = ch + self.peek(1)

            if pair in TWO_CHAR_OPERATORS:

                self.advance()
                self.advance()

                self.add_token(
                    pair,
                    TWO_CHAR_OPERATORS[pair],
                    start_line,
                    start_column
                )

                continue

            # Single-character operators and delimiters.
            if ch in ONE_CHAR_TOKENS:

                self.advance()

                self.add_token(
                    ch,
                    ONE_CHAR_TOKENS[ch],
                    start_line,
                    start_column
                )

                continue

            # Valid identifiers.
            if self.is_letter(ch):

                self.scan_identifier()
                continue

            # Invalid identifiers beginning with underscore.
            if ch == "_":

                self.scan_invalid_identifier()
                continue

            # Unknown symbols.
            self.advance()

            self.add_error(
                "Unknown symbol",
                ch,
                start_line,
                start_column
            )

        return self.tokens, self.errors


# ============================================================
# 5. DISPLAY RESULTS
# ============================================================

def print_results(filename, tokens, errors):

    print("\nSYNORA LEXICAL ANALYSIS")

    print(f"Source file: {filename}")

    print("-" * 78)

    print(
        f"{'TOKEN':<28}"
        f"{'TOKEN TYPE':<28}"
        f"{'LINE':>6}"
        f"{'COLUMN':>9}"
    )

    print("-" * 78)

    for token in tokens:

        print(
            f"{token.text!r:<28}"
            f"{token.token_type:<28}"
            f"{token.line:>6}"
            f"{token.column:>9}"
        )

    print("-" * 78)

    print(f"Total tokens: {len(tokens)}")

    if not errors:

        print("No lexical errors found.")

    else:

        print(f"Total lexical errors: {len(errors)}")

        print("\n--- LEXICAL ERRORS ---")

        for error in errors:

            print(
                f"Line {error.line}, "
                f"Column {error.column} | "
                f"{error.message} | "
                f"Token: {error.text!r}"
            )


# ============================================================
# 6. PROGRAM ENTRY POINT
# ============================================================

def main():

    if len(sys.argv) > 1:

        filename = sys.argv[1]

    else:

        filename = input(
            "Enter SYNORA source file name "
            "(e.g. program.syn): "
        ).strip()

    if not filename:

        print("Error: no source filename provided.")

        return 2

    path = Path(filename)

    if path.suffix.lower() != ".syn":

        print(
            "Error: SYNORA source files must "
            "use the .syn extension."
        )

        return 2

    try:

        source = path.read_text(
            encoding="utf-8-sig"
        )

    except (OSError, UnicodeError) as exc:

        print(f"Error reading source file: {exc}")

        return 2

    scanner = SynoraScanner(source)

    tokens, errors = scanner.scan()

    print_results(
        str(path),
        tokens,
        errors
    )

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
