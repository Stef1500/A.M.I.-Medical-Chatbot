import os
from bson import ObjectId
from pymongo import MongoClient
import bcrypt
from flask import Flask, render_template, request, jsonify, session, redirect, flash
from AMIDatabase import users, chats

app = Flask(__name__)
app.secret_key = os.urandom(12)


#Adapted and refined version of the preliminary login function
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":


        username = request.form["username"]
        password = request.form["password"]

        user = users.find_one({"username": username})

        if not user:
            flash("Invalid credentials", "error")
            return redirect("/")

        if user and bcrypt.checkpw(password.encode('utf-8'), user["password"]):
            session["user_id"] = str(user["_id"])
            session['logged_in'] = True
            return redirect("/chat")

        if not bcrypt.checkpw(password.encode("utf-8"), user["password"]):
            flash("Invalid credentials", "error")
            return redirect("/")

    return render_template("login.html")


#Adapted and refined version of the preliminary AddUser function
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


#I don't know if we want the settings to be in a different html or in a modal, leaving this here just incase
@app.route("/settings")
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("logged_in", None)
    return redirect("/")


#All basic stuff setup for chat, only things needed are:
# - retrieve and display chat list and history
# - implement AI response logic
# - idr what else
@app.route("/chat", methods=["GET", "POST"])
def chat():
    if not session.get("logged_in"):
        return redirect("/")

    user_id = session["user_id"]
    user = users.find_one({"_id": ObjectId(user_id)})


    return render_template("chat.html")



app.run(port=8000, debug=True)