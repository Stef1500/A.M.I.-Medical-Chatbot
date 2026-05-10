from pymongo import MongoClient
import bcrypt

client = MongoClient('localhost', 27017)
db = client["AMIDatabase"]
users = db["users"]
chats = db["chats"]

#functions are subject to change when adapting them to grab POST requests but the core stays the same
def AddUser(username, password):
    if users.find_one({"username": username}) is None:
        password = bcrypt.hashpw(password.encode('utf-8'),bcrypt.gensalt())
        users.insert_one({"username": username, "password": password, "admin": False})
        #goes to login page
    else:
        return "Username already exists"
        #goes back to login page with error message

def login(username, password):
    user = users.find_one({"username": username})

    if user and bcrypt.checkpw(password.encode('utf-8'), user["password"]):
        return True #change to "go to chat page" and send user_id
    return False #change go back to login page with error message


#subject to change depending on whether we make the user write the chat name or let the AI do it
def AddChat(user_id, title):
    chat = {
        "user_id": user_id,
        "title": title,
        "messages": [],
    }
    chats.insert_one(chat)

#Needs to be changed when implementing alongside the page
def NewMessage(user_id, user_message,AMI_message):
    chats.update_one({"user_id": user_id},
                     {"$push": {"messages": {"$each": [user_message, AMI_message]}}}
                     )


#needed to get the context back to AMI
def GetMessages(chat_id):
    chat = chats.find_one({"_id": chat_id})
    if chat is None:
        return "Chat does not exist"

    for message in range(0, len(chat["messages"]),2):
        print(f"User: {chat['messages'][message]}")
        print(f"Bot: {chat['messages'][message+1]}")

