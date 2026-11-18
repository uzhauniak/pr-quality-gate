"""Targeted mutation testing: mutate only the source lines a PR changed.

    python quality/mutate.py --base origin/main
    python quality/mutate.py --lines services/pricing/src/pricing/engine.py:67

For each changed line, small semantic edits are applied one at a time (`>` → `>=`,
`+` → `-`, `0.03` → `1.03`, `and` → `or`, a response field renamed, ...) and the owning
service's unit + integration tests run. A mutant the tests don't notice ("survivor")
means that line could be wrong and CI would stay green. Any survivor fails the check.

Why not mutmut / cosmic-ray over the whole module? Those answer "how good is this suite
overall?" and belong in a nightly job. A PR gate needs "is *this change* tested?",
in seconds, so this runner is scoped to changed lines and capped by --max-mutants.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_GLOB = re.compile(r"^services/(?P<service>[^/]+)/src/.+\.py$")

COMPARE_SWAPS: dict[type[ast.cmpop], type[ast.cmpop]] = {
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
}
BINOP_SWAPS: dict[type[ast.operator], type[ast.operator]] = {
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.Div,
    ast.Div: ast.Mult,
}
SYMBOL = {
    ast.Gt: ">", ast.GtE: ">=", ast.Lt: "<", ast.LtE: "<=", ast.Eq: "==", ast.NotEq: "!=",
    ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
}  # fmt: skip
HINTS = {
    "compare": "add a test at the boundary value",
    "arithmetic": "assert the exact computed amount",
    "constant": "assert the value this constant controls",
    "boolean": "cover the case where only one of the conditions holds",
    "key": "assert behaviour that depends on this key (e.g. a response field)",
}


@dataclass(frozen=True)
class Mutant:
    path: str
    line: int
    node_index: int
    kind: str
    detail: str  # e.g. "`>` → `>=`"
    arg: int = 0  # which operator in a chained comparison


@dataclass
class Result:
    mutant: Mutant
    killed: bool
    seconds: float


# ---------------------------------------------------------------- discovery


def changed_lines_from_diff(diff: str) -> dict[str, set[int]]:
    """Parse `git diff -U0` output into {path: {added/modified line numbers}}."""
    changed: dict[str, set[int]] = {}
    path: str | None = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            path = target[2:] if target.startswith("b/") else None
        elif line.startswith("@@") and path:
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if match:
                start, count = int(match[1]), int(match[2] or 1)
                changed.setdefault(path, set()).update(range(start, start + count))
    return {p: lines for p, lines in changed.items() if SOURCE_GLOB.match(p) and lines}


def _is_docstring(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    parent = parents.get(node)
    return isinstance(parent, ast.Expr) and isinstance(node, ast.Constant)


def _decimal_literal(node: ast.AST) -> str | None:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Decimal"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        try:
            Decimal(node.args[0].value)
        except InvalidOperation:
            return None
        return node.args[0].value
    return None


def find_mutants(path: str, source: str, lines: set[int]) -> list[Mutant]:
    tree = ast.parse(source)
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    mutants: list[Mutant] = []
    for index, node in enumerate(ast.walk(tree)):
        if isinstance(node, ast.Dict):  # keys may sit on changed lines of a multi-line dict
            for i, key in enumerate(node.keys):
                if (
                    isinstance(key, ast.Constant)
                    and isinstance(key.value, str)
                    and key.lineno in lines
                ):
                    detail = f'key `"{key.value}"` renamed'
                    mutants.append(Mutant(path, key.lineno, index, "key", detail, i))
            continue
        line = getattr(node, "lineno", None)
        if line not in lines:
            continue

        def add(kind: str, detail: str, arg: int = 0, *, _i: int = index, _l: int = line) -> None:
            mutants.append(Mutant(path, _l, _i, kind, detail, arg))

        if isinstance(node, ast.Compare):
            for i, op in enumerate(node.ops):
                swap = COMPARE_SWAPS.get(type(op))
                if swap:
                    add("compare", f"`{SYMBOL[type(op)]}` → `{SYMBOL[swap]}`", i)
        elif isinstance(node, ast.BinOp) and type(node.op) in BINOP_SWAPS:
            swap = BINOP_SWAPS[type(node.op)]
            add("arithmetic", f"`{SYMBOL[type(node.op)]}` → `{SYMBOL[swap]}`")
        elif isinstance(node, ast.BoolOp):
            new = "or" if isinstance(node.op, ast.And) else "and"
            old = "and" if new == "or" else "or"
            add("boolean", f"`{old}` → `{new}`")
        elif (literal := _decimal_literal(node)) is not None:
            add("constant", f'`Decimal("{literal}")` → `Decimal("{Decimal(literal) + 1}")`')
        elif (
            isinstance(node, ast.Constant)
            and type(node.value) in (int, float)
            and not _is_docstring(node, parents)
            and not isinstance(parents.get(node), ast.keyword)  # timeouts, retries, ...
        ):
            add("constant", f"`{node.value!r}` → `{node.value + 1!r}`")
    return mutants


def apply_mutant(source: str, mutant: Mutant) -> str:
    tree = ast.parse(source)
    node = list(ast.walk(tree))[mutant.node_index]
    if mutant.kind == "compare":
        assert isinstance(node, ast.Compare)
        node.ops[mutant.arg] = COMPARE_SWAPS[type(node.ops[mutant.arg])]()
    elif mutant.kind == "arithmetic":
        assert isinstance(node, ast.BinOp)
        node.op = BINOP_SWAPS[type(node.op)]()
    elif mutant.kind == "boolean":
        assert isinstance(node, ast.BoolOp)
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
    elif mutant.kind == "constant" and isinstance(node, ast.Call):
        arg = node.args[0]
        assert isinstance(arg, ast.Constant)
        arg.value = str(Decimal(arg.value) + 1)
    elif mutant.kind == "constant":
        assert isinstance(node, ast.Constant)
        node.value = node.value + 1
    elif mutant.kind == "key":
        assert isinstance(node, ast.Dict)
        key = node.keys[mutant.arg]
        assert isinstance(key, ast.Constant)
        key.value = f"{key.value}__mutant"
    return ast.unparse(tree) + "\n"


# ---------------------------------------------------------------- execution


def service_of(path: str) -> str:
    match = SOURCE_GLOB.match(path)
    assert match, path
    return match["service"]


def run_tests(service: str, timeout: float) -> bool:
    """True if the service's unit + integration tests pass."""
    with tempfile.TemporaryDirectory() as cache:
        env = {**os.environ, "PYTHONPYCACHEPREFIX": cache, "PYTHONDONTWRITEBYTECODE": "1"}
        cmd = [
            sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider",
            f"services/{service}/tests/unit", f"services/{service}/tests/integration",
        ]  # fmt: skip
        try:
            proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return False  # an infinite loop counts as caught
    return proc.returncode == 0


def run(mutants: list[Mutant], timeout: float) -> list[Result]:
    results: list[Result] = []
    for path in sorted({m.path for m in mutants}):
        file = ROOT / path
        original = file.read_text(encoding="utf-8")
        service = service_of(path)
        if not run_tests(service, timeout):
            raise SystemExit(f"{service} tests fail without any mutation; fix them first")
        try:
            for mutant in (m for m in mutants if m.path == path):
                file.write_text(apply_mutant(original, mutant), encoding="utf-8")
                started = time.monotonic()
                killed = not run_tests(service, timeout)
                results.append(Result(mutant, killed, time.monotonic() - started))
                print(
                    f"{'killed  ' if killed else 'SURVIVED'} {path}:{mutant.line} {mutant.detail}"
                )
        finally:
            file.write_text(original, encoding="utf-8")
    return results


# ---------------------------------------------------------------- reporting


def report_markdown(results: list[Result], sources: dict[str, str]) -> str:
    if not results:
        return "## Mutation testing\n\nNo mutable code on the changed lines.\n"
    killed = sum(r.killed for r in results)
    score = 100 * killed / len(results)
    lines = [
        "## Mutation testing (changed lines only)",
        "",
        f"**{killed}/{len(results)} mutants killed ({score:.0f}%)**",
        "",
        "| | Location | Code | Mutation |",
        "|---|---|---|---|",
    ]
    for r in results:
        m = r.mutant
        code = sources[m.path].splitlines()[m.line - 1].strip().replace("|", "\\|")
        lines.append(
            f"| {'✅' if r.killed else '❌'} | `{m.path}:{m.line}` | `{code}` | {m.detail} |"
        )
    survivors = [r.mutant for r in results if not r.killed]
    if survivors:
        lines += ["", "**Survivors — no test fails if this line is wrong:**"]
        for m in survivors:
            name = Path(m.path).name
            lines.append(f"- `{name}:{m.line}` {m.detail}: {HINTS[m.kind]}")
    return "\n".join(lines) + "\n"


def git_diff_u0(base: str) -> str:
    return subprocess.run(
        ["git", "diff", "-U0", f"{base}...HEAD", "--", "services"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout


def parse_lines_arg(values: list[str]) -> dict[str, set[int]]:
    changed: dict[str, set[int]] = {}
    for value in values:
        path, _, spec = value.rpartition(":")
        changed.setdefault(path, set()).update(int(n) for n in spec.split(","))
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--base", help="git ref; mutate lines changed since its merge base")
    source.add_argument("--lines", nargs="+", metavar="PATH:N[,N]", help="explicit lines")
    parser.add_argument("--max-mutants", type=int, default=40)
    parser.add_argument("--timeout", type=float, default=60.0, help="seconds per test run")
    parser.add_argument("--summary", type=Path, help="append the markdown report here")
    args = parser.parse_args(argv)

    changed = (
        parse_lines_arg(args.lines)
        if args.lines
        else changed_lines_from_diff(git_diff_u0(args.base))
    )
    sources = {p: (ROOT / p).read_text(encoding="utf-8") for p in changed}
    mutants = [
        m for p, lines in sorted(changed.items()) for m in find_mutants(p, sources[p], lines)
    ]
    if len(mutants) > args.max_mutants:
        print(f"{len(mutants)} mutants, capped at {args.max_mutants}")
        mutants = mutants[: args.max_mutants]

    results = run(mutants, args.timeout)
    report = report_markdown(results, sources)
    print("\n" + report)
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as out:
            out.write(report)
    return 1 if any(not r.killed for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
