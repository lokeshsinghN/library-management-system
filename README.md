# Library Management System

A beginner-friendly library administration app built with Flask, SQLite, HTML, CSS, Bootstrap 5, and Jinja2. An administrator can maintain book and member records, issue and return books, and track overdue fines.

## Features

- Hashed-password admin login and logout
- Dashboard counts for books, availability, issues, members, and overdue books
- Add, search, edit, and delete books and members
- Issue a book for 14 days and record the issue in history
- Return tracking with a fine of ₹5 per overdue day
- Issue history with live status for books that are still issued
- Validation for required fields, duplicate ISBNs and Member IDs, and book quantities
- SQLite database and default administrator are initialized automatically

## Technologies

- Python 3
- Flask
- SQLite (`sqlite3`)
- HTML, CSS, Bootstrap 5, and Jinja2 templates

## Project structure

```text
library_management/
├── app.py
├── database.py
├── requirements.txt
├── library.db              # Created automatically when the app starts
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── books.html
│   ├── add_book.html
│   ├── edit_book.html
│   ├── members.html
│   ├── add_member.html
│   ├── edit_member.html
│   ├── issue_book.html
│   ├── return_book.html
│   └── issue_history.html
└── static/
    └── style.css
```

## Installation

From the project directory, create and activate a virtual environment, then install the dependencies:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Database

No manual database setup is required. Running `app.py` creates `library.db` in the project directory if it does not exist, then creates the `users`, `books`, `members`, and `issues` tables. The default administrator is also created on first startup.

## Run the application

```powershell
python app.py
```

Open [http://127.0.0.1:5000/](http://127.0.0.1:5000/) in a browser. Bootstrap styles are loaded from the Bootstrap CDN, so an internet connection is needed for those styles and responsive navigation.

## Default login

- **Username:** `admin`
- **Password:** `admin123`

Set the `LIBRARY_ADMIN_PASSWORD` environment variable before first startup to choose a different initial admin password. Set `FLASK_SECRET_KEY` to a private value when deploying outside a local development environment. The default credentials and development secret are intended only for local coursework.
