"""The server runs Python 3.11 (see .cpanel.yml), while development may use a newer one.

Python 3.12 lets an f-string reuse its own quote inside {…} (PEP 701); 3.11 can't even
import such a file, which takes the whole API down. This catches it before deploying.
"""

import tokenize
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"


def _quote(token: str) -> str:
    return token.lstrip("rRbBuUfF")[:1]


def _problems(path: Path) -> list[str]:
    if not hasattr(tokenize, "FSTRING_START"):
        return []  # running on 3.11 itself: importing the app already proves it
    found, enclosing = [], []
    with path.open("rb") as fh:
        for tok in tokenize.tokenize(fh.readline):
            if tok.type == tokenize.FSTRING_START:
                if _quote(tok.string) in enclosing:
                    found.append(f"{path.name}:{tok.start[0]}")
                enclosing.append(_quote(tok.string))
            elif tok.type == tokenize.FSTRING_END:
                enclosing.pop()
            elif enclosing and tok.type == tokenize.STRING and (_quote(tok.string) in enclosing or "\\" in tok.string):
                found.append(f"{path.name}:{tok.start[0]}")
    return found


@pytest.mark.parametrize("path", sorted(APP.rglob("*.py")), ids=lambda p: str(p.relative_to(APP)))
def test_f_strings_work_on_python_311(path):
    assert _problems(path) == [], "f-string reuses its quote (or a backslash) inside {…}: fails on the server's Python 3.11"
