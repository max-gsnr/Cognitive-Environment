from app import ability, difficulty
from app.difficulty import ADDITION, SUBTRACTION, base_vector

FLOOR = difficulty.floor_vector("single_digit")


def test_the_rating_scale_agrees_with_the_ladder_about_what_is_harder():
    for skill_id, tiers in ability.LADDER.items():
        ratings = [ability.tier_rating(vector, skill_id) for vector in tiers]
        ranks = [difficulty.rank(vector, skill_id) for vector in tiers]
        assert ratings == sorted(ratings)
        assert ranks == sorted(ranks)


def test_every_rated_tier_can_actually_be_asked():
    for skill_id, tiers in ability.LADDER.items():
        for vector in tiers:
            assert difficulty.satisfiable(vector, skill_id)


def test_a_new_child_is_aimed_at_their_own_floor():
    rating = ability.starting_rating(FLOOR, ADDITION, "medium")
    assert ability.expected_success(rating, FLOOR, ADDITION) == 0.8
    chosen = ability.choose_tier(rating, ADDITION, FLOOR, FLOOR)
    assert difficulty.tier_key(chosen) == difficulty.tier_key(FLOOR)


def test_leniency_sets_how_much_success_the_child_gets():
    for band, target in ability.TARGET_SUCCESS.items():
        rating = ability.starting_rating(FLOOR, ADDITION, band)
        assert round(ability.expected_success(rating, FLOOR, ADDITION), 6) == target


def test_questions_are_aimed_at_the_target_success_rate():
    for skill_id in (ADDITION, SUBTRACTION):
        for rating in range(0, 1200, 50):
            chosen = ability.choose_tier(
                float(rating), skill_id, FLOOR, FLOOR, attempts_seen=1
            )
            expected = ability.expected_success(float(rating), chosen, skill_id)
            if difficulty.tier_key(chosen) == difficulty.tier_key(FLOOR):
                continue  # a child rated below their own floor cannot be aimed
            # Within half a rung of target, which the ladder's granularity allows.
            assert 0.66 <= expected <= 0.93


def test_one_answer_cannot_move_the_tier_but_a_run_of_them_can():
    rating = ability.starting_rating(FLOOR, ADDITION, "medium")
    vector = dict(FLOOR)
    for _ in range(1):
        rating = ability.update_rating(rating, vector, ADDITION, True, 0)
    assert difficulty.tier_key(
        ability.choose_tier(rating, ADDITION, FLOOR, vector, attempts_seen=1)
    ) == difficulty.tier_key(FLOOR)

    for seen in range(1, 8):
        rating = ability.update_rating(rating, vector, ADDITION, True, seen)
    moved = ability.choose_tier(rating, ADDITION, FLOOR, vector, attempts_seen=8)
    assert difficulty.rank(moved, ADDITION) > difficulty.rank(FLOOR, ADDITION)


def test_the_estimate_settles_as_evidence_accumulates():
    assert ability.k_factor(0) > ability.k_factor(10) > ability.k_factor(100)
    assert ability.k_factor(10_000) >= ability.K_FLOOR


def test_a_run_of_errors_is_answered_with_a_deliberately_easy_question():
    vector = {**base_vector(2), "magnitude": "high_double", "carries": True}
    rating = ability.tier_rating(vector, ADDITION) + ability.target_offset("medium")
    steady = ability.choose_tier(rating, ADDITION, FLOOR, vector)
    rested = ability.choose_tier(
        rating, ADDITION, FLOOR, vector, errors_in_a_row=ability.REST_AFTER_ERRORS
    )
    assert difficulty.rank(rested, ADDITION) < difficulty.rank(steady, ADDITION)


def test_a_fluency_question_arrives_on_schedule_and_is_easier():
    vector = {**base_vector(2), "magnitude": "mid_double", "carries": True}
    rating = ability.tier_rating(vector, ADDITION) + ability.target_offset("medium")
    steady = ability.choose_tier(rating, ADDITION, FLOOR, vector, attempts_seen=4)
    fluency = ability.choose_tier(
        rating, ADDITION, FLOOR, vector, attempts_seen=ability.FLUENCY_EVERY
    )
    assert difficulty.rank(fluency, ADDITION) < difficulty.rank(steady, ADDITION)


def test_the_tier_never_falls_below_the_floor():
    floor = difficulty.floor_vector("double_digit")
    chosen = ability.choose_tier(
        -5000.0, ADDITION, floor, floor, errors_in_a_row=5, attempts_seen=5
    )
    assert difficulty.rank(chosen, ADDITION) >= difficulty.rank(floor, ADDITION)


def test_an_unaskable_tier_is_still_rated():
    """Vectors from an older session may not be on the ladder; nothing may crash."""
    unaskable = {**base_vector(2), "magnitude": "high_double", "carries": False}
    assert not difficulty.satisfiable(unaskable, ADDITION)
    assert ability.tier_rating(unaskable, ADDITION) > 0
