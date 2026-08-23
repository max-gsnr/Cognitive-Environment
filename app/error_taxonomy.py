"""Classify a wrong answer into the mistake that produced it.

`classify_attempt` is pure and never calls a model. It is the one part of the
system Devin is not allowed to touch, so the meaning of an error class cannot
drift between game versions.
"""

from __future__ import annotations

CORRECT = "correct"
BORROW_OMITTED = "borrow_omitted"
BORROW_ACROSS_ZERO = "borrow_across_zero"
CARRY_OMITTED = "carry_omitted"
PLACE_VALUE_MISALIGNMENT = "place_value_misalignment"
OPERATOR_CONFUSION = "operator_confusion"
COUNTING_SLIP = "counting_slip"
UNCLASSIFIED = "unclassified"

# Which axis of the difficulty vector a class implicates. None means the caller
# decides (counting_slip splits by latency; operator_confusion never decrements).
AXIS_FOR_CLASS: dict[str, str | None] = {
    BORROW_OMITTED: "borrows",
    BORROW_ACROSS_ZERO: "zero_in_minuend",
    CARRY_OMITTED: "carries",
    PLACE_VALUE_MISALIGNMENT: "digits",
    OPERATOR_CONFUSION: None,
    COUNTING_SLIP: None,
    UNCLASSIFIED: None,
}


def _digits(value: int, width: int) -> list[int]:
    padded = str(value).rjust(width, "0")
    return [int(char) for char in padded]


def _from_digits(digits: list[int]) -> int:
    return int("".join(str(digit) for digit in digits) or "0")


def _digitwise_absolute_difference(a: int, b: int) -> int:
    width = max(len(str(a)), len(str(b)))
    return _from_digits(
        [abs(x - y) for x, y in zip(_digits(a, width), _digits(b, width), strict=True)]
    )


def _digitwise_sum_mod_ten(a: int, b: int) -> int:
    width = max(len(str(a)), len(str(b)))
    return _from_digits(
        [
            (x + y) % 10
            for x, y in zip(_digits(a, width), _digits(b, width), strict=True)
        ]
    )


def _zero_sits_in_a_borrow_column(a: int, b: int) -> bool:
    width = max(len(str(a)), len(str(b)))
    top, bottom = _digits(a, width), _digits(b, width)
    return any(x == 0 and y > 0 for x, y in zip(top, bottom, strict=True))


def _misaligned_results(a: int, b: int, operator: str) -> set[int]:
    """Results of applying the smaller operand in the wrong column (234 + 5 = 284)."""
    if len(str(a)) == len(str(b)):
        return set()
    smaller, larger = (b, a) if len(str(b)) < len(str(a)) else (a, b)
    shifts = len(str(larger)) - len(str(smaller))
    results = set()
    for shift in range(1, shifts + 1):
        moved = smaller * (10**shift)
        results.add(larger + moved if operator == "+" else larger - moved)
    return results


def classify_attempt(
    operands: list[int], operator: str, answer_given: int
) -> str:
    """Return the error class for one answer. No latency, no state, no model."""
    a, b = operands[0], operands[1]
    correct_answer = a + b if operator == "+" else a - b

    if answer_given == correct_answer:
        return CORRECT

    if operator == "-":
        if answer_given == _digitwise_absolute_difference(a, b):
            if _zero_sits_in_a_borrow_column(a, b):
                return BORROW_ACROSS_ZERO
            return BORROW_OMITTED
    elif answer_given == _digitwise_sum_mod_ten(a, b):
        return CARRY_OMITTED

    if answer_given in _misaligned_results(a, b, operator):
        return PLACE_VALUE_MISALIGNMENT

    inverse = a - b if operator == "+" else a + b
    if answer_given == inverse:
        return OPERATOR_CONFUSION

    if abs(answer_given - correct_answer) == 1:
        return COUNTING_SLIP

    return UNCLASSIFIED
