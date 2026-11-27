"""Handwritten Pratt/recursive-descent parser: tokens -> ``lang.ast`` (T3.3).

``parse(source, file=None)`` returns a ``Program``. Lexical errors surface as ``LexError``;
syntax errors as ``ParseError`` (``.location`` is a ``SourceLoc``).

Precedence, lowest to highest (MATLAB order): ``||``, ``&&``, ``|``, ``&``, comparisons,
``a:b:c`` ranges, ``+ -``, ``* / \\ .* ./ .\\``, unary ``+ - ~``, ``^ .^`` (left
associative; the exponent may carry a unary sign, so ``2^-1`` works), then postfix
``'``, ``.'``, ``(...)``, ``{...}`` and ``.name``.

Source positions: ``Binary.loc`` is the operator, ``Index``/``CellIndex``/``Field``/``Range``
use the start of their target or first operand, every other node uses its first token.

Not supported in v1 (clear ParseError): command syntax (``hold on``), dynamic fields
``s.(n)``, ``for (i = ...)`` parenthesised headers, ``~`` in function parameter lists.
Functions may end with ``end`` or run to the next ``function``/end of file.
"""

from __future__ import annotations

from engstudio.core.diagnostics import SourceLoc
from engstudio.core.errors import EngStudioError
from engstudio.lang import ast as A
from engstudio.lang.lexer import Token, tokenize

_BLOCK_WORDS = frozenset({"end", "else", "elseif", "case", "otherwise", "catch"})
_CMP_OPS = ("==", "~=", "<", "<=", ">", ">=")
_ADD_OPS = ("+", "-")
_MUL_OPS = ("*", "/", "\\", ".*", "./", ".\\")
_SIGNS = ("+", "-", "~")
_OPERAND_KINDS = ("IDENT", "NUMBER", "IMAG", "STRING", "DQSTRING")


class ParseError(EngStudioError):
    """Syntax error with a source location."""

    code = "E_PARSE"

    def __init__(self, message: str, location: SourceLoc | None = None) -> None:
        super().__init__(message)
        self.location = location

    def to_diagnostic(self, location: SourceLoc | None = None):  # type: ignore[override]
        return super().to_diagnostic(location or self.location)


def _describe(tok: Token) -> str:
    if tok.kind == "EOF":
        return "end of input"
    if tok.kind == "NEWLINE":
        return "end of line"
    return f"'{tok.text}'"


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.t = tokens
        self.i = 0
        self.depth = 0  # >0 while inside index arguments: 'end' and ':' are index forms

    # -- token helpers -----------------------------------------------------
    @property
    def tok(self) -> Token:
        return self.t[self.i]

    def peek(self, k: int = 1) -> Token:
        return self.t[min(self.i + k, len(self.t) - 1)]

    def advance(self) -> Token:
        t = self.t[self.i]
        if t.kind != "EOF":
            self.i += 1
        return t

    def at(self, kind: str) -> bool:
        return self.tok.kind == kind

    def at_kw(self, *names: str) -> bool:
        return self.tok.kind == "KEYWORD" and self.tok.text in names

    def err(self, message: str, tok: Token | None = None) -> ParseError:
        return ParseError(message, (tok or self.tok).loc)

    def unexpected(self) -> ParseError:
        return self.err(f"unexpected {_describe(self.tok)}")

    def expect(self, kind: str, what: str) -> Token:
        if self.tok.kind != kind:
            raise self.err(f"expected {what}, found {_describe(self.tok)}")
        return self.advance()

    # -- program / blocks --------------------------------------------------
    def program(self) -> A.Program:
        body = self.block(frozenset(), None, allow_eof=True)
        return A.Program(body, loc=self.t[0].loc)

    def block(
        self, terms: frozenset[str], opener: Token | None, allow_eof: bool = False
    ) -> tuple[A.Node, ...]:
        stmts: list[A.Node] = []
        while True:
            while self.tok.kind in ("NEWLINE", ";", ","):
                self.advance()
            t = self.tok
            if t.kind == "EOF":
                if allow_eof or opener is None:
                    break
                raise self.err(
                    f"missing 'end' for '{opener.text}' opened at line {opener.loc.line}"
                )
            if t.kind == "KEYWORD" and t.text in terms:
                break
            stmts.append(self.statement())
        return tuple(stmts)

    def header_sep(self) -> None:
        if self.tok.kind in (",", ";", "NEWLINE"):
            self.advance()

    def terminate(self, expr: A.Node | None = None) -> bool:
        """Consume a statement terminator; return True when the result is displayed."""
        t = self.tok
        if t.kind == ";":
            self.advance()
            return False
        if t.kind in (",", "NEWLINE"):
            self.advance()
            return True
        if t.kind == "EOF" or (t.kind == "KEYWORD" and t.text in _BLOCK_WORDS):
            return True
        if isinstance(expr, A.Ident) and t.kind in _OPERAND_KINDS:
            raise self.err(
                f"command syntax is not supported; write {expr.name}(...) with parentheses"
            )
        raise self.unexpected()

    # -- statements --------------------------------------------------------
    def statement(self) -> A.Node:
        t = self.tok
        if t.kind == "KEYWORD":
            return self.keyword_statement(t)
        if t.kind == "[" and self.is_multi_assign():
            return self.multi_assign()
        expr = self.expression()
        if self.at("="):
            self.advance()
            self.check_lvalue(expr, t)
            value = self.expression()
            return A.Assign((expr,), value, self.terminate(), loc=t.loc)
        return A.ExprStmt(expr, self.terminate(expr), loc=t.loc)

    def check_lvalue(self, node: A.Node, start: Token) -> None:
        base = node
        while isinstance(base, (A.Index, A.CellIndex, A.Field)):
            base = base.target
        if not isinstance(base, A.Ident):
            raise self.err("invalid assignment target", start)

    def is_multi_assign(self) -> bool:
        depth = 0
        j = self.i
        while True:
            k = self.t[j].kind
            if k == "[":
                depth += 1
            elif k == "]":
                depth -= 1
                if depth == 0:
                    return self.t[j + 1].kind == "="
            elif k in ("EOF", "NEWLINE"):
                return False
            j += 1

    def multi_assign(self) -> A.Node:
        start = self.advance()  # '['
        targets: list[A.Node] = []
        while True:
            while self.at(","):
                self.advance()
            if self.at("]"):
                break
            t = self.tok
            if t.kind == "~" and self.peek().kind in (",", "]"):
                self.advance()
                targets.append(A.Tilde(loc=t.loc))
            else:
                target = self.postfix()
                self.check_lvalue(target, t)
                targets.append(target)
            if not (self.at(",") or self.at("]")):
                raise self.err(f"expected ',' or ']', found {_describe(self.tok)}")
        self.advance()  # ']'
        self.expect("=", "'='")
        if not targets:
            raise self.err("empty output list", start)
        if all(isinstance(x, A.Tilde) for x in targets):
            raise self.err("at least one output must be named", start)
        if len(targets) == 1 and isinstance(targets[0], A.Tilde):
            raise self.err("'~' needs a multi-output assignment", start)
        value = self.expression()
        return A.Assign(tuple(targets), value, self.terminate(), loc=start.loc)

    def keyword_statement(self, t: Token) -> A.Node:
        word = t.text
        if word == "if":
            return self.if_statement()
        if word == "for":
            return self.for_statement()
        if word == "while":
            return self.while_statement()
        if word == "switch":
            return self.switch_statement()
        if word == "try":
            return self.try_statement()
        if word == "function":
            return self.function_def()
        if word in ("break", "continue", "return"):
            self.advance()
            self.terminate()
            node_type = {"break": A.Break, "continue": A.Continue, "return": A.Return}[word]
            return node_type(loc=t.loc)
        raise self.err(f"unexpected '{word}'")

    def if_statement(self) -> A.Node:
        kw = self.advance()
        clauses: list[A.IfClause] = []
        else_body: tuple[A.Node, ...] | None = None
        cond = self.expression()
        self.header_sep()
        body = self.block(frozenset({"elseif", "else", "end"}), kw)
        clauses.append(A.IfClause(cond, body, loc=kw.loc))
        while True:
            t = self.tok
            if t.text == "elseif":
                self.advance()
                cond = self.expression()
                self.header_sep()
                body = self.block(frozenset({"elseif", "else", "end"}), t)
                clauses.append(A.IfClause(cond, body, loc=t.loc))
            elif t.text == "else":
                self.advance()
                else_body = self.block(frozenset({"end"}), t)
            else:
                break
        self.advance()  # 'end'
        return A.If(tuple(clauses), else_body, loc=kw.loc)

    def for_statement(self) -> A.Node:
        kw = self.advance()
        var = self.expect("IDENT", "a loop variable name")
        self.expect("=", "'=' after the loop variable")
        iterable = self.expression()
        self.header_sep()
        body = self.block(frozenset({"end"}), kw)
        self.advance()
        return A.For(A.Ident(var.text, loc=var.loc), iterable, body, loc=kw.loc)

    def while_statement(self) -> A.Node:
        kw = self.advance()
        cond = self.expression()
        self.header_sep()
        body = self.block(frozenset({"end"}), kw)
        self.advance()
        return A.While(cond, body, loc=kw.loc)

    def switch_statement(self) -> A.Node:
        kw = self.advance()
        subject = self.expression()
        cases: list[A.Case] = []
        otherwise: tuple[A.Node, ...] | None = None
        while True:
            while self.tok.kind in ("NEWLINE", ";", ","):
                self.advance()
            t = self.tok
            if t.kind == "KEYWORD" and t.text == "case":
                self.advance()
                value = self.expression()
                self.header_sep()
                body = self.block(frozenset({"case", "otherwise", "end"}), t)
                cases.append(A.Case(value, body, loc=t.loc))
            elif t.kind == "KEYWORD" and t.text == "otherwise":
                self.advance()
                otherwise = self.block(frozenset({"end"}), t)
            elif t.kind == "KEYWORD" and t.text == "end":
                self.advance()
                break
            elif t.kind == "EOF":
                raise self.err(f"missing 'end' for 'switch' opened at line {kw.loc.line}")
            else:
                raise self.err(f"expected 'case', 'otherwise' or 'end', found {_describe(t)}")
        return A.Switch(subject, tuple(cases), otherwise, loc=kw.loc)

    def try_statement(self) -> A.Node:
        kw = self.advance()
        body = self.block(frozenset({"catch", "end"}), kw)
        catch_var: str | None = None
        catch_body: tuple[A.Node, ...] = ()
        if self.at_kw("catch"):
            ct = self.advance()
            if (
                self.tok.kind == "IDENT"
                and self.tok.loc.line == ct.loc.line
                and self.peek().kind in ("NEWLINE", ";", ",", "EOF")
            ):
                catch_var = self.advance().text
            catch_body = self.block(frozenset({"end"}), ct)
        self.advance()  # 'end'
        return A.TryCatch(body, catch_var, catch_body, loc=kw.loc)

    def name_list(self, closer: str, what: str) -> list[str]:
        names: list[str] = []
        while True:
            while self.at(","):
                self.advance()
            if self.at(closer):
                return names
            if self.at("~"):
                raise self.err("'~' placeholders in parameter lists are not supported")
            names.append(self.expect("IDENT", what).text)
            if not (self.at(",") or self.at(closer)):
                raise self.err(f"expected ',' or '{closer}', found {_describe(self.tok)}")

    def function_def(self) -> A.Node:
        kw = self.advance()
        outputs: list[str] = []
        if self.at("["):
            self.advance()
            outputs = self.name_list("]", "an output name")
            self.expect("]", "']'")
            self.expect("=", "'=' after the output list")
            name = self.expect("IDENT", "a function name")
        elif self.tok.kind == "IDENT" and self.peek().kind == "=":
            outputs = [self.advance().text]
            self.advance()
            name = self.expect("IDENT", "a function name")
        else:
            name = self.expect("IDENT", "a function name")
        params: list[str] = []
        if self.at("("):
            self.advance()
            params = self.name_list(")", "a parameter name")
            self.expect(")", "')'")
        if len(set(params)) != len(params):
            raise self.err("duplicate parameter name", name)
        if len(set(outputs)) != len(outputs):
            raise self.err("duplicate output name", name)
        body = self.block(frozenset({"end", "function"}), kw, allow_eof=True)
        if self.at_kw("end"):
            self.advance()
        return A.FunctionDef(name.text, tuple(params), tuple(outputs), body, loc=kw.loc)

    # -- expressions -------------------------------------------------------
    def expression(self) -> A.Node:
        return self.binary(("||",), self.and_and)

    def and_and(self) -> A.Node:
        return self.binary(("&&",), self.or_)

    def or_(self) -> A.Node:
        return self.binary(("|",), self.and_)

    def and_(self) -> A.Node:
        return self.binary(("&",), self.comparison)

    def comparison(self) -> A.Node:
        return self.binary(_CMP_OPS, self.range_)

    def additive(self) -> A.Node:
        return self.binary(_ADD_OPS, self.multiplicative)

    def multiplicative(self) -> A.Node:
        return self.binary(_MUL_OPS, self.unary)

    def binary(self, ops, sub) -> A.Node:
        left = sub()
        while self.tok.kind in ops:
            op = self.advance()
            right = sub()
            left = A.Binary(op.kind, left, right, loc=op.loc)
        return left

    def range_(self) -> A.Node:
        first = self.additive()
        if not self.at(":"):
            return first
        self.advance()
        second = self.additive()
        if self.at(":"):
            self.advance()
            third = self.additive()
            return A.Range(first, second, third, loc=first.loc)
        return A.Range(first, None, second, loc=first.loc)

    def unary(self) -> A.Node:
        if self.tok.kind in _SIGNS:
            op = self.advance()
            return A.Unary(op.kind, self.unary(), loc=op.loc)
        return self.power()

    def power(self) -> A.Node:
        left = self.postfix()
        while self.tok.kind in ("^", ".^"):
            op = self.advance()
            right = self.power_operand()
            left = A.Binary(op.kind, left, right, loc=op.loc)
        return left

    def power_operand(self) -> A.Node:
        if self.tok.kind in _SIGNS:
            op = self.advance()
            return A.Unary(op.kind, self.power_operand(), loc=op.loc)
        return self.postfix()

    def postfix(self) -> A.Node:
        expr = self.primary()
        while True:
            k = self.tok.kind
            if k == "(":
                expr = A.Index(expr, self.args("(", ")"), loc=expr.loc)
            elif k == "{":
                expr = A.CellIndex(expr, self.args("{", "}"), loc=expr.loc)
            elif k == ".":
                self.advance()
                if self.at("("):
                    raise self.err("dynamic field names s.(expr) are not supported")
                name = self.expect("IDENT", "a field name after '.'")
                expr = A.Field(expr, name.text, loc=expr.loc)
            elif k == "TRANSPOSE":
                t = self.advance()
                expr = A.Postfix(t.text, expr, loc=t.loc)
            else:
                return expr

    def args(self, opener: str, closer: str) -> tuple[A.Node, ...]:
        self.advance()  # opener
        self.depth += 1
        out: list[A.Node] = []
        if self.at(closer):
            self.advance()
            self.depth -= 1
            return ()
        while True:
            if self.at(":") and self.peek().kind in (",", closer):
                out.append(A.Colon(loc=self.advance().loc))
            else:
                out.append(self.expression())
            if self.at(","):
                self.advance()
            elif self.at(closer):
                self.advance()
                break
            else:
                raise self.err(f"expected ',' or '{closer}', found {_describe(self.tok)}")
        self.depth -= 1
        return tuple(out)

    def primary(self) -> A.Node:
        t = self.tok
        k = t.kind
        if k == "NUMBER":
            self.advance()
            return A.Number(t.value, loc=t.loc)
        if k == "IMAG":
            self.advance()
            return A.Imag(t.value, loc=t.loc)
        if k in ("STRING", "DQSTRING"):
            self.advance()
            return A.String(t.value, k == "DQSTRING", loc=t.loc)
        if k == "IDENT":
            self.advance()
            return A.Ident(t.text, loc=t.loc)
        if k == "KEYWORD" and t.text == "end" and self.depth > 0:
            self.advance()
            return A.End(loc=t.loc)
        if k == "(":
            self.advance()
            inner = self.expression()
            self.expect(")", "')'")
            return inner
        if k == "[":
            return self.rows("]", A.Matrix)
        if k == "{":
            return self.rows("}", A.CellLiteral)
        if k == "@":
            return self.function_handle()
        raise self.unexpected()

    def rows(self, closer: str, node_type) -> A.Node:
        start = self.advance()
        rows: list[tuple[A.Node, ...]] = []
        row: list[A.Node] = []
        while True:
            k = self.tok.kind
            if k == closer:
                self.advance()
                break
            if k == ",":
                self.advance()
            elif k == ";":
                self.advance()
                if row:
                    rows.append(tuple(row))
                    row = []
            elif k in ("EOF", "NEWLINE"):
                raise self.unexpected()
            else:
                row.append(self.expression())
                if self.tok.kind not in (",", ";", closer):
                    raise self.err(f"expected ',' or '{closer}', found {_describe(self.tok)}")
        if row:
            rows.append(tuple(row))
        return node_type(tuple(rows), loc=start.loc)

    def function_handle(self) -> A.Node:
        at = self.advance()  # '@'
        if self.at("("):
            self.advance()
            params = self.name_list(")", "a parameter name")
            self.expect(")", "')'")
            if len(set(params)) != len(params):
                raise self.err("duplicate parameter name", at)
            if self.tok.kind == "," and self.tok.synthetic:
                self.advance()  # lexer split "@(x) body" inside [] or {}
            return A.AnonFunc(tuple(params), self.expression(), loc=at.loc)
        name = self.expect("IDENT", "a function name or '(' after '@'")
        return A.FuncHandle(name.text, loc=at.loc)


def parse(source: str, file: str | None = None) -> A.Program:
    """Parse ``source`` into a ``Program``. Raises ``LexError`` or ``ParseError``."""
    return _Parser(tokenize(source, file)).program()
