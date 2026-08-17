from __future__ import annotations


def calculate_score(
    review_count: int,
    average: float,
    **kwargs,
) -> float | None:

    if review_count < 2:
        return None

    return average


def compute_weighted_total(
    creativity: int,
    technical_execution: int,
    feasibility: int,
    problem_fit_demo: int,
) -> float:

    return round(
        (creativity / 10) * 35
        + (technical_execution / 10) * 35
        + (feasibility / 6) * 20
        + (problem_fit_demo / 4) * 10,
        2,
    )