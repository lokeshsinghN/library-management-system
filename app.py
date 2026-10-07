import os
import sqlite3
from datetime import date, timedelta
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database import get_db, init_db


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "FLASK_SECRET_KEY", "local-development-key-change-this"
)
app.config["DATABASE"] = os.environ.get(
    "LIBRARY_DATABASE", os.path.join(os.path.dirname(__file__), "library.db")
)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

# The tables and default administrator are created automatically on startup.
with app.app_context():
    init_db()


def login_required(view):
    """Send visitors who are not logged in to the admin login page."""
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def required_text(form, field, label):
    value = form.get(field, "").strip()
    if not value:
        raise ValueError(f"{label} is required.")
    return value


def required_integer(form, field, label):
    value = required_text(form, field, label)
    try:
        result = int(value)
    except ValueError:
        raise ValueError(f"{label} must be a whole number.") from None
    if result < 0:
        raise ValueError(f"{label} cannot be negative.")
    return result


def book_form_values(form):
    return (
        required_text(form, "title", "Title"),
        required_text(form, "author", "Author"),
        required_text(form, "category", "Category"),
        required_text(form, "isbn", "ISBN"),
        required_text(form, "publisher", "Publisher"),
        required_integer(form, "quantity", "Quantity"),
    )


def member_form_values(form):
    values = (
        required_text(form, "member_id", "Member ID"),
        required_text(form, "name", "Name"),
        required_text(form, "email", "Email"),
        required_text(form, "phone", "Phone"),
        required_text(form, "address", "Address"),
    )
    if "@" not in values[2] or "." not in values[2].rsplit("@", 1)[-1]:
        raise ValueError("Enter a valid email address.")
    return values


def get_book(book_id):
    with get_db() as connection:
        return connection.execute(
            "SELECT * FROM books WHERE id = ?", (book_id,)
        ).fetchone()


def get_member(member_pk):
    with get_db() as connection:
        return connection.execute(
            "SELECT * FROM members WHERE id = ?", (member_pk,)
        ).fetchone()


def issue_history_rows():
    today = date.today()
    with get_db() as connection:
        rows = connection.execute(
            """
            SELECT issues.*, books.title AS book_title,
                   members.name AS member_name, members.member_id AS member_code
            FROM issues
            JOIN books ON books.id = issues.book_id
            JOIN members ON members.id = issues.member_id
            ORDER BY issues.id DESC
            """
        ).fetchall()

    history = []
    for row in rows:
        item = dict(row)
        due = date.fromisoformat(item["due_date"])
        if item["return_date"]:
            item["status"] = "Returned"
            item["display_overdue_days"] = item["overdue_days"]
            item["display_fine"] = item["fine"]
        elif today > due:
            item["status"] = "Overdue"
            item["display_overdue_days"] = (today - due).days
            item["display_fine"] = item["display_overdue_days"] * 5
        else:
            item["status"] = "Issued"
            item["display_overdue_days"] = 0
            item["display_fine"] = 0
        history.append(item)
    return history


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with get_db() as connection:
            user = connection.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session.permanent = True
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    today = date.today().isoformat()
    with get_db() as connection:
        stats = {
            "total_books": connection.execute(
                "SELECT COALESCE(SUM(quantity), 0) FROM books"
            ).fetchone()[0],
            "available_books": connection.execute(
                "SELECT COALESCE(SUM(available_quantity), 0) FROM books"
            ).fetchone()[0],
            "issued_books": connection.execute(
                "SELECT COUNT(*) FROM issues WHERE return_date IS NULL"
            ).fetchone()[0],
            "total_members": connection.execute(
                "SELECT COUNT(*) FROM members"
            ).fetchone()[0],
            "overdue_books": connection.execute(
                "SELECT COUNT(*) FROM issues WHERE return_date IS NULL AND due_date < ?",
                (today,),
            ).fetchone()[0],
        }
    return render_template("dashboard.html", stats=stats)


@app.route("/books")
@login_required
def books():
    search = request.args.get("q", "").strip()
    with get_db() as connection:
        rows = connection.execute(
            """
            SELECT * FROM books
            WHERE title LIKE ? OR author LIKE ? OR isbn LIKE ?
            ORDER BY title COLLATE NOCASE
            """,
            (f"%{search}%", f"%{search}%", f"%{search}%"),
        ).fetchall()
    return render_template("books.html", books=rows, search=search)


@app.route("/books/add", methods=["GET", "POST"])
@login_required
def add_book():
    if request.method == "POST":
        try:
            values = book_form_values(request.form)
            with get_db() as connection:
                connection.execute(
                    """
                    INSERT INTO books
                    (title, author, category, isbn, publisher, quantity, available_quantity)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    values + (values[5],),
                )
            flash("Book added successfully.", "success")
            return redirect(url_for("books"))
        except ValueError as error:
            flash(str(error), "danger")
        except sqlite3.IntegrityError:
            flash("That ISBN is already in use.", "danger")
    return render_template("add_book.html")


@app.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
@login_required
def edit_book(book_id):
    book = get_book(book_id)
    if book is None:
        flash("Book not found.", "warning")
        return redirect(url_for("books"))
    if request.method == "POST":
        try:
            values = book_form_values(request.form)
            with get_db() as connection:
                issued_count = connection.execute(
                    "SELECT COUNT(*) FROM issues WHERE book_id = ? AND return_date IS NULL",
                    (book_id,),
                ).fetchone()[0]
                if values[5] < issued_count:
                    raise ValueError(
                        f"Quantity cannot be less than the {issued_count} currently issued copy/copies."
                    )
                available = values[5] - issued_count
                connection.execute(
                    """
                    UPDATE books
                    SET title = ?, author = ?, category = ?, isbn = ?, publisher = ?,
                        quantity = ?, available_quantity = ?
                    WHERE id = ?
                    """,
                    values + (available, book_id),
                )
            flash("Book updated successfully.", "success")
            return redirect(url_for("books"))
        except ValueError as error:
            flash(str(error), "danger")
        except sqlite3.IntegrityError:
            flash("That ISBN is already in use by another book.", "danger")
        book = dict(book)
        book.update(
            title=request.form.get("title", book["title"]),
            author=request.form.get("author", book["author"]),
            category=request.form.get("category", book["category"]),
            isbn=request.form.get("isbn", book["isbn"]),
            publisher=request.form.get("publisher", book["publisher"]),
        )
    return render_template("edit_book.html", book=book)


@app.route("/books/<int:book_id>/delete", methods=["POST"])
@login_required
def delete_book(book_id):
    try:
        with get_db() as connection:
            cursor = connection.execute("DELETE FROM books WHERE id = ?", (book_id,))
            if cursor.rowcount == 0:
                flash("Book not found.", "warning")
            else:
                flash("Book deleted successfully.", "success")
    except sqlite3.IntegrityError:
        flash("This book has issue history and cannot be deleted.", "danger")
    return redirect(url_for("books"))


@app.route("/members")
@login_required
def members():
    search = request.args.get("q", "").strip()
    pattern = f"%{search}%"
    with get_db() as connection:
        rows = connection.execute(
            """
            SELECT * FROM members
            WHERE name LIKE ? OR member_id LIKE ? OR email LIKE ?
            ORDER BY name COLLATE NOCASE
            """,
            (pattern, pattern, pattern),
        ).fetchall()
    return render_template("members.html", members=rows, search=search)


@app.route("/members/add", methods=["GET", "POST"])
@login_required
def add_member():
    if request.method == "POST":
        try:
            values = member_form_values(request.form)
            with get_db() as connection:
                connection.execute(
                    """
                    INSERT INTO members (member_id, name, email, phone, address)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    values,
                )
            flash("Member added successfully.", "success")
            return redirect(url_for("members"))
        except ValueError as error:
            flash(str(error), "danger")
        except sqlite3.IntegrityError:
            flash("That Member ID is already in use.", "danger")
    return render_template("add_member.html")


@app.route("/members/<int:member_pk>/edit", methods=["GET", "POST"])
@login_required
def edit_member(member_pk):
    member = get_member(member_pk)
    if member is None:
        flash("Member not found.", "warning")
        return redirect(url_for("members"))
    if request.method == "POST":
        try:
            values = member_form_values(request.form)
            with get_db() as connection:
                connection.execute(
                    """
                    UPDATE members
                    SET member_id = ?, name = ?, email = ?, phone = ?, address = ?
                    WHERE id = ?
                    """,
                    values + (member_pk,),
                )
            flash("Member updated successfully.", "success")
            return redirect(url_for("members"))
        except ValueError as error:
            flash(str(error), "danger")
        except sqlite3.IntegrityError:
            flash("That Member ID is already in use by another member.", "danger")
        member = dict(member)
        for field in ("member_id", "name", "email", "phone", "address"):
            member[field] = request.form.get(field, member[field])
    return render_template("edit_member.html", member=member)


@app.route("/members/<int:member_pk>/delete", methods=["POST"])
@login_required
def delete_member(member_pk):
    try:
        with get_db() as connection:
            cursor = connection.execute(
                "DELETE FROM members WHERE id = ?", (member_pk,)
            )
            if cursor.rowcount == 0:
                flash("Member not found.", "warning")
            else:
                flash("Member deleted successfully.", "success")
    except sqlite3.IntegrityError:
        flash("This member has issue history and cannot be deleted.", "danger")
    return redirect(url_for("members"))


@app.route("/issue", methods=["GET", "POST"])
@login_required
def issue_book():
    if request.method == "POST":
        try:
            member_id = required_integer(request.form, "member_id", "Member")
            book_id = required_integer(request.form, "book_id", "Book")
            if member_id == 0 or book_id == 0:
                raise ValueError("Select both a member and a book.")
            issue_date = date.today()
            due_date = issue_date + timedelta(days=14)
            with get_db() as connection:
                member = connection.execute(
                    "SELECT id FROM members WHERE id = ?", (member_id,)
                ).fetchone()
                if member is None:
                    raise ValueError("The selected member does not exist.")
                cursor = connection.execute(
                    """
                    UPDATE books SET available_quantity = available_quantity - 1
                    WHERE id = ? AND available_quantity > 0
                    """,
                    (book_id,),
                )
                if cursor.rowcount == 0:
                    exists = connection.execute(
                        "SELECT id FROM books WHERE id = ?", (book_id,)
                    ).fetchone()
                    if exists is None:
                        raise ValueError("The selected book does not exist.")
                    raise ValueError("This book is currently unavailable.")
                connection.execute(
                    """
                    INSERT INTO issues (book_id, member_id, issue_date, due_date)
                    VALUES (?, ?, ?, ?)
                    """,
                    (book_id, member_id, issue_date.isoformat(), due_date.isoformat()),
                )
            flash(
                f"Book issued successfully. It is due on {due_date.isoformat()}.",
                "success",
            )
            return redirect(url_for("issue_history"))
        except ValueError as error:
            flash(str(error), "danger")

    with get_db() as connection:
        available_books = connection.execute(
            "SELECT id, title, author, available_quantity FROM books "
            "WHERE available_quantity > 0 ORDER BY title COLLATE NOCASE"
        ).fetchall()
        all_books = connection.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        member_rows = connection.execute(
            "SELECT id, member_id, name FROM members ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return render_template(
        "issue_book.html",
        books=available_books,
        members=member_rows,
        has_books=all_books > 0,
    )


@app.route("/return", methods=["GET", "POST"])
@login_required
def return_book():
    if request.method == "POST":
        try:
            issue_id = required_integer(request.form, "issue_id", "Issue")
            if issue_id == 0:
                raise ValueError("Select an issued book to return.")
            return_date = date.today()
            with get_db() as connection:
                issue = connection.execute(
                    "SELECT * FROM issues WHERE id = ? AND return_date IS NULL",
                    (issue_id,),
                ).fetchone()
                if issue is None:
                    raise ValueError("This issue was already returned or does not exist.")
                due_date = date.fromisoformat(issue["due_date"])
                overdue_days = max(0, (return_date - due_date).days)
                fine = overdue_days * 5
                cursor = connection.execute(
                    """
                    UPDATE issues
                    SET return_date = ?, overdue_days = ?, fine = ?
                    WHERE id = ? AND return_date IS NULL
                    """,
                    (return_date.isoformat(), overdue_days, fine, issue_id),
                )
                if cursor.rowcount != 1:
                    raise ValueError("This issue was already returned.")
                connection.execute(
                    "UPDATE books SET available_quantity = available_quantity + 1 WHERE id = ?",
                    (issue["book_id"],),
                )
            flash(
                f"Book returned. Overdue days: {overdue_days}. Fine: ₹{fine}.",
                "success",
            )
            return redirect(url_for("issue_history"))
        except ValueError as error:
            flash(str(error), "danger")

    today = date.today()
    with get_db() as connection:
        rows = connection.execute(
            """
            SELECT issues.id, issues.issue_date, issues.due_date,
                   books.title AS book_title, members.name AS member_name,
                   members.member_id AS member_code
            FROM issues
            JOIN books ON books.id = issues.book_id
            JOIN members ON members.id = issues.member_id
            WHERE issues.return_date IS NULL
            ORDER BY issues.due_date, issues.id
            """
        ).fetchall()
    outstanding = []
    for row in rows:
        item = dict(row)
        item["overdue_days"] = max(0, (today - date.fromisoformat(item["due_date"])).days)
        item["estimated_fine"] = item["overdue_days"] * 5
        outstanding.append(item)
    return render_template("return_book.html", issues=outstanding)


@app.route("/history")
@login_required
def issue_history():
    return render_template("issue_history.html", issues=issue_history_rows())


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
