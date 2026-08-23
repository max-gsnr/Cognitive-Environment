from datetime import UTC, datetime, timedelta

from app import adaptation, difficulty, error_taxonomy
from app.baseline import LatencySample, compute_baseline
from app.difficulty import ADDITION, SUBTRACTION, base_vector

NOW = datetime(2026, 8, 23, tzinfo=UTC)
FLOOR = difficulty.floor_vector("single_digit")


def samples(count, latency_ms, age_days=0):
    return [
        LatencySample(latency_ms, NOW - timedelta(days=age_days, minutes=index))
        for index in range(count)
    ]


def answer(vector, skill_id, correct, latency_ms=2000):
    """The operands and the given answer for a right or wrong attempt at a tier."""
    question = difficulty.next_question(vector, skill_id)
    given = question["correct_answer"] if correct else question["correct_answer"] + 1
    return {
        "operands": question["operands"],
        "operator": question["operator"],
        "answer_given": given,
        "latency_ms": latency_ms,
    }


def play(results, skill_id=ADDITION, leniency_band="medium", floor=FLOOR):
    """Answer a session's worth of questions, returning every decision made."""
    vector = dict(floor)
    rating = None
    decisions = []
    for index, correct in enumerate(results):
        decision = adaptation.next_vector(
            vector=vector,
            skill_id=skill_id,
            floor=floor,
            baseline=None,
            leniency_band=leniency_band,
            rating=(
                adaptation.replay([], floor, skill_id, leniency_band)[0]
                if rating is None
                else rating
            ),
            attempts_seen=index,
            prior_errors_in_a_row=decisions[-1].errors_in_a_row if decisions else 0,
            **answer(vector, skill_id, correct),
        )
        vector, rating = decision.vector, decision.rating
        decisions.append(decision)
    return decisions


def test_baseline_needs_five_samples():
    assert compute_baseline(samples(4, 3000), now=NOW) is None
    assert compute_baseline(samples(5, 3000), now=NOW) == 3000


def test_baseline_ignores_attempts_older_than_three_days():
    assert compute_baseline(samples(6, 3000, age_days=4), now=NOW) is None


def test_correct_and_at_pace_asks_for_harder_work():
    movement = adaptation.decide_movement(error_taxonomy.CORRECT, 2000, 3000)
    assert movement.direction == adaptation.INCREMENT


def test_correct_but_slow_holds_rather_than_punishing_the_child():
    movement = adaptation.decide_movement(error_taxonomy.CORRECT, 5000, 3000)
    assert movement.direction == adaptation.HOLD


def test_no_baseline_means_correctness_alone_moves_the_vector():
    movement = adaptation.decide_movement(error_taxonomy.CORRECT, 99999, None)
    assert movement.direction == adaptation.INCREMENT


def test_fast_counting_slip_holds_and_repeats():
    movement = adaptation.decide_movement(error_taxonomy.COUNTING_SLIP, 1000, 3000)
    assert movement.direction == adaptation.HOLD
    assert movement.repeat_tier is True


def test_slow_counting_slip_softens_magnitude_only():
    movement = adaptation.decide_movement(error_taxonomy.COUNTING_SLIP, 9000, 3000)
    assert movement.direction == adaptation.DECREMENT
    assert movement.axis == "magnitude"


def test_operator_confusion_does_not_move_the_ladder():
    movement = adaptation.decide_movement(error_taxonomy.OPERATOR_CONFUSION, 3000, 3000)
    assert movement.direction == adaptation.HOLD


def test_unclassified_is_left_for_loop_b():
    movement = adaptation.decide_movement(error_taxonomy.UNCLASSIFIED, 3000, 3000)
    assert movement.direction == adaptation.HOLD


def test_one_correct_answer_does_not_move_the_tier():
    """The regression this policy exists for: a single success is not evidence."""
    decision = play([True])[-1]
    assert decision.movement.direction == adaptation.HOLD
    assert difficulty.tier_key(decision.vector) == difficulty.tier_key(FLOOR)


def test_a_perfect_ten_question_session_stays_near_the_child():
    """It used to reach the ceiling --- 3+4 to 738+195 --- in nine answers."""
    decisions = play([True] * 10)
    rungs = difficulty.rank(decisions[-1].vector, ADDITION)[0]
    assert rungs <= 2  # still one- or two-digit work
    assert all(d.vector["digits"] <= 2 for d in decisions)


def test_the_session_does_move_for_a_child_who_is_ready():
    ranks = [difficulty.rank(d.vector, ADDITION) for d in play([True] * 10)]
    assert ranks[-1] > difficulty.rank(FLOOR, ADDITION)


def test_two_errors_in_a_row_buy_an_easier_question():
    vector = {**base_vector(2), "magnitude": "high_double", "carries": True}
    decision = adaptation.next_vector(
        vector=vector,
        skill_id=ADDITION,
        floor=FLOOR,
        baseline=None,
        leniency_band="medium",
        rating=1000.0,
        attempts_seen=6,
        prior_errors_in_a_row=1,
        **answer(vector, ADDITION, correct=False),
    )
    assert decision.errors_in_a_row == 2
    assert difficulty.rank(decision.vector, ADDITION) < difficulty.rank(
        vector, ADDITION
    )


def test_a_wrong_answer_never_drops_below_the_profile_floor():
    floor = difficulty.floor_vector("double_digit")
    decisions = play([False] * 6, floor=floor)
    for decision in decisions:
        assert difficulty.rank(decision.vector, ADDITION) >= difficulty.rank(
            floor, ADDITION
        )


def test_difficulty_stays_calm_across_a_mixed_session():
    results = [True, True, False, True, True, False, True, True, True, False]
    directions = [d.movement.direction for d in play(results)]
    assert sum(1 for d in directions if d != adaptation.HOLD) <= 4


def test_borrow_error_targets_the_borrow_axis():
    vector = {**base_vector(2), "magnitude": "high_double", "borrows": True}
    decision = adaptation.next_vector(
        vector=vector,
        skill_id=SUBTRACTION,
        operands=[52, 27],
        operator="-",
        answer_given=35,
        latency_ms=4000,
        baseline=4000,
        floor=FLOOR,
        leniency_band="low",
        rating=1000.0,
    )
    assert decision.movement.error_class == error_taxonomy.BORROW_OMITTED
    assert decision.vector["borrows"] is False


def test_replay_reproduces_a_live_session_exactly():
    """The rating is a fold over the attempt log, so it survives a restart."""
    results = [True, False, True, True, False, True]
    decisions = play(results)

    history = [
        (
            decisions[index - 1].vector if index else dict(FLOOR),
            decisions[index].movement.error_class,
            results[index],
        )
        for index in range(len(results))
    ]
    replayed, counted = adaptation.replay(history, FLOOR, ADDITION, "medium")
    assert replayed == decisions[-1].rating
    assert counted == len(results)
    assert adaptation.errors_in_a_row(history) == 0


def test_answers_that_say_nothing_about_difficulty_leave_the_rating_alone():
    vector = {**base_vector(2), "magnitude": "mid_double"}
    decision = adaptation.next_vector(
        vector=vector,
        skill_id=ADDITION,
        operands=[41, 12],
        operator="+",
        answer_given=29,  # subtracted instead of adding
        latency_ms=3000,
        baseline=None,
        floor=FLOOR,
        leniency_band="medium",
        rating=500.0,
    )
    assert decision.movement.error_class == error_taxonomy.OPERATOR_CONFUSION
    assert decision.rating == 500.0
    assert difficulty.tier_key(decision.vector) == difficulty.tier_key(vector)
