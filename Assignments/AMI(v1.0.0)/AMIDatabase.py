from pymongo import MongoClient
import bcrypt

client = MongoClient('localhost', 27017)
db = client["AMIDatabase"]
users = db["users"]
chats = db["chats"]


#subject to change depending on whether we make the user write the chat name or let the AI do it
def AddChat(user_id, title):
    chat = {
        "user_id": user_id,
        "title": title,
        "messages": [],
    }
    chats.insert_one(chat)

#needed to get the context back to AMI
def GetMessages(chat_id):
    chat = chats.find_one({"_id": chat_id})
    if chat is None:
        return "Chat does not exist"

    for message in range(0, len(chat["messages"]),2):
        print(f"User: {chat['messages'][message]}")
        print(f"Bot: {chat['messages'][message+1]}")

