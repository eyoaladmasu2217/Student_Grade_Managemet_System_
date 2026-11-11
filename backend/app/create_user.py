import argparse
import getpass
import sqlite3
from contextlib import closing

from pydantic import EmailStr, TypeAdapter, ValidationError

from app.database import connect, initialize_database
from app.security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an initial gradebook user.")
    parser.add_argument("--email", required=True, help="User email address")
    parser.add_argument("--name", required=True, help="User's display name")
    parser.add_argument(
        "--role",
        required=True,
        choices=("admin", "instructor", "student"),
        help="User role",
    )
    args = parser.parse_args()
    if not args.name.strip():
        parser.error("Name cannot be blank")
    try:
        email = str(TypeAdapter(EmailStr).validate_python(args.email))
    except ValidationError as error:
        parser.error(f"Invalid email: {error}")

    password = getpass.getpass("Password (minimum 12 characters): ")
    if len(password) < 12:
        parser.error("Password must contain at least 12 characters")

    initialize_database()
    with closing(connect()) as connection:
        try:
            connection.execute(
                """
                INSERT INTO users (email, full_name, password_hash, role)
                VALUES (?, ?, ?, ?)
                """,
                (email.lower(), args.name.strip(), hash_password(password), args.role),
            )
        except sqlite3.IntegrityError as error:
            if "UNIQUE constraint failed" in str(error):
                parser.error("A user with that email already exists")
            raise
        connection.commit()
    print(f"Created {args.role} account for {email}")


if __name__ == "__main__":
    main()
