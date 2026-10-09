import os
import time
import sqlite3

from flask import Flask, request, jsonify, send_from_directory, session
from werkzeug.security import generate_password_hash, check_password_hash

from google import genai
from google.genai import types


# ============================================
# HER RIGHTS AI
# FLASK BACKEND
# ============================================

app = Flask(__name__)


# ============================================
# SECRET KEY
# ============================================

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "HerRightsAI-development-secret-key"
)


# ============================================
# DATABASE
# ============================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "herRights.db")
STATIC_FOLDER = os.path.join(BASE_DIR, "static")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    # ----------------------------------------
    # USERS TABLE
    # ----------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ----------------------------------------
    # CONVERSATIONS TABLE
    # ----------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # ----------------------------------------
    # MESSAGES TABLE
    # ----------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
    """)

    conn.commit()
    conn.close()


# ============================================
# GEMINI AI
# ============================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

gemini_client = None

if GEMINI_API_KEY:
    gemini_client = genai.Client(
        api_key=GEMINI_API_KEY
    )


PRIMARY_MODEL = "gemini-3.8-flash"
FALLBACK_MODEL = "gemini-3.5-flash-lite"


# ============================================
# HER RIGHTS AI INSTRUCTIONS
# ============================================

SYSTEM_INSTRUCTION = """
You are HerRights AI, an AI-based Legal Rights and Cyber Safety Assistant
designed as a college project for women in India.

Your purpose is to provide clear, simple and supportive general information
about:

- Women's legal rights in India
- Cyber safety
- Online harassment
- Cybercrime
- Domestic violence
- Workplace safety
- General legal procedures
- How to find official government resources
- Safety steps in urgent situations

Important rules:

1. Give general informational guidance, not guaranteed legal outcomes.

2. Do not pretend to be a lawyer, police officer, or government official.

3. Encourage users to contact qualified legal professionals or appropriate
   authorities for serious or urgent matters.

4. For emergencies, advise the user to contact appropriate emergency services.

5. Never ask users to share passwords, OTPs, bank PINs, card numbers,
   authentication codes, or other sensitive credentials.

6. Do not invent laws, government schemes, helpline numbers, or legal sections.

7. When appropriate, direct users to official Indian government resources.

8. India Code:
   https://www.indiacode.gov.in/home

9. National Cyber Crime Reporting Portal:
   https://cybercrime.gov.in/

10. Use simple language suitable for a general user.

11. Be respectful and supportive.

12. If the user describes immediate physical danger, prioritize immediate
    safety and contacting emergency services.

13. Keep responses concise and easy to read.

14. Prefer short paragraphs and bullet points when appropriate.

15. Usually answer within 5 to 8 short sections or bullet points.

16. Always finish the response completely. Do not stop in the middle of a
    sentence or leave an unfinished thought.
"""


# ============================================
# CHECK TEMPORARY GEMINI ERRORS
# ============================================

def is_temporary_error(error):

    error_text = str(error).lower()

    temporary_errors = [
        "429",
        "500",
        "502",
        "503",
        "504",
        "408",
        "resource_exhausted",
        "service_unavailable",
        "timeout",
        "timed out",
        "temporarily unavailable"
    ]

    for error_code in temporary_errors:

        if error_code in error_text:
            return True

    return False


# ============================================
# GEMINI REQUEST WITH RETRY
# ============================================

def generate_with_retry(model_name, user_message):

    max_retries = 2

    for attempt in range(max_retries + 1):

        try:

            print(
                f"Trying {model_name} "
                f"(attempt {attempt + 1}/{max_retries + 1})"
            )

            response = gemini_client.models.generate_content(
                model=model_name,
                contents=user_message,
                config=types.GenerateContentConfig(

                    system_instruction=SYSTEM_INSTRUCTION,

                    thinking_config=types.ThinkingConfig(
                        thinking_level="low"
                    ),

                    max_output_tokens=1600
                )
            )

            if response and response.text:

                print(
                    f"Gemini response received from: {model_name}"
                )

                return response.text

            raise Exception(
                "Gemini returned an empty response."
            )

        except Exception as error:

            print(
                f"Gemini error with {model_name}: {error}"
            )

            if not is_temporary_error(error):

                raise error

            if attempt == max_retries:

                raise error

            delay = 1 * (2 ** attempt)

            print(
                f"Temporary Gemini error. "
                f"Retrying in {delay} seconds..."
            )

            time.sleep(delay)


# ============================================
# GENERATE AI RESPONSE
# ============================================

def generate_ai_response(user_message):

    if not gemini_client:

        raise Exception(
            "Gemini API key is not configured."
        )

    models_to_try = [
        PRIMARY_MODEL,
        FALLBACK_MODEL
    ]

    last_error = None

    for model_name in models_to_try:

        try:

            return generate_with_retry(
                model_name,
                user_message
            )

        except Exception as error:

            last_error = error

            print(
                f"Model failed: {model_name}"
            )

            print(
                "Trying the next model..."
            )

            continue

    raise last_error


# ============================================
# HOME PAGE
# ============================================

@app.route("/")
def home():

    return send_from_directory(
        STATIC_FOLDER,
        "index.html"
    )


# ============================================
# STATIC FILES
# ============================================

@app.route("/<path:filename>")
def static_files(filename):

    return send_from_directory(
        STATIC_FOLDER,
        filename
    )


# ============================================
# SIGNUP
# ============================================

@app.route("/api/signup", methods=["POST"])
def signup():

    data = request.get_json()

    if not data:

        return jsonify({
            "success": False,
            "message": "Invalid request."
        }), 400

    name = data.get(
        "name",
        ""
    ).strip()

    email = data.get(
        "email",
        ""
    ).strip().lower()

    password = data.get(
        "password",
        ""
    )

    if not name or not email or not password:

        return jsonify({
            "success": False,
            "message": "Please fill in all fields."
        }), 400

    if len(password) < 6:

        return jsonify({
            "success": False,
            "message": "Password must contain at least 6 characters."
        }), 400

    conn = get_db()

    existing_user = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        (email,)
    ).fetchone()

    if existing_user:

        conn.close()

        return jsonify({
            "success": False,
            "message": "An account with this email already exists."
        }), 400

    hashed_password = generate_password_hash(
        password
    )

    conn.execute(
        """
        INSERT INTO users (name, email, password)
        VALUES (?, ?, ?)
        """,
        (
            name,
            email,
            hashed_password
        )
    )

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Account created successfully."
    })


# ============================================
# LOGIN
# ============================================

@app.route("/api/login", methods=["POST"])
def login():

    data = request.get_json()

    if not data:

        return jsonify({
            "success": False,
            "message": "Invalid request."
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
            "message": "Please enter email and password."
        }), 400

    conn = get_db()

    user = conn.execute(
        """
        SELECT id, name, email, password
        FROM users
        WHERE email = ?
        """,
        (email,)
    ).fetchone()

    conn.close()

    if not user:

        return jsonify({
            "success": False,
            "message": "Invalid email or password."
        }), 401

    if not check_password_hash(
        user["password"],
        password
    ):

        return jsonify({
            "success": False,
            "message": "Invalid email or password."
        }), 401

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]

    return jsonify({
        "success": True,
        "message": "Login successful.",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"]
        }
    })


# ============================================
# LOGOUT
# ============================================

@app.route("/api/logout", methods=["POST"])
def logout():

    session.clear()

    return jsonify({
        "success": True,
        "message": "Logged out successfully."
    })


# ============================================
# CURRENT USER
# ============================================

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


# ============================================
# PROFILE
# ============================================

@app.route("/api/profile", methods=["GET"])
def profile():

    if "user_id" not in session:

        return jsonify({
            "success": False,
            "message": "Not logged in."
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

    if not user:

        return jsonify({
            "success": False,
            "message": "User not found."
        }), 404

    return jsonify({
        "success": True,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "created_at": user["created_at"]
        }
    })


# ============================================
# CHAT HISTORY
# ============================================

@app.route("/api/conversations", methods=["GET"])
def get_conversations():

    if "user_id" not in session:

        return jsonify({
            "success": False,
            "message": "Please log in to view chat history."
        }), 401

    user_id = session["user_id"]

    conn = get_db()

    conversations = conn.execute(
        """
        SELECT id, title, created_at, updated_at
        FROM conversations
        WHERE user_id = ?
        ORDER BY updated_at DESC
        """,
        (user_id,)
    ).fetchall()

    conn.close()

    result = []

    for conversation in conversations:

        result.append({
            "id": conversation["id"],
            "title": conversation["title"],
            "created_at": conversation["created_at"],
            "updated_at": conversation["updated_at"]
        })

    return jsonify({
        "success": True,
        "conversations": result
    })


# ============================================
# GET ONE CONVERSATION
# ============================================

@app.route(
    "/api/conversations/<int:conversation_id>",
    methods=["GET"]
)
def get_conversation(conversation_id):

    if "user_id" not in session:

        return jsonify({
            "success": False,
            "message": "Please log in."
        }), 401

    user_id = session["user_id"]

    conn = get_db()

    conversation = conn.execute(
        """
        SELECT id, title, created_at, updated_at
        FROM conversations
        WHERE id = ? AND user_id = ?
        """,
        (
            conversation_id,
            user_id
        )
    ).fetchone()

    if not conversation:

        conn.close()

        return jsonify({
            "success": False,
            "message": "Conversation not found."
        }), 404

    messages = conn.execute(
        """
        SELECT id, sender, message, created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id ASC
        """,
        (conversation_id,)
    ).fetchall()

    conn.close()

    message_list = []

    for message in messages:

        message_list.append({
            "id": message["id"],
            "sender": message["sender"],
            "message": message["message"],
            "created_at": message["created_at"]
        })

    return jsonify({
        "success": True,
        "conversation": {
            "id": conversation["id"],
            "title": conversation["title"],
            "created_at": conversation["created_at"],
            "updated_at": conversation["updated_at"],
            "messages": message_list
        }
    })


# ============================================
# DELETE ONE CONVERSATION
# ============================================

@app.route(
    "/api/conversations/<int:conversation_id>",
    methods=["DELETE"]
)
def delete_conversation(conversation_id):

    if "user_id" not in session:

        return jsonify({
            "success": False,
            "message": "Please log in."
        }), 401

    user_id = session["user_id"]

    conn = get_db()

    conversation = conn.execute(
        """
        SELECT id
        FROM conversations
        WHERE id = ? AND user_id = ?
        """,
        (
            conversation_id,
            user_id
        )
    ).fetchone()

    if not conversation:

        conn.close()

        return jsonify({
            "success": False,
            "message": "Conversation not found."
        }), 404

    conn.execute(
        """
        DELETE FROM messages
        WHERE conversation_id = ?
        """,
        (conversation_id,)
    )

    conn.execute(
        """
        DELETE FROM conversations
        WHERE id = ? AND user_id = ?
        """,
        (
            conversation_id,
            user_id
        )
    )

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Conversation deleted."
    })


# ============================================
# DELETE ALL CONVERSATIONS
# ============================================

@app.route("/api/conversations", methods=["DELETE"])
def delete_all_conversations():

    if "user_id" not in session:

        return jsonify({
            "success": False,
            "message": "Please log in."
        }), 401

    user_id = session["user_id"]

    conn = get_db()

    conversations = conn.execute(
        """
        SELECT id
        FROM conversations
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchall()

    for conversation in conversations:

        conn.execute(
            """
            DELETE FROM messages
            WHERE conversation_id = ?
            """,
            (conversation["id"],)
        )

    conn.execute(
        """
        DELETE FROM conversations
        WHERE user_id = ?
        """,
        (user_id,)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "All chat history deleted."
    })


# ============================================
# AI CHAT
# ============================================

@app.route("/api/chat", methods=["POST"])
def chat():

    data = request.get_json()

    if not data:

        return jsonify({
            "success": False,
            "message": "Invalid request."
        }), 400

    user_message = data.get(
        "message",
        ""
    ).strip()

    if not user_message:

        return jsonify({
            "success": False,
            "message": "Please enter a message."
        }), 400

    if len(user_message) > 3000:

        return jsonify({
            "success": False,
            "message": "Please keep your message below 3000 characters."
        }), 400

    if not gemini_client:

        return jsonify({
            "success": False,
            "message": "The AI service is not configured yet."
        }), 500

    # ----------------------------------------
    # CHECK LOGIN
    # ----------------------------------------

    logged_in = "user_id" in session
    user_id = session.get("user_id")

    # Frontend may send an existing conversation ID
    conversation_id = data.get("conversation_id")

    # ----------------------------------------
    # CREATE / CHECK CONVERSATION
    # ----------------------------------------

    conn = None

    try:

        if logged_in:

            conn = get_db()

            # If an existing conversation was supplied,
            # make sure it belongs to this user.
            if conversation_id:

                conversation = conn.execute(
                    """
                    SELECT id
                    FROM conversations
                    WHERE id = ? AND user_id = ?
                    """,
                    (
                        conversation_id,
                        user_id
                    )
                ).fetchone()

                if not conversation:

                    conversation_id = None

            # Create a new conversation if necessary
            if not conversation_id:

                title = user_message.replace("\n", " ").strip()

                if len(title) > 45:
                    title = title[:45].rstrip() + "..."

                if not title:
                    title = "New conversation"

                cursor = conn.execute(
                    """
                    INSERT INTO conversations
                    (user_id, title)
                    VALUES (?, ?)
                    """,
                    (
                        user_id,
                        title
                    )
                )

                conversation_id = cursor.lastrowid

            # Save user message
            conn.execute(
                """
                INSERT INTO messages
                (conversation_id, sender, message)
                VALUES (?, ?, ?)
                """,
                (
                    conversation_id,
                    "user",
                    user_message
                )
            )

            conn.commit()

        # ----------------------------------------
        # GENERATE AI RESPONSE
        # ----------------------------------------

        answer = generate_ai_response(
            user_message
        )

        # ----------------------------------------
        # SAVE AI RESPONSE
        # ----------------------------------------

        if logged_in and conn:

            conn.execute(
                """
                INSERT INTO messages
                (conversation_id, sender, message)
                VALUES (?, ?, ?)
                """,
                (
                    conversation_id,
                    "bot",
                    answer
                )
            )

            conn.execute(
                """
                UPDATE conversations
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
                """,
                (
                    conversation_id,
                    user_id
                )
            )

            conn.commit()

        response_data = {
            "success": True,
            "response": answer
        }

        # Only logged-in users get a conversation ID
        if logged_in:

            response_data["conversation_id"] = conversation_id

        return jsonify(response_data)

    except Exception as error:

        print(
            "Final Gemini error:",
            error
        )

        return jsonify({
            "success": False,
            "message": (
                "The AI service is temporarily unavailable. "
                "Please try again in a moment."
            )
        }), 503

    finally:

        if conn:

            conn.close()


# ============================================
# START APPLICATION
# ============================================

init_db()


if __name__ == "__main__":

    if GEMINI_API_KEY:

        print("========================================")
        print("HerRights AI")
        print("Gemini API key found.")
        print("Primary model:", PRIMARY_MODEL)
        print("Fallback model:", FALLBACK_MODEL)
        print("Thinking level: LOW")
        print("Maximum output tokens: 1600")
        print("Retry system: Enabled")
        print("Chat history: Enabled")
        print("========================================")

    else:

        print("========================================")
        print("WARNING: GEMINI_API_KEY not found.")
        print("========================================")

    app.run(debug=True)