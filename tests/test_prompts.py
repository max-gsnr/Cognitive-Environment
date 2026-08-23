import re

from app import prompts


def test_devin_prompts_have_no_unresolved_placeholders():
    """Rendered Devin prompts must not leave placeholder tokens behind."""
    cases = (
        (
            prompts.GENERATE_GAME_PROMPT,
            {
                "profile_json": "{}",
                "skill_label": "Addition",
                "skill_id": "addition",
                "initial_difficulty_vector_json": "{}",
                "profile_id": "profile-1",
                "top_interest": "space",
                "game_id": "game-1",
                "version": 2,
                "posthog_project_key": "project-key",
                "posthog_host": "https://posthog.example",
                "session_length": 10,
            },
        ),
        (
            prompts.ITERATE_PROMPT,
            {
                "profile_json": "{}",
                "code_path": "games/profile-1/addition/v1/index.html",
                "current_version": 1,
                "skill_label": "Addition",
                "skill_id": "addition",
                "current_difficulty_vector_json": "{}",
                "n": 0,
                "error_class_breakdown_json": "{}",
                "development_notes_text": "None",
                "reported_problems_text": "None",
                "posthog_project_id": "project-id",
                "posthog_host": "https://posthog.example",
                "game_id": "game-1",
                "profile_id": "profile-1",
                "since_timestamp": "2026-01-01T00:00:00+00:00",
                "new_version": 2,
                "telemetry_signals_json": "{}",
            },
        ),
    )

    for template, values in cases:
        rendered = prompts.render(template, **values)
        leftover = re.search(r"\{(\w+)\}", rendered)
        assert leftover is None, (
            f"unresolved placeholder: {leftover.group(0) if leftover else ''}"
        )
