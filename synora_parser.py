from pathlib import Path
import sys

from synora_lexical_analyzer import SynoraScanner


class ParseError(Exception):
    """Stores and displays a syntax error with its source location."""

    def __init__(self, message, token=None):
        self.message = message
        self.token = token

        if token is None:
            location = "at end of file"
        else:
            location = (
                f"at line {token.line}, "
                f"column {token.column}"
            )

        super().__init__(f"Syntax error {location}: {message}")


# RECURSIVE DESCENT PARSER

class SynoraParser:

    TYPE_WORDS = {
        "whole",
        "decimal",
        "text",
        "flag",
    }

    LITERAL_TYPES = {
        "INTEGER_LITERAL",
        "DECIMAL_LITERAL",
        "STRING_LITERAL",
        "BOOLEAN_LITERAL",
    }

    def __init__(self, tokens):
        self.tokens = tokens
        self.position = 0

    # TOKEN STREAM UTILITIES

    def current(self):
        """Return the current token, or None at the end."""
        if self.position < len(self.tokens):
            return self.tokens[self.position]
        return None

    def lookahead(self, offset=1):
        """Return a future token without consuming it."""
        index = self.position + offset
        if index < len(self.tokens):
            return self.tokens[index]
        return None

    def at_end(self):
        return self.current() is None

    def token_text(self):
        token = self.current()
        return token.text if token is not None else None

    def check_text(self, text):
        token = self.current()
        return token is not None and token.text == text

    def check_type(self, token_type):
        token = self.current()
        return (
            token is not None
            and token.token_type == token_type
        )

    def advance(self):
        """Consume and return the current token."""
        token = self.current()
        if token is not None:
            self.position += 1
        return token

    def error(self, message):
        raise ParseError(message, self.current())

    # TERMINAL MATCHING

    def expect(self, expected_text):
        """
        Match a terminal using its exact token text.
        Examples: begin, finish, =, ;, (, ).
        """
        if not self.check_text(expected_text):
            found = self.token_text()
            self.error(
                f"Expected {expected_text!r}, found {found!r}."
            )
        return self.advance()

    def expect_type(self, expected_type):
        """
        Match a terminal using its token type.
        Examples: IDENTIFIER, INTEGER_LITERAL.
        """
        if not self.check_type(expected_type):
            token = self.current()

            if token is None:
                found = "end of file"
            else:
                found = f"{token.text!r} ({token.token_type})"

            self.error(
                f"Expected token type {expected_type}, "
                f"found {found}."
            )

        return self.advance()

    # 3. PROGRAM AND TOP-LEVEL ITEMS

    def parse(self):
        """Start parsing and ensure no tokens remain afterward."""
        self.parse_program()

        if not self.at_end():
            self.error(
                f"Unexpected token {self.token_text()!r} "
                "after program end."
            )

    def parse_program(self):
        """
        <program> ::= begin <top-level-items> finish

        Function definitions and ordinary statements are
        accepted as top-level items, matching the uploaded parser.
        """
        self.expect("begin")

        while not self.check_text("finish") and not self.at_end():
            if self.check_text("define"):
                self.parse_function_definition()
            else:
                self.parse_statement()

        self.expect("finish")

    # 4. STATEMENTS AND STATEMENT LISTS

    def parse_statement_list(self, stop_words):
        """
        Parse statements until a stopping keyword is reached.
        Each successful statement must consume input.
        """
        while (
            not self.at_end()
            and self.token_text() not in stop_words
        ):
            self.parse_statement()

    def parse_statement(self):
        """Choose the correct non-terminal from the current token."""
        token = self.current()

        if token is None:
            self.error("Expected a statement, found end of file.")

        word = token.text

        if word == "make":
            self.parse_declaration()
        elif word in self.TYPE_WORDS:
            self.parse_typed_declaration()
        elif word == "set":
            self.parse_assignment()
        elif word == "show":
            self.parse_output()
        elif word == "ask":
            self.parse_input()
        elif word == "when":
            self.parse_conditional()
        elif word == "while":
            self.parse_while_loop()
        elif word == "repeat":
            self.parse_repeat_loop()
        elif word == "switch":
            self.parse_switch()
        elif word == "give":
            self.parse_return_statement()
        elif token.token_type == "IDENTIFIER":
            self.parse_call_statement()
        else:
            self.error(
                f"Token {word!r} cannot start a statement."
            )

    # 5. DECLARATIONS AND ASSIGNMENTS

    def parse_declaration(self):
        # make <identifier> = <expression> ;
        self.expect("make")
        self.expect_type("IDENTIFIER")
        self.expect("=")
        self.parse_expression()
        self.expect(";")

    def parse_typed_declaration(self):
        # <type> <identifier> = <expression> ;
        self.parse_type()
        self.expect_type("IDENTIFIER")
        self.expect("=")
        self.parse_expression()
        self.expect(";")

    def parse_assignment(self):
        # set <identifier> = <expression> ;
        self.expect("set")
        self.expect_type("IDENTIFIER")
        self.expect("=")
        self.parse_expression()
        self.expect(";")

    def parse_call_statement(self):
        # <function-call> ;
        self.parse_function_call()
        self.expect(";")

    # 6. INPUT AND OUTPUT

    def parse_output(self):
        # show <expression> ;
        self.expect("show")
        self.parse_expression()
        self.expect(";")

    def parse_input(self):
        # ask <identifier> ;
        self.expect("ask")
        self.expect_type("IDENTIFIER")
        self.expect(";")

    # 7. CONDITIONALS AND LOOPS

    def parse_conditional(self):
        # when <expression> do <statements>
        # [otherwise <statements>] stop
        self.expect("when")
        self.parse_expression()
        self.expect("do")

        self.parse_statement_list({"otherwise", "stop"})

        if self.check_text("otherwise"):
            self.advance()
            self.parse_statement_list({"stop"})

        self.expect("stop")

    def parse_while_loop(self):
        # while <expression> do <statements> stop
        self.expect("while")
        self.parse_expression()
        self.expect("do")
        self.parse_statement_list({"stop"})
        self.expect("stop")

    def parse_repeat_loop(self):
        # repeat <expression> times <statements> stop
        self.expect("repeat")
        self.parse_expression()
        self.expect("times")
        self.parse_statement_list({"stop"})
        self.expect("stop")

    # 8. SWITCH, CASE AND DEFAULT

    def parse_switch(self):
        # switch <expression>
        # case <literal> do <statements>
        # [case ...] [default do <statements>] stop

        self.expect("switch")
        self.parse_expression()

        if not self.check_text("case"):
            self.error(
                "A switch statement must contain "
                "at least one case."
            )

        while self.check_text("case"):
            self.advance()
            self.parse_literal()
            self.expect("do")
            self.parse_statement_list(
                {"case", "default", "stop"}
            )

        if self.check_text("default"):
            self.advance()
            self.expect("do")
            self.parse_statement_list({"stop"})

        self.expect("stop")

    def parse_literal(self):
        """A case label must be a literal token."""
        token = self.current()

        if token is None:
            self.error("Expected a literal, found end of file.")

        if token.token_type in self.LITERAL_TYPES:
            self.advance()
            return

        self.error(
            "A case label must be an integer, decimal, "
            "string, or Boolean literal."
        )

    # 9. FUNCTIONS AND RETURN STATEMENTS

    def parse_function_definition(self):
        # define <return-type> <identifier>
        # ( <parameter-list> ) <statements> stop

        self.expect("define")
        self.parse_return_type()
        self.expect_type("IDENTIFIER")
        self.expect("(")
        self.parse_parameter_list()
        self.expect(")")

        self.parse_statement_list({"stop"})
        self.expect("stop")

    def parse_return_type(self):
        if self.check_text("void"):
            self.advance()
        else:
            self.parse_type()

    def parse_parameter_list(self):
        # Empty parameter list is allowed.
        if self.check_text(")"):
            return

        while True:
            self.parse_type()
            self.expect_type("IDENTIFIER")

            if not self.check_text(","):
                break

            self.advance()

            # A comma must be followed by another parameter.
            if self.check_text(")"):
                self.error("Expected a parameter after ','.")

    def parse_return_statement(self):
        # give [<expression>] ;
        self.expect("give")

        if not self.check_text(";"):
            self.parse_expression()

        self.expect(";")

    # ========================================================
    # 10. EXPRESSIONS
    #
    # Precedence (highest to lowest):
    # 1. Unary
    # 2. Multiplication, division, modulus
    # 3. Addition, subtraction
    # 4. Relational operators
    # 5. Equality operators
    # 6. AND
    # 7. OR
    # ========================================================

    def parse_expression(self):
        self.parse_or()

    def parse_or(self):
        self.parse_and()

        while self.check_text("or"):
            self.advance()
            self.parse_and()

    def parse_and(self):
        self.parse_equality()

        while self.check_text("and"):
            self.advance()
            self.parse_equality()

    def parse_equality(self):
        self.parse_relational()

        if self.token_text() in {"==", "!="}:
            self.advance()
            self.parse_relational()

            if self.token_text() in {"==", "!="}:
                self.error(
                    "Equality operators are non-associative; "
                    "use parentheses to make the intended "
                    "comparison clear."
                )

    def parse_relational(self):
        self.parse_additive()

        if self.token_text() in {"<", "<=", ">", ">="}:
            self.advance()
            self.parse_additive()

            if self.token_text() in {"<", "<=", ">", ">="}:
                self.error(
                    "Relational operators are non-associative; "
                    "chained comparisons are not allowed."
                )

    def parse_additive(self):
        self.parse_multiplicative()

        while self.token_text() in {"+", "-"}:
            self.advance()
            self.parse_multiplicative()

    def parse_multiplicative(self):
        self.parse_unary()

        while self.token_text() in {"*", "/", "%"}:
            self.advance()
            self.parse_unary()

    def parse_unary(self):
        if self.check_text("not") or self.check_text("-"):
            self.advance()
            self.parse_unary()
        else:
            self.parse_primary()

    # 11. PRIMARY EXPRESSIONS, VARIABLES AND CASTS

    def parse_primary(self):
        token = self.current()

        if token is None:
            self.error(
                "Expected an expression, found end of file."
            )

        # Parenthesized expression: ( <expression> )
        if self.check_text("("):
            self.advance()
            self.parse_expression()
            self.expect(")")
            return

        # Type casting: <type> ( <expression> )
        if (
            token.text in self.TYPE_WORDS
            and self.lookahead() is not None
            and self.lookahead().text == "("
        ):
            self.advance()
            self.expect("(")
            self.parse_expression()
            self.expect(")")
            return

        # Identifier or function call.
        if token.token_type == "IDENTIFIER":
            if (
                self.lookahead() is not None
                and self.lookahead().text == "("
            ):
                self.parse_function_call()
            else:
                self.advance()
            return

        # Literal.
        if token.token_type in self.LITERAL_TYPES:
            self.advance()
            return

        self.error(
            f"Unexpected token {token.text!r} in expression."
        )

    # 12. FUNCTION CALLS AND ARGUMENTS

    def parse_function_call(self):
        # <identifier> ( <argument-list> )
        self.expect_type("IDENTIFIER")
        self.expect("(")
        self.parse_argument_list()
        self.expect(")")

    def parse_argument_list(self):
        # Empty argument list is allowed.
        if self.check_text(")"):
            return

        while True:
            self.parse_expression()

            if not self.check_text(","):
                break

            self.advance()

            if self.check_text(")"):
                self.error("Expected an argument after ','.")

    # 13. DATA TYPES

    def parse_type(self):
        token = self.current()

        if token is None or token.text not in self.TYPE_WORDS:
            self.error(
                "Expected a data type: "
                "whole, decimal, text, or flag."
            )

        return self.advance()


# 14. PROGRAM ENTRY POINT

def main():

    if len(sys.argv) != 2:
        print("Usage: python synora_parser.py program.syn")
        return 2

    path = Path(sys.argv[1])

    if path.suffix.lower() != ".syn":
        print(
            "Error: SYNORA source files must "
            "use the .syn extension."
        )
        return 2

    try:
        source = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        print(f"Error reading source file: {exc}")
        return 2

    # PHASE 1: LEXICAL ANALYSIS
    scanner = SynoraScanner(source)
    tokens, lexical_errors = scanner.scan()

    if lexical_errors:
        print("\nSYNORA LEXICAL ERRORS")

        for error in lexical_errors:
            print(
                f"Line {error.line}, "
                f"Column {error.column}: "
                f"{error.message} | {error.text!r}"
            )

        print(
            "\nParsing stopped because "
            "lexical errors were found."
        )
        return 1

    # PHASE 2: SYNTAX ANALYSIS
    parser = SynoraParser(tokens)

    try:
        parser.parse()
    except ParseError as error:
        print("\nSYNORA SYNTAX ERROR")
        print(error)
        return 1

    print("\nSYNORA SYNTAX ANALYSIS")
    print("Parsing successful.")
    print("No syntax errors found.")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
