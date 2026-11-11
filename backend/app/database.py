import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

DATABASE_PATH = Path(
    os.getenv(
        "SGMS_DATABASE_PATH",
        str(Path(__file__).resolve().parents[1] / "data" / "gradebook.sqlite3"),
    )
)


def connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def get_db() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()


def initialize_database() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('admin', 'instructor', 'student')),
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            );

            CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS sessions_expires_at_idx ON sessions(expires_at);

            CREATE TABLE IF NOT EXISTS academic_years (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                CHECK (start_date <= end_date)
            );

            CREATE TABLE IF NOT EXISTS terms (
                id INTEGER PRIMARY KEY,
                academic_year_id INTEGER NOT NULL
                    REFERENCES academic_years(id) ON DELETE RESTRICT,
                name TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                CHECK (start_date <= end_date),
                UNIQUE (academic_year_id, name)
            );

            CREATE INDEX IF NOT EXISTS terms_academic_year_idx
                ON terms(academic_year_id);

            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY,
                code TEXT NOT NULL UNIQUE COLLATE NOCASE,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS sections (
                id INTEGER PRIMARY KEY,
                course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE RESTRICT,
                term_id INTEGER NOT NULL REFERENCES terms(id) ON DELETE RESTRICT,
                instructor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                section_code TEXT NOT NULL,
                UNIQUE (course_id, term_id, section_code)
            );

            CREATE INDEX IF NOT EXISTS sections_term_id_idx ON sections(term_id);
            CREATE INDEX IF NOT EXISTS sections_instructor_id_idx ON sections(instructor_id);

            CREATE TABLE IF NOT EXISTS enrollments (
                id INTEGER PRIMARY KEY,
                section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE RESTRICT,
                student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'withdrawn')),
                enrolled_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                UNIQUE (section_id, student_id)
            );

            CREATE INDEX IF NOT EXISTS enrollments_student_id_idx
                ON enrollments(student_id, status);

            CREATE TABLE IF NOT EXISTS assessment_categories (
                id INTEGER PRIMARY KEY,
                section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE RESTRICT,
                name TEXT NOT NULL COLLATE NOCASE,
                weight REAL NOT NULL CHECK (weight > 0 AND weight <= 100),
                UNIQUE (section_id, name)
            );

            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY,
                category_id INTEGER NOT NULL
                    REFERENCES assessment_categories(id) ON DELETE RESTRICT,
                title TEXT NOT NULL COLLATE NOCASE,
                max_points REAL NOT NULL CHECK (max_points > 0),
                due_date TEXT,
                UNIQUE (category_id, title)
            );

            CREATE INDEX IF NOT EXISTS assessments_category_id_idx
                ON assessments(category_id);

            CREATE TABLE IF NOT EXISTS assessment_scores (
                id INTEGER PRIMARY KEY,
                assessment_id INTEGER NOT NULL
                    REFERENCES assessments(id) ON DELETE RESTRICT,
                student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                points REAL NOT NULL CHECK (points >= 0),
                updated_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                UNIQUE (assessment_id, student_id)
            );

            CREATE INDEX IF NOT EXISTS assessment_scores_student_idx
                ON assessment_scores(student_id);

            CREATE TABLE IF NOT EXISTS grade_bands (
                code TEXT PRIMARY KEY COLLATE NOCASE,
                minimum_percentage REAL NOT NULL UNIQUE
                    CHECK (minimum_percentage >= 0 AND minimum_percentage <= 100)
            );

            CREATE TABLE IF NOT EXISTS section_releases (
                section_id INTEGER PRIMARY KEY REFERENCES sections(id) ON DELETE RESTRICT,
                released_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                released_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            );

            CREATE TABLE IF NOT EXISTS released_grades (
                section_id INTEGER NOT NULL REFERENCES section_releases(section_id) ON DELETE RESTRICT,
                student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                percentage REAL NOT NULL CHECK (percentage >= 0 AND percentage <= 100),
                letter_grade TEXT NOT NULL,
                PRIMARY KEY (section_id, student_id)
            );

            CREATE INDEX IF NOT EXISTS released_grades_student_idx
                ON released_grades(student_id);

            CREATE TABLE IF NOT EXISTS grade_corrections (
                id INTEGER PRIMARY KEY,
                section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE RESTRICT,
                student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE RESTRICT,
                previous_points REAL NOT NULL,
                new_points REAL NOT NULL,
                previous_percentage REAL NOT NULL,
                new_percentage REAL NOT NULL,
                previous_letter_grade TEXT NOT NULL,
                new_letter_grade TEXT NOT NULL,
                changed_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                reason TEXT NOT NULL,
                changed_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS grade_corrections_section_idx
                ON grade_corrections(section_id, changed_at DESC);
            """
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO grade_bands (code, minimum_percentage)
            VALUES (?, ?)
            """,
            [("A", 90), ("B", 80), ("C", 70), ("D", 60), ("F", 0)],
        )
