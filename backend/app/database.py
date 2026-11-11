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
            """
        )
