"""Who can be interested in whom: the one rule shared by suggestions, search and the seed."""


def is_interested(orientation: str | None, gender: str | None, other_gender: str | None) -> bool:
    """Whether someone of this orientation and gender is interested in another gender.

    - ``bi``, or no orientation given (the subject's default), is interested
      in everyone;
    - ``homo`` in the same gender;
    - ``hetero`` in the other binary gender (male <-> female); someone of
      gender ``other`` who says ``hetero`` is interested in men and women.

    Args:
        orientation: ``homo``, ``hetero``, ``bi`` or None.
        gender: Gender of the person whose interest is asked.
        other_gender: Gender of the person they might be interested in.

    Returns:
        True if they are interested.
    """
    if orientation == "homo":
        return gender is not None and other_gender == gender
    if orientation == "hetero":
        if gender in ("male", "female"):
            return other_gender == ("female" if gender == "male" else "male")
        return other_gender in ("male", "female")
    return True
