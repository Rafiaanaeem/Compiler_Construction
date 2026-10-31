
from dataclasses import dataclass
from pathlib import Path
import sys
import unittest


# 1. RESERVED WORDS

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


# 2. OPERATORS AND DELIMITERS

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


# 3. TOKEN AND ERROR STRUCTURES

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


# 4. SYNORA SCANNER

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

    # Character utilities

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
            "A" <= ch <= "Z" or "a" <= ch <= "z"
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

    # Identifiers and reserved words
    # Identifier: letter (letter | digit | _)*

    # def scan_identifier(self):
    #     start = self.index
    #     start_line = self.line
    #     start_column = self.column

    #     self.advance()

    #     while (
    #         self.is_letter(self.peek())
    #         or self.is_digit(self.peek())
    #         or self.peek() == "_"
    #     ):
    #         self.advance()

    #     text = self.source[start:self.index]
    #     token_type = RESERVED_WORDS.get(text, "IDENTIFIER")

    #     self.add_token(
    #         text, token_type, start_line, start_column
    #     )

    
    def scan_identifier(self):
        start = self.index
        start_line = self.line
        start_column = self.column

        # Collect the complete candidate token.
        # Whitespace ends the candidate.
        while self.peek() and not self.peek().isspace():
            self.advance()

        text = self.source[start:self.index]

        # A valid identifier must start with a letter
        # and contain only letters, digits, or underscores.
        valid_identifier = (
            bool(text)
            and self.is_letter(text[0])
            and all(
                self.is_letter(ch)
                or self.is_digit(ch)
                or ch == "_"
                for ch in text
            )
        )

        if not valid_identifier:
            self.add_error(
                "Invalid identifier",
                text,
                start_line,
                start_column,
            )
            return

        token_type = RESERVED_WORDS.get(text, "IDENTIFIER")
        self.add_token(
            text,
            token_type,
            start_line,
            start_column,
        )


    # Malformed numeric literal helper

    def consume_bad_number_tail(self):
        """
        Consume adjacent letters, digits, underscores, and dots
        so malformed numeric spellings can be reported together.
        """

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

    # Integer and decimal literals
    # Integer: digit+
    # Decimal: digit+ "." digit+

    def scan_number(self):
        start = self.index
        start_line = self.line
        start_column = self.column

        # Read integer digits.
        while self.is_digit(self.peek()):
            self.advance()

        is_decimal = False
        malformed = False

        # Optional decimal point.
        if self.peek() == ".":
            is_decimal = True
            self.advance()

            # A decimal requires digits after the dot.
            if not self.is_digit(self.peek()):
                malformed = True
            else:
                while self.is_digit(self.peek()):
                    self.advance()

        # Reject adjacent letters, underscores, or extra dots.
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
                start_column,
            )
            return

        token_type = (
            "DECIMAL_LITERAL"
            if is_decimal
            else "INTEGER_LITERAL"
        )

        self.add_token(
            text, token_type, start_line, start_column
        )

    # Decimal beginning with a dot: .5, .5abc, etc.
    # These are invalid because a decimal needs digits before
    # and after the decimal point.

    def scan_leading_dot_number(self):
        start = self.index
        start_line = self.line
        start_column = self.column

        self.advance()  # Consume the dot.

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
            start_column,
        )

    # Strings
    # Strings use double quotes. Escape sequences are not
    # implemented because they are not defined in the spec.

    def scan_string(self):
        start = self.index
        start_line = self.line
        start_column = self.column

        self.advance()  # Opening quote.

        while self.peek() not in ("", '"', "\n"):
            self.advance()

        if self.peek() == '"':
            self.advance()

            text = self.source[start:self.index]

            self.add_token(
                text,
                "STRING_LITERAL",
                start_line,
                start_column,
            )
        else:
            text = self.source[start:self.index]

            self.add_error(
                "Unterminated string literal",
                text,
                start_line,
                start_column,
            )

    # Single-line comments: # ...

    def scan_line_comment(self):
        while self.peek() not in ("", "\n"):
            self.advance()

    # Multiline comments: /* ... */

    def scan_block_comment(self):
        start = self.index
        start_line = self.line
        start_column = self.column

        self.advance()  # /
        self.advance()  # *

        while self.peek():
            if self.peek() == "*" and self.peek(1) == "/":
                self.advance()
                self.advance()
                return

            self.advance()

        text = self.source[start:self.index]

        self.add_error(
            "Unterminated multiline comment",
            text,
            start_line,
            start_column,
        )

    # Main scanning loop

    
    def scan(self):
        while self.peek():
            ch = self.peek()

            # Ignore whitespace.
            if ch.isspace():
                self.advance()
                continue

            start_line = self.line
            start_column = self.column

            # Single-line comment.
            if ch == "#":
                self.scan_line_comment()
                continue

            # Multiline comment.
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
                    start_column,
                )
                continue

            # String literal.
            if ch == '"':
                self.scan_string()
                continue

            # Integer or decimal literal.
            if self.is_digit(ch):
                self.scan_number()
                continue

            # Invalid decimal beginning with a dot.
            if ch == "." and self.is_digit(self.peek(1)):
                self.scan_leading_dot_number()
                continue

            # Longest match: two-character operators first.
            pair = ch + self.peek(1)

            if pair in TWO_CHAR_OPERATORS:
                self.advance()
                self.advance()
                self.add_token(
                    pair,
                    TWO_CHAR_OPERATORS[pair],
                    start_line,
                    start_column,
                )
                continue

            # Single-character operators and delimiters.
            if ch in ONE_CHAR_TOKENS:
                self.advance()
                self.add_token(
                    ch,
                    ONE_CHAR_TOKENS[ch],
                    start_line,
                    start_column,
                )
                continue

            # Identifier or invalid identifier candidate.
            if (
                self.is_letter(ch)
                or ch == "_"
                or (
                    not ch.isspace()
                    and ch not in ONE_CHAR_TOKENS
                    and ch not in ('"', "#", "/")
                )
            ):
                self.scan_identifier()
                continue

            # Any remaining character is invalid.
            self.advance()
            self.add_error(
                "Unknown symbol",
                ch,
                start_line,
                start_column,
            )

        return self.tokens, self.errors



# 5. DISPLAY RESULTS

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
                f"Line {error.line}, Column {error.column} | "
                f"{error.message} | Token: {error.text!r}"
            )


# 6. AUTOMATED TESTS

# class SynoraScannerTests(unittest.TestCase):

#     def scan_text(self, source):
#         scanner = SynoraScanner(source)
#         return scanner.scan()

#     def test_keywords_identifiers_booleans(self):
#         tokens, errors = self.scan_text(
#             "begin finish my_var item2 true false and"
#         )

#         self.assertEqual(errors, [])
#         self.assertEqual(
#             [t.token_type for t in tokens],
#             [
#                 "KEYWORD",
#                 "KEYWORD",
#                 "IDENTIFIER",
#                 "IDENTIFIER",
#                 "BOOLEAN_LITERAL",
#                 "BOOLEAN_LITERAL",
#                 "LOGICAL_OPERATOR",
#             ],
#         )

#     def test_numbers(self):
#         tokens, errors = self.scan_text(
#             "0 123 12.34 0.93"
#         )

#         self.assertEqual(errors, [])
#         self.assertEqual(
#             [t.token_type for t in tokens],
#             [
#                 "INTEGER_LITERAL",
#                 "INTEGER_LITERAL",
#                 "DECIMAL_LITERAL",
#                 "DECIMAL_LITERAL",
#             ],
#         )

#     def test_malformed_numbers(self):
#         _tokens, errors = self.scan_text(
#             "12. .5 12abc 12.5abc 4.2.1 12.. .5abc"
#         )

#         self.assertEqual(len(errors), 7)

#     def test_operators(self):
#         tokens, errors = self.scan_text(
#             "+ - * / % == != >= <= > < ="
#         )

#         self.assertEqual(errors, [])
#         self.assertEqual(
#             [t.token_type for t in tokens],
#             [
#                 "ARITHMETIC_OPERATOR",
#                 "ARITHMETIC_OPERATOR",
#                 "ARITHMETIC_OPERATOR",
#                 "ARITHMETIC_OPERATOR",
#                 "ARITHMETIC_OPERATOR",
#                 "RELATIONAL_OPERATOR",
#                 "RELATIONAL_OPERATOR",
#                 "RELATIONAL_OPERATOR",
#                 "RELATIONAL_OPERATOR",
#                 "RELATIONAL_OPERATOR",
#                 "RELATIONAL_OPERATOR",
#                 "ASSIGNMENT_OPERATOR",
#             ],
#         )

#     def test_increment_and_decrement_are_not_special_tokens(self):
#         tokens, errors = self.scan_text("++ --")

#         self.assertEqual(errors, [])
#         self.assertEqual(len(tokens), 4)
#         self.assertTrue(
#             all(
#                 t.token_type == "ARITHMETIC_OPERATOR"
#                 for t in tokens
#             )
#         )

#     def test_strings(self):
#         tokens, errors = self.scan_text(
#             '"hello world"\n"unfinished'
#         )

#         self.assertEqual(
#             [t.token_type for t in tokens],
#             ["STRING_LITERAL"],
#         )
#         self.assertEqual(len(errors), 1)

#     def test_comments(self):
#         tokens, errors = self.scan_text(
#             "begin # line comment\n"
#             "/* multiline\ncomment */ finish"
#         )

#         self.assertEqual(errors, [])
#         self.assertEqual(
#             [t.text for t in tokens],
#             ["begin", "finish"],
#         )

#     def test_unterminated_block_comment(self):
#         _tokens, errors = self.scan_text(
#             "begin /* unfinished"
#         )

#         self.assertEqual(len(errors), 1)
#         self.assertEqual(
#             errors[0].message,
#             "Unterminated multiline comment",
#         )

#     def test_unexpected_comment_terminator(self):
#         _tokens, errors = self.scan_text("*/")
#         self.assertEqual(len(errors), 1)

#     def test_unknown_symbols(self):
#         _tokens, errors = self.scan_text("$ @")
#         self.assertEqual(len(errors), 2)

#     def test_invalid_identifier(self):
#         _tokens, errors = self.scan_text("_name")

#         self.assertEqual(len(errors), 1)
#         self.assertIn(
#             "Invalid identifier",
#             errors[0].message,
#         )

#     def test_line_and_column(self):
#         tokens, errors = self.scan_text("begin\r\nshow 1;")

#         self.assertEqual(errors, [])
#         self.assertEqual(
#             (tokens[1].line, tokens[1].column),
#             (2, 1),
#         )

#     def test_valid_program(self):
#         source = (
#             "begin\n"
#             "make whole age = 18;\n"
#             "make decimal average = 12.5;\n"
#             'make text message = "Hello";\n'
#             "make flag active = true;\n"
#             "show message;\n"
#             "finish\n"
#         )

#         _tokens, errors = self.scan_text(source)
#         self.assertEqual(errors, [])


# 7. PROGRAM ENTRY POINT

def main():

    # Run automated tests:
    # python synora_lexical_analyzer.py --test
    # if len(sys.argv) == 2 and sys.argv[1] == "--test":
    #     suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    #         SynoraScannerTests
    #     )

    #     result = unittest.TextTestRunner(
    #         verbosity=2
    #     ).run(suite)

    #     return 0 if result.wasSuccessful() else 1

    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = input(
            "Enter SYNORA source file name (e.g. program.syn): "
        ).strip()

    if not filename:
        print("Error: no source filename provided.")
        return 2

    path = Path(filename)

    if path.suffix.lower() != ".syn":
        print(
            "Error: SYNORA source files must use the .syn extension."
        )
        return 2

    try:
        source = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        print(f"Error reading source file: {exc}")
        return 2

    scanner = SynoraScanner(source)
    tokens, errors = scanner.scan()

    print_results(str(path), tokens, errors)

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
