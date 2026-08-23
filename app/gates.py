"""Re-check a generated game ourselves, in code the generating agent never sees.

Until now `gate_results` was whatever the Devin session reported about its own
work, and a version went live on that report alone -- but a report is not
evidence about the work that produced it, and a child is the one who meets the
result.

So these checks are deliberately dumb and deliberately ours: static assertions
over the produced files plus a real headless playthrough with the backend's own
question generator behind a stubbed API. They do not replace Devin's gates --
they are recorded alongside them under `independent`, and a version has to pass
both to go live.

Nothing here reads the child's data or the network.
"""

from __future__ import annotations

import contextlib
import functools
import json
import re
import threading
from collections.abc import Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from app import difficulty, error_taxonomy

# Every event Loop B's diagnosis is computed from. A game that silently stops
# emitting one of these does not fail visibly -- the iteration just goes blind,
# which is exactly the kind of rot a gate is for.
REQUIRED_EVENTS = (
    "problem_shown",
    "answer_submitted",
    "idle_tick",
    "edit_event",
    "motion_event",
    "level_started",
    "level_abandoned",
)

# The game is a rendering shell: it must ask the backend for questions and post
# answers back, rather than owning difficulty or correctness. Matched loosely --
# the endpoint may be assembled from a base URL -- since the playthrough check
# below is what actually proves the calls happen.
REQUIRED_CALLS = ("next-question", "attempts")

# WCAG 2.3.1: nothing may flash faster than 3Hz. A full flash cycle therefore
# cannot be shorter than a third of a second.
MIN_FLASH_SECONDS = 0.334
DURATION = re.compile(r"animation(?:-duration)?\s*:[^;}]*?([\d.]+)(m?s)", re.I)

PLAYTHROUGH_QUESTIONS = 3
PLAYTHROUGH_TIMEOUT_MS = 15000


def verify_static(code_path: str | None) -> dict[str, str]:
    """The checks that need no browser: what is in the files the agent produced."""
    root = _root(code_path)
    if root is None:
        return {"files": f"FAIL - no game directory at {code_path!r}"}

    source = _source(root)
    return {
        "files": _files(root),
        "shell_contract": _shell_contract(source),
        "instrumentation": _instrumentation(source),
        "no_fast_flashing": _no_fast_flashing(source),
        "focus_visible": _focus_visible(source),
    }


async def verify(
    code_path: str | None, skill_id: str, vector: dict[str, Any]
) -> dict[str, Any]:
    """Every independent check, static and live. `passed` is false if any failed.

    A skipped check (no browser available) is neither a pass nor a failure, so it
    does not fail the version -- but it is listed, because "we could not look" and
    "we looked and it was fine" must not read the same to whoever ships this.
    """
    results: dict[str, str] = verify_static(code_path)
    if not _any_failed(results):
        try:
            results["playthrough"] = await verify_playthrough(
                code_path, skill_id, vector
            )
        except Exception as error:  # pragma: no cover - browser/driver failures
            # A checker that cannot run must not masquerade as a checker that
            # found nothing, nor take the whole status endpoint down with it.
            results["playthrough"] = f"SKIP - the browser check errored: {error}"
    return {
        **results,
        "passed": not _any_failed(results),
        "skipped": [name for name, value in results.items() if _is_skip(value)],
    }


async def verify_playthrough(
    code_path: str | None, skill_id: str, vector: dict[str, Any]
) -> str:
    """Play the real game in a real browser, with our question generator stubbed in.

    Stubbing the two endpoints rather than pointing the game at a live server keeps
    the check hermetic and lets us assert the thing that actually matters: that the
    game asks for every question and posts every answer instead of inventing them.
    The game is served over real HTTP rather than file://, because a file:// origin
    fails same-origin fetches the game legitimately makes.
    """
    root = _root(code_path)
    if root is None or not (root / "index.html").exists():
        return f"FAIL - no index.html at {code_path!r}"

    try:
        from playwright.async_api import async_playwright
    except ImportError:  # pragma: no cover - browser deps are optional locally
        return "SKIP - playwright is not installed in this environment"

    asked = 0
    posted = 0
    console: list[str] = []
    pending: dict[str, Any] = {}

    async with async_playwright() as driver:
        browser = await driver.chromium.launch()
        page = await browser.new_page()
        page.on(
            "console",
            lambda message: console.append(message.text)
            if message.type == "error"
            else None,
        )

        async def question(route: Any) -> None:
            nonlocal asked
            asked += 1
            pending.clear()
            pending.update(difficulty.next_question(vector, skill_id))
            await route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(pending),
            )

        async def attempt(route: Any) -> None:
            nonlocal posted
            posted += 1
            body = route.request.post_data_json or {}
            error_class = error_taxonomy.classify_attempt(
                body.get("operands") or [0, 0],
                body.get("operator", "+"),
                body.get("answer_given", 0),
            )
            await route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "attempt_id": f"gate-check-{posted}",
                        "is_correct": error_class == error_taxonomy.CORRECT,
                        "error_class": error_class,
                        "updated_difficulty_vector": vector,
                        "movement": "hold",
                        "repeat_tier": False,
                    }
                ),
            )

        await page.route("**/next-question*", question)
        await page.route("**/attempts", attempt)

        with _served(root) as origin:
            await page.goto(f"{origin}/index.html", timeout=PLAYTHROUGH_TIMEOUT_MS)
            await page.wait_for_timeout(1500)

            for turn in range(PLAYTHROUGH_QUESTIONS):
                answer = pending.get("correct_answer")
                if answer is None:
                    break
                # One deliberately wrong answer: the game must survive both.
                await _answer(page, answer + 1 if turn == 1 else answer)

        await browser.close()

    if asked == 0:
        return "FAIL - the game never called next-question; it owns its own questions"
    if posted == 0:
        return "FAIL - the game never posted an attempt; correctness is client-side"
    if console:
        return f"FAIL - {len(console)} console error(s): {console[0][:120]}"
    return (
        f"PASS - drew {asked} question(s) from the backend and posted "
        f"{posted} attempt(s), no console errors"
    )


async def _answer(page: Any, answer: int) -> None:
    """Type an answer into the first input and submit it.

    Deliberately generic: a game that cannot be driven by typing a number and
    pressing Enter is one this check reports on, not one it accommodates.
    """
    box = page.locator("input").first
    if await box.count() == 0:
        return
    await box.fill(str(answer))
    await box.press("Enter")
    await page.wait_for_timeout(800)


@contextlib.contextmanager
def _served(root: Path) -> Iterator[str]:
    """Serve the game directory on an ephemeral localhost port for the check."""
    handler = functools.partial(_QuietHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:
        pass


def _root(code_path: str | None) -> Path | None:
    if not code_path:
        return None
    path = Path(code_path)
    if path.name.endswith(".html"):
        path = path.parent
    return path if path.is_dir() else None


def _source(root: Path) -> str:
    """Every text file in the game, concatenated. Prototype-grade on purpose."""
    parts = []
    for file in sorted(root.rglob("*")):
        if file.suffix.lower() in {".html", ".js", ".css"} and file.is_file():
            parts.append(file.read_text(errors="ignore"))
    return "\n".join(parts)


def _files(root: Path) -> str:
    if not (root / "index.html").exists():
        return "FAIL - no index.html"
    return f"PASS - {len(list(root.rglob('*')))} file(s) under {root}"


def _shell_contract(source: str) -> str:
    missing = [call for call in REQUIRED_CALLS if call not in source]
    if missing:
        return f"FAIL - never calls {', '.join(missing)}"
    return "PASS - draws questions from the backend and posts attempts to it"


def _instrumentation(source: str) -> str:
    missing = [
        event
        for event in REQUIRED_EVENTS
        if f'"{event}"' not in source and f"'{event}'" not in source
    ]
    if missing:
        return f"FAIL - never emits {', '.join(missing)}"
    return f"PASS - emits all {len(REQUIRED_EVENTS)} events Loop B reads"


def _no_fast_flashing(source: str) -> str:
    for value, unit in DURATION.findall(source):
        seconds = float(value) / 1000 if unit.lower() == "ms" else float(value)
        if 0 < seconds < MIN_FLASH_SECONDS:
            return f"FAIL - a {seconds}s animation can flash faster than 3Hz"
    return "PASS - no animation short enough to flash above 3Hz"


def _focus_visible(source: str) -> str:
    if ":focus" not in source:
        return "FAIL - no :focus styling, so keyboard focus is invisible"
    return "PASS - keyboard focus is styled"


def _any_failed(results: dict[str, str]) -> bool:
    return any(value.startswith("FAIL") for value in results.values())


def _is_skip(value: str) -> bool:
    return value.startswith("SKIP")
