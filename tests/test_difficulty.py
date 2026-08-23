import random

import pytest

from app import difficulty
from app.difficulty import ADDITION, SUBTRACTION, base_vector


def test_increment_walks_bands_then_flags_then_digits():
    vector = base_vector(2)
    assert vector["magnitude"] == "low_double"

    vector = difficulty.increment(vector, ADDITION)
    assert vector["magnitude"] == "mid_double"

    # 70-99 without a carry describes nothing, so carrying comes first instead.
    vector = difficulty.increment(vector, ADDITION)
    assert (vector["magnitude"], vector["carries"]) == ("mid_double", True)
    vector = difficulty.increment(vector, ADDITION)
    assert (vector["magnitude"], vector["carries"]) == ("high_double", True)

    vector = difficulty.increment(vector, ADDITION)
    assert vector["digits"] == 3
    assert vector["magnitude"] == "low_triple"
    assert vector["carries"] is False


def test_subtraction_enables_borrows_then_zero_in_minuend():
    vector = {**base_vector(2), "magnitude": "high_double"}
    vector = difficulty.increment(vector, SUBTRACTION)
    assert vector["borrows"] is True
    vector = difficulty.increment(vector, SUBTRACTION)
    assert vector["zero_in_minuend"] is True


def test_increment_stops_at_the_ceiling():
    vector = {
        "digits": 3,
        "magnitude": "high_triple",
        "carries": True,
        "borrows": True,
        "zero_in_minuend": True,
    }
    assert difficulty.increment(vector, SUBTRACTION) == vector


def test_decrement_honours_the_axis_the_error_class_names():
    vector = {**base_vector(3), "borrows": True, "zero_in_minuend": True}
    moved = difficulty.decrement(vector, SUBTRACTION, axis="borrows")
    assert moved["borrows"] is False
    # Dropping borrows has to take the zero with it; borrowing across a zero is
    # still borrowing, so the pair would describe no question at all.
    assert moved["zero_in_minuend"] is False


def test_single_digit_subtraction_skips_borrowing_and_grows_a_digit():
    """a >= b at one digit can never borrow, so that rung does not exist."""
    vector = difficulty.increment(base_vector(1), SUBTRACTION)
    assert vector["digits"] == 2
    assert vector["borrows"] is False


@pytest.mark.parametrize("skill", [ADDITION, SUBTRACTION])
def test_the_whole_ladder_only_asks_answerable_questions(skill):
    """Every rung must generate on its own terms, never the 1-1 fallback."""
    rng = random.Random(11)
    vector = base_vector(1)
    seen = set()
    while difficulty.tier_key(vector) not in seen:
        seen.add(difficulty.tier_key(vector))
        for _ in range(20):
            question = difficulty.next_question(vector, skill, rng)
            a, b = question["operands"]
            if skill == ADDITION:
                assert difficulty._has_carry(a, b) is bool(vector["carries"])
            else:
                assert difficulty._has_borrow(a, b) is bool(vector["borrows"])
                assert difficulty._zero_in_borrow_column(a, b) is bool(
                    vector["zero_in_minuend"]
                )
        vector = difficulty.increment(vector, skill)


def test_decrement_falls_back_to_the_reverse_ladder():
    vector = {**base_vector(2), "magnitude": "mid_double"}
    moved = difficulty.decrement(vector, ADDITION, axis="carries")
    assert moved["magnitude"] == "low_double"


def test_floor_is_never_crossed():
    floor = difficulty.floor_vector("double_digit")
    vector = base_vector(2)
    moved = difficulty.apply_movement(vector, ADDITION, "decrement", floor)
    assert moved["digits"] == 2


@pytest.mark.parametrize("skill", [ADDITION, SUBTRACTION])
@pytest.mark.parametrize("digits", [1, 2, 3])
def test_generated_questions_respect_the_vector(skill, digits):
    rng = random.Random(7)
    vector = base_vector(digits)
    if skill == SUBTRACTION and digits > 1:
        vector["borrows"] = True

    for _ in range(50):
        question = difficulty.next_question(vector, skill, rng)
        a, b = question["operands"]
        assert a >= 0 and b >= 0
        assert len(str(a)) <= 3 and len(str(b)) <= 3
        assert question["correct_answer"] >= 0
        if skill == SUBTRACTION:
            assert a >= b


def test_carry_flag_controls_whether_a_carry_is_present():
    rng = random.Random(3)
    without = {**base_vector(2), "magnitude": "mid_double", "carries": False}
    question = difficulty.next_question(without, ADDITION, rng)
    a, b = question["operands"]
    assert (a % 10) + (b % 10) < 10


def test_single_digit_magnitude_variants_are_safely_supported():
    for mag in ("single", "low_single", "mid_single", "high_single", "unknown_mag"):
        vector = {
            "digits": 1,
            "magnitude": mag,
            "carries": False,
            "borrows": False,
            "zero_in_minuend": False,
        }
        assert difficulty.satisfiable(vector, ADDITION)
        assert difficulty.satisfiable(vector, SUBTRACTION)
        q = difficulty.next_question(vector, ADDITION)
        assert len(q["operands"]) == 2
        q_sub = difficulty.next_question(vector, SUBTRACTION)
        assert q_sub["operands"][0] >= q_sub["operands"][1]
