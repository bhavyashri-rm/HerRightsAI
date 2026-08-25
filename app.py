from flask import Flask, request, jsonify, session, send_from_directory
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os


# ============================================================
# HER RIGHTS AI
# ============================================================

app = Flask(__name__, static_folder="static")

# IMPORTANT:
# Change this to a long random secret before deploying.
app.secret_key = "HerRightsAI-college-project-change-this-secret-key"


# ============================================================
# DATABASE
# ============================================================

DATABASE = "herRights.db"


def get_db():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            email TEXT UNIQUE NOT NULL,

            password TEXT NOT NULL,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )
    """)

    conn.commit()

    conn.close()


# ============================================================
# SERVE FRONTEND
# ============================================================

@app.route("/")
def home():

    return send_from_directory(
        app.static_folder,
        "index.html"
    )


@app.route("/<path:filename>")
def serve_static(filename):

    return send_from_directory(
        app.static_folder,
        filename
    )


# ============================================================
# SIGN UP
# ============================================================

@app.route("/api/signup", methods=["POST"])
def signup():

    data = request.get_json()

    if not data:

        return jsonify({
            "success": False,
            "message": "No data received."
        }), 400


    name = data.get("name", "").strip()

    email = data.get("email", "").strip().lower()

    password = data.get("password", "")


    # -----------------------------
    # Validation
    # -----------------------------

    if not name:

        return jsonify({
            "success": False,
            "message": "Please enter your name."
        }), 400


    if not email:

        return jsonify({
            "success": False,
            "message": "Please enter your email."
        }), 400


    if not password:

        return jsonify({
            "success": False,
            "message": "Please enter a password."
        }), 400


    if len(password) < 6:

        return jsonify({
            "success": False,
            "message":
                "Password must contain at least 6 characters."
        }), 400


    # -----------------------------
    # Hash password
    # -----------------------------

    password_hash = generate_password_hash(password)


    conn = get_db()


    try:

        conn.execute(
            """
            INSERT INTO users
            (name, email, password)
            VALUES (?, ?, ?)
            """,

            (
                name,
                email,
                password_hash
            )
        )

        conn.commit()


    except sqlite3.IntegrityError:

        conn.close()

        return jsonify({
            "success": False,
            "message":
                "An account with this email already exists."
        }), 409


    conn.close()


    # -----------------------------
    # Automatically log user in
    # -----------------------------

    conn = get_db()

    user = conn.execute(
        """
        SELECT id, name, email
        FROM users
        WHERE email = ?
        """,
        (email,)
    ).fetchone()

    conn.close()


    session["user_id"] = user["id"]

    session["user_name"] = user["name"]

    session["user_email"] = user["email"]


    return jsonify({

        "success": True,

        "message":
            "Account created successfully.",

        "user": {

            "name": user["name"],

            "email": user["email"]

        }

    })


# ============================================================
# LOGIN
# ============================================================

@app.route("/api/login", methods=["POST"])
def login():

    data = request.get_json()


    if not data:

        return jsonify({
            "success": False,
            "message": "No data received."
        }), 400


    email = data.get(
        "email",
        ""
    ).strip().lower()


    password = data.get(
        "password",
        ""
    )


    if not email or not password:

        return jsonify({
            "success": False,
            "message":
                "Please enter email and password."
        }), 400


    conn = get_db()


    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE email = ?
        """,

        (email,)
    ).fetchone()


    conn.close()


    if user is None:

        return jsonify({
            "success": False,
            "message":
                "No account found with this email."
        }), 401


    # -----------------------------
    # Check password
    # -----------------------------

    if not check_password_hash(
        user["password"],
        password
    ):

        return jsonify({
            "success": False,
            "message":
                "Incorrect password."
        }), 401


    # -----------------------------
    # Create session
    # -----------------------------

    session["user_id"] = user["id"]

    session["user_name"] = user["name"]

    session["user_email"] = user["email"]


    return jsonify({

        "success": True,

        "message":
            "Login successful.",

        "user": {

            "name": user["name"],

            "email": user["email"]

        }

    })


# ============================================================
# LOGOUT
# ============================================================

@app.route("/api/logout", methods=["POST"])
def logout():

    session.clear()


    return jsonify({

        "success": True,

        "message":
            "Logged out successfully."

    })


# ============================================================
# CHECK LOGIN STATUS
# ============================================================

@app.route("/api/me", methods=["GET"])
def current_user():

    if "user_id" not in session:

        return jsonify({

            "logged_in": False

        })


    return jsonify({

        "logged_in": True,

        "user": {

            "id": session["user_id"],

            "name": session["user_name"],

            "email": session["user_email"]

        }

    })


# ============================================================
# OPTIONAL: PROTECTED PROFILE ENDPOINT
# ============================================================

@app.route("/api/profile", methods=["GET"])
def profile():

    if "user_id" not in session:

        return jsonify({

            "success": False,

            "message":
                "Please log in first."

        }), 401


    conn = get_db()


    user = conn.execute(
        """
        SELECT id, name, email, created_at
        FROM users
        WHERE id = ?
        """,

        (session["user_id"],)
    ).fetchone()


    conn.close()


    if user is None:

        session.clear()

        return jsonify({

            "success": False,

            "message":
                "User account not found."

        }), 404


    return jsonify({

        "success": True,

        "user": dict(user)

    })


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    init_db()

    print("")
    print("====================================")
    print("          HER RIGHTS AI")
    print("====================================")
    print("")
    print("Database:")
    print("herRights.db")
    print("")
    print("Backend running at:")
    print("http://127.0.0.1:5000")
    print("")

    app.run(
        debug=True
    )