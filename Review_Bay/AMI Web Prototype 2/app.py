import os
from bson import ObjectId
import bcrypt
from flask import Flask, render_template, request, jsonify, session, redirect, flash
from AMIDatabase import users, chats, AddChat

app = Flask(__name__)
app.secret_key = os.urandom(12)

#NF: Redirects to homepage.html to allow user to choose to: login, enter as guest, or register.
@app.route("/")
def homepage():
    return render_template("homepage.html")

#NF: Created new route for the login option.
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":


        username = request.form["username"]
        password = request.form["password"]

        user = users.find_one({"username": username})

        if not user:
            flash("Invalid credentials", "error")
            return redirect("/login")

        if user and bcrypt.checkpw(password.encode('utf-8'), user["password"]):
            session["user_id"] = str(user["_id"])
            session['logged_in'] = True
            return redirect("/chat")

        if not bcrypt.checkpw(password.encode("utf-8"), user["password"]):
            flash("Invalid credentials", "error")
            return redirect("/login")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if users.find_one({"username": username}) is None:
            password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            users.insert_one({"username": username, "password": password, "admin": False})
            return redirect("/")
        else:
            flash("Username already taken", "error")
            return redirect("/register")


    return render_template("register.html")


#NF: Redirects to settings.html
@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("logged_in", None)
    return redirect("/")

#redirects to chat.html
@app.route("/chat", methods=["GET", "POST"])
def chat():
    #NF: Unsure how to implement this back without messing with accountless login (guest).
    """
    if not session.get("logged_in"):
        return redirect("/")

    user_id = session["user_id"]
    user = users.find_one({"_id": ObjectId(user_id)})

    if user_id:
        render_template("login.html")
    """


    return render_template("chat.html")


#logic to create new chat, returns the chat_id and title
@app.route("/create_chat", methods=["POST"])
def create_chat():
    user_id = session["user_id"]

    data = request.get_json()
    title = data.get("title", "New Chat")

    chat = {
        "user_id": user_id,
        "title": title,
        "messages": []
    }

    result = chats.insert_one(chat)

    return {
        "chat_id": str(result.inserted_id),
        "title": chat["title"]
    }

#returns all chats of a user from the database
@app.route("/get_chats")
def get_chats():
    #NF: This is temporary remedy to account for guest (accountless login). May need to be changed.
    try:
        user_id = session["user_id"]

        if not user_id:
            return {
                "logged_in": 0,
                "chats": []
            }


        user_chats = chats.find({"user_id": user_id})


        return {
            "chats": [
                {"_id": str(chat["_id"]), "title": chat["title"],"logged_in": 1 }
                for chat in user_chats
            ]
        }
    except KeyError:
        return {
            "logged_in": 0,
            "chats": []
        }

#
@app.route("/get_chat/<chat_id>")
def get_chat(chat_id):
    chat = chats.find_one({"_id": ObjectId(chat_id)})
    print("Chat retrieved from DB", chat)

    if not chat:
        print("Chat not found")
        return {"messages": []}

    print("Messages:", chat.get("messages", []))

    return {
        "messages": chat.get("messages", [])
    }

@app.route("/add_message", methods=["POST"])
def add_message():
    data = request.get_json()

    chat_id = data.get("chat_id")
    text = data.get("text")
    sender = data.get("sender")

    if not chat_id:
        return {"error": "No chat_id provided"}, 400

    chats.update_one(
        {"_id": ObjectId(chat_id)},
        {
            "$push": {
                "messages": {
                    "text": text,
                    "sender": sender
                }
            }
        }
    )
    print("Message saved")
    return {"status": "ok"}

app.run(debug=True,port=8000)
