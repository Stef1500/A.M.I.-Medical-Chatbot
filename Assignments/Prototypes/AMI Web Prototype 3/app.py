import os
import uuid
from bson import ObjectId
import bcrypt
from datetime import datetime

from dask.array import remainder
from flask import Flask, render_template, request, jsonify, session, redirect, flash

from AMIDatabase import users, chats
from ami_engine import generate_ami_reply


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))


#NF: Sends user to "account" page. Conditional statements in the HTML are used if user is a Guest or LoggedIn.
@app.route("/account")
def account():
    #NF: If function not run, user status will not be recorded and will be sent to a blank page.
    get_current_user_key()
    return render_template("account.html")

#NF: Sends user to "aboutus" page.
@app.route("/aboutus")
def about_us():
    return render_template("aboutus.html")

#NF: Not yet implemented. Processes LoggedIn user's preferences from the "settings" page.
#SB: Implemented, see ami_engine.py for changes
@app.route("/preferences", methods=["GET", "POST"])
def preferences():
    # NF: To avoid an error the user will be sent to the homepage.
    preferences = request.form["preferences"]

    os.environ["PREFERENCES"] = preferences



    return render_template("chat.html")

#NF: Check if it is properly implemented. Deletes account of user from database.
#SB: Wrong syntax, fixed.
@app.route("/deleteaccount")
def delete_account():
    user_details = get_current_user_key()
    user_account = user_details["user_id"]

    try:
        users.delete_one({"_id": ObjectId(user_account)})
        print(f"deleted account {user_account}")
    except Exception as e:
        print(f"could not delete {user_account} error: {e}")
    return redirect("/logout")

@app.route("/enterguestmode")
def enter_guest_mode():
    session.pop("user_id", None)
    session.pop("logged_in", None)
    session.pop("guest_id", None)
    return redirect("/chat")

def get_current_user_key():
    """
    Logged-in users use their Mongo user_id.
    Guests get a stable guest_id in session.
    """
    if session.get("user_id"):
        return {
            "user_id": session["user_id"],
            "logged_in": True,
        }

    if "guest_id" not in session:
        session["guest_id"] = f"guest-{uuid.uuid4()}"

    return {
        "user_id": session["guest_id"],
        "logged_in": False,
    }


def serialize_chat_messages(messages):
    """
    Ensure messages are safe JSON objects for the frontend.
    """
    safe_messages = []
    for msg in messages:
        safe_messages.append({
            "text": msg.get("text", ""),
            "sender": msg.get("sender", "user"),
            "references": msg.get("references", []),
            "query_type": msg.get("query_type"),
            "expression_state": msg.get("expression_state"),
            "thinking_state": msg.get("thinking_state"),
            "severity": msg.get("severity"),
        })
    return safe_messages


@app.route("/")
def homepage():
    return render_template("homepage.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = users.find_one({"username": username})

        if not user:
            flash("Invalid credentials", "error")
            return redirect("/login")

        if bcrypt.checkpw(password.encode("utf-8"), user["password"]):
            session["user_id"] = str(user["_id"])
            session["logged_in"] = True
            session.pop("guest_id", None)
            return redirect("/chat")

        flash("Invalid credentials", "error")
        return redirect("/login")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if users.find_one({"username": username}) is None:
            password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
            users.insert_one({
                "username": username,
                "password": password_hash,
                "admin": False
            })
            return redirect("/")

        flash("Username already taken", "error")
        return redirect("/register")

    return render_template("register.html")


@app.route("/settings")
def settings():
    # NF: If function not run, user status will not be recorded and will not be shown the preferences feature.
    get_current_user_key()
    return render_template("settings.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("logged_in", None)
    session.pop("guest_id", None)
    return redirect("/")


@app.route("/chat", methods=["GET"])
def chat():
    return render_template("chat.html")


@app.route("/create_chat", methods=["POST"])
def create_chat():
    current_user = get_current_user_key()
    user_id = current_user["user_id"]

    data = request.get_json(silent=True) or {}
    title = data.get("title", "New Chat").strip() or "New Chat"

    chat_doc = {
        "user_id": user_id,
        "title": title,
        "messages": [],
        "last_updated": datetime.utcnow(),

    }

    result = chats.insert_one(chat_doc)

    return jsonify({
        "chat_id": str(result.inserted_id),
        "title": title,
        "logged_in": 1 if current_user["logged_in"] else 0
    })


@app.route("/get_chats")
def get_chats():
    current_user = get_current_user_key()
    user_id = current_user["user_id"]

    user_chats = chats.find({"user_id": user_id}).sort("last_updated", -1)

    return jsonify({
        "logged_in": 1 if current_user["logged_in"] else 0,
        "chats": [
            {
                "_id": str(chat["_id"]),
                "title": chat.get("title", "New Chat")
            }
            for chat in user_chats
        ]
    })


@app.route("/get_chat/<chat_id>")
def get_chat(chat_id):
    try:
        chat = chats.find_one({"_id": ObjectId(chat_id)})
    except Exception:
        return jsonify({"messages": []}), 400

    if not chat:
        return jsonify({"messages": []})

    print(chat)

    return jsonify({
        "messages": serialize_chat_messages(chat.get("messages", []))
    })


@app.route("/add_message", methods=["POST"])
def add_message():
    data = request.get_json(silent=True) or {}

    chat_id = data.get("chat_id")
    text = data.get("text", "")
    sender = data.get("sender", "user")

    if not chat_id:
        return jsonify({"error": "No chat_id provided"}), 400

    try:
        chats.update_one(
            {"_id": ObjectId(chat_id)},
            {
                "$push": {
                    "messages": {
                        "text": text,
                        "sender": sender
                    }
                },
                "$set": {
                    "last_updated": datetime.utcnow()
                }
            }
        )
    except Exception:
        return jsonify({"error": "Invalid chat_id"}), 400

    return jsonify({"status": "ok"})


@app.route("/generate_reply", methods=["POST"])
def generate_reply():
    """
    Main AI route:
    1. Accept user message + chat_id
    2. Save user message
    3. Generate AMI reply through ami_engine
    4. Save AI reply + metadata
    5. Return structured JSON to frontend
    """
    data = request.get_json(silent=True) or {}

    chat_id = data.get("chat_id")
    user_input = (data.get("text") or "").strip()

    if not chat_id:
        return jsonify({"error": "No chat_id provided"}), 400

    if not user_input:
        return jsonify({"error": "No text provided"}), 400

    try:
        object_id = ObjectId(chat_id)
    except Exception:
        return jsonify({"error": "Invalid chat_id"}), 400

    chat_doc = chats.find_one({"_id": object_id})
    if not chat_doc:
        return jsonify({"error": "Chat not found"}), 404

    # Save user message first
    user_message = {
        "text": user_input,
        "sender": "user"
    }

    chats.update_one(
        {"_id": object_id},
        {
            "$push": {"messages": user_message},
            "$set": {"last_updated": datetime.utcnow()}
        }
    )

    # Re-fetch so engine gets up-to-date history
    chat_doc = chats.find_one({"_id": object_id})
    prior_messages = chat_doc.get("messages", [])

    try:
        ai_result = generate_ami_reply(user_input=user_input, prior_messages=prior_messages)
    except Exception as e:
        return jsonify({
            "error": "AI generation failed",
            "details": str(e)
        }), 500

    reply_text = ai_result.get("reply", "").strip()
    query_type = ai_result.get("query_type", "unclear")
    expression_state = ai_result.get("expression_state", "neutral")
    thinking_state = ai_result.get("thinking_state", "done")
    severity = ai_result.get("severity", "low")
    references = ai_result.get("references", [])

    ai_message = {
        "text": reply_text,
        "sender": "ai",
        "references": references,
        "query_type": query_type,
        "expression_state": expression_state,
        "thinking_state": thinking_state,
        "severity": severity,
    }

    chats.update_one(
        {"_id": object_id},
        {
            "$push": {"messages": ai_message},
            "$set": {"last_updated": datetime.utcnow()}
        }
    )

    return jsonify({
        "reply": reply_text,
        "query_type": query_type,
        "expression_state": expression_state,
        "thinking_state": thinking_state,
        "severity": severity,
        "references": references
    })


if __name__ == "__main__":
    app.run(debug=True, port=8000)
