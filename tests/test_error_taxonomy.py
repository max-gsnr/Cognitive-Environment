from app.error_taxonomy import (
    BORROW_ACROSS_ZERO,
    BORROW_OMITTED,
    CARRY_OMITTED,
    CORRECT,
    COUNTING_SLIP,
    OPERATOR_CONFUSION,
    PLACE_VALUE_MISALIGNMENT,
    UNCLASSIFIED,
    classify_attempt,
)


def test_correct():
    assert classify_attempt([12, 7], "+", 19) == CORRECT


def test_carry_omitted():
    # 27 + 15: digitwise (2+1)(7+5 mod 10) = 32, the classic dropped carry.
    assert classify_attempt([27, 15], "+", 32) == CARRY_OMITTED


def test_borrow_omitted():
    # 52 - 27: digitwise |5-2||2-7| = 35.
    assert classify_attempt([52, 27], "-", 35) == BORROW_OMITTED


def test_borrow_across_zero_beats_borrow_omitted():
    # 302 - 178 with a zero sitting in a borrow column.
    assert classify_attempt([302, 178], "-", 276) == BORROW_ACROSS_ZERO


def test_place_value_misalignment():
    assert classify_attempt([234, 5], "+", 284) == PLACE_VALUE_MISALIGNMENT


def test_operator_confusion():
    assert classify_attempt([14, 6], "+", 8) == OPERATOR_CONFUSION
    assert classify_attempt([14, 6], "-", 20) == OPERATOR_CONFUSION


def test_counting_slip():
    assert classify_attempt([14, 6], "+", 21) == COUNTING_SLIP
    assert classify_attempt([14, 6], "+", 19) == COUNTING_SLIP


def test_unclassified():
    assert classify_attempt([14, 6], "+", 77) == UNCLASSIFIED


def test_classification_is_pure():
    args = ([52, 27], "-", 35)
    assert classify_attempt(*args) == classify_attempt(*args)
