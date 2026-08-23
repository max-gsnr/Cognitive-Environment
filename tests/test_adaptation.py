from datetime import UTC, datetime, timedelta

from app import adaptation, difficulty, error_taxonomy
from app.baseline import LatencySample, compute_baseline
from app.difficulty import ADDITION, SUBTRACTION, base_vector

NOW = datetime(2026, 8, 23, tzinfo=UTC)


def samples(count, latency_ms, age_days=0):
    return [
        LatencySample(latency_ms, NOW - timedelta(days=age_days, minutes=index))
        for index in range(count)
    ]


def test_baseline_needs_five_samples():
    assert compute_baseline(samples(4, 3000), now=NOW) is None
    assert compute_baseline(samples(5, 3000), now=NOW) == 3000


def test_baseline_ignores_attempts_older_than_three_days():
    assert compute_baseline(samples(6, 3000, age_days=4), now=NOW) is None


def test_correct_and_at_pace_increments():
    movement = adaptation.decide_movement(error_taxonomy.CORRECT, 2000, 3000)
    assert movement.direction == adaptation.INCREMENT


def test_correct_but_slow_decrements():
    movement = adaptation.decide_movement(error_taxonomy.CORRECT, 5000, 3000)
    assert movement.direction == adaptation.DECREMENT


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


def test_high_leniency_needs_three_rough_attempts_to_move_once():
    vector = {**base_vector(2), "magnitude": "mid_double"}
    floor = difficulty.floor_vector("single_digit")
    movement = adaptation.Movement(
        adaptation.DECREMENT, "magnitude", error_taxonomy.COUNTING_SLIP
    )

    credit = 0.0
    current = vector
    for _ in range(2):
        current, credit = adaptation.apply(
            current, ADDITION, movement, floor, "high", credit
        )
    assert current["magnitude"] == "mid_double"

    current, credit = adaptation.apply(
        current, ADDITION, movement, floor, "high", credit
    )
    assert current["magnitude"] == "low_double"


def test_low_leniency_moves_on_the_first_bad_attempt():
    vector = {**base_vector(2), "magnitude": "mid_double"}
    floor = difficulty.floor_vector("single_digit")
    movement = adaptation.Movement(
        adaptation.DECREMENT, "magnitude", error_taxonomy.COUNTING_SLIP
    )
    moved, _ = adaptation.apply(vector, ADDITION, movement, floor, "low", 0.0)
    assert moved["magnitude"] == "low_double"


def test_borrow_error_targets_the_borrow_axis():
    vector = {**base_vector(2), "magnitude": "high_double", "borrows": True}
    floor = difficulty.floor_vector("single_digit")
    updated, movement, _ = adaptation.next_vector(
        vector=vector,
        skill_id=SUBTRACTION,
        operands=[52, 27],
        operator="-",
        answer_given=35,
        latency_ms=4000,
        baseline=4000,
        floor=floor,
        leniency_band="low",
        decrement_credit=0.0,
    )
    assert movement.error_class == error_taxonomy.BORROW_OMITTED
    assert updated["borrows"] is False
