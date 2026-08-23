import random

import pytest

from app import difficulty
from app.difficulty import ADDITION, SUBTRACTION, base_vector


def test_increment_walks_bands_then_flags_then_digits():
    vector = base_vector(2)
    assert vector["magnitude"] == "low_double"

    vector = difficulty.increment(vector, ADDITION)
    assert vector["magnitude"] == "mid_double"
    vector = difficulty.increment(vector, ADDITION)
    assert vector["magnitude"] == "high_double"

    vector = difficulty.increment(vector, ADDITION)
    assert vector["carries"] is True

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
    assert moved["zero_in_minuend"] is True


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
