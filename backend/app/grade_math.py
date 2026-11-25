import math
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class GradeSummary:
    weighted_points: float
    graded_weight: float
    current_percentage: float | None
    final_percentage: float | None
    is_complete: bool


def _summary_from(categories: Sequence[sqlite3.Row]) -> GradeSummary:
    total_weight = sum(row["weight"] for row in categories)
    weighted_points = 0.0
    graded_weight = 0.0
    all_assessments_scored = bool(categories)

    for category in categories:
        if category["scored_count"] > 0 and category["scored_max_points"] > 0:
            category_fraction = category["earned_points"] / category["scored_max_points"]
            weighted_points += category_fraction * category["weight"]
            graded_weight += category["weight"]
        if (
            category["assessment_count"] == 0
            or category["scored_count"] != category["assessment_count"]
        ):
            all_assessments_scored = False

    weights_total_one_hundred = math.isclose(total_weight, 100.0, abs_tol=0.000001)
    is_complete = weights_total_one_hundred and all_assessments_scored
    current_percentage = (
        round(weighted_points / graded_weight * 100, 2)
        if graded_weight > 0
        else None
    )
    final_percentage = round(weighted_points, 2) if is_complete else None
    return GradeSummary(
        weighted_points=round(weighted_points, 2),
        graded_weight=round(graded_weight, 2),
        current_percentage=current_percentage,
        final_percentage=final_percentage,
        is_complete=is_complete,
    )


def calculate_grade_for_student(
    connection: sqlite3.Connection,
    section_id: int,
    student_id: int,
) -> GradeSummary:
    categories = connection.execute(
        """
        SELECT assessment_categories.weight,
               COUNT(assessments.id) AS assessment_count,
               COUNT(assessment_scores.id) AS scored_count,
               COALESCE(
                   SUM(CASE WHEN assessment_scores.id IS NOT NULL
                       THEN assessments.max_points ELSE 0 END),
                   0
               ) AS scored_max_points,
               COALESCE(SUM(assessment_scores.points), 0) AS earned_points
        FROM assessment_categories
        LEFT JOIN assessments
            ON assessments.category_id = assessment_categories.id
        LEFT JOIN assessment_scores
            ON assessment_scores.assessment_id = assessments.id
            AND assessment_scores.student_id = ?
        WHERE assessment_categories.section_id = ?
        GROUP BY assessment_categories.id
        """,
        (student_id, section_id),
    ).fetchall()
    return _summary_from(categories)


def load_scores_for_students(
    connection: sqlite3.Connection,
    section_id: int,
    student_ids: Sequence[int],
) -> dict[int, dict[int, float]]:
    if not student_ids:
        return {}
    placeholders = ", ".join("(?)" for _ in student_ids)
    rows = connection.execute(
        f"""
        WITH students(id) AS (VALUES {placeholders})
        SELECT assessment_scores.student_id, assessment_scores.assessment_id,
               assessment_scores.points
        FROM students
        JOIN assessment_scores ON assessment_scores.student_id = students.id
        JOIN assessments ON assessments.id = assessment_scores.assessment_id
        JOIN assessment_categories
            ON assessment_categories.id = assessments.category_id
        WHERE assessment_categories.section_id = ?
        """,
        (*student_ids, section_id),
    ).fetchall()
    scores: dict[int, dict[int, float]] = {
        student_id: {} for student_id in student_ids
    }
    for row in rows:
        scores[row["student_id"]][row["assessment_id"]] = row["points"]
    return scores


def calculate_grades_for_students(
    connection: sqlite3.Connection,
    section_id: int,
    student_ids: Sequence[int],
) -> dict[int, GradeSummary]:
    if not student_ids:
        return {}
    placeholders = ", ".join("(?)" for _ in student_ids)
    rows = connection.execute(
        f"""
        WITH students(id) AS (VALUES {placeholders})
        SELECT students.id AS student_id,
               assessment_categories.weight AS weight,
               COUNT(assessments.id) AS assessment_count,
               COUNT(assessment_scores.id) AS scored_count,
               COALESCE(
                   SUM(CASE WHEN assessment_scores.id IS NOT NULL
                       THEN assessments.max_points ELSE 0 END),
                   0
               ) AS scored_max_points,
               COALESCE(SUM(assessment_scores.points), 0) AS earned_points
        FROM students
        CROSS JOIN assessment_categories
        LEFT JOIN assessments
            ON assessments.category_id = assessment_categories.id
        LEFT JOIN assessment_scores
            ON assessment_scores.assessment_id = assessments.id
            AND assessment_scores.student_id = students.id
        WHERE assessment_categories.section_id = ?
        GROUP BY students.id, assessment_categories.id
        """,
        (*student_ids, section_id),
    ).fetchall()

    grouped: dict[int, list[sqlite3.Row]] = {student_id: [] for student_id in student_ids}
    for row in rows:
        grouped[row["student_id"]].append(row)
    return {student_id: _summary_from(group) for student_id, group in grouped.items()}
