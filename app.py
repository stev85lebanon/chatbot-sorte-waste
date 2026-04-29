import os
import json
import random
import re
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
from difflib import SequenceMatcher

# ---------------- SETUP ----------------
load_dotenv()

app = Flask(__name__)
app.secret_key = "secret123"

# Load data.json
with open("data.json", "r") as f:
    data = json.load(f)

# ---------------- NORMALIZE ----------------
def normalize(text):
    return re.sub(r"[^a-zA-Z\s]", "", text.lower()).strip()

# ---------------- GREETING DETECTION ----------------
WELCOME_PHRASES = [
    "hi", "hello", "hey", "heya", "hallo", "hej",
    "good morning", "good afternoon", "good evening",
    "whats up", "sup", "hola", "ciao"
]

def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def is_welcome(text):
    text = normalize(text)

    for phrase in WELCOME_PHRASES:
        if phrase in text:
            return True

    for phrase in WELCOME_PHRASES:
        if similarity(text, phrase) > 0.75:
            return True

    return False

# ---------------- EXIT DETECTION ----------------
CLOSING_MESSAGES = [
    "Have a nice day!",
    "Good evening!",
    "Take care!",
    "Glad I could help!",
    "Let me know if you need anything else!"
]

def is_exit(text):
    text = normalize(text)
    return any(w in text for w in ["thank", "thanks", "thx", "bye", "ok", "okay", "nothing"])

# ---------------- INTENT CLASSIFIER ----------------
def classify_intent(text):
    text = normalize(text)

    if "pizza" in text:
        return "pizza_box"

    if "glass" in text:
        return "glass_types"

    if "battery" in text:
        return "batteries"

    return "unknown"

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json["message"]
    text = normalize(user_input)

    # ---------------- GREETING ----------------
    if is_welcome(text):
        session.clear()
        return jsonify({
            "reply": "Karla: Hello. What do you want to throw away?"
        })

    # ---------------- EXIT / GOODBYE ----------------
    if is_exit(text):
        session.clear()
        return jsonify({
            "reply": f"Karla: {random.choice(CLOSING_MESSAGES)}"
        })

    # ---------------- CONTINUE FLOW ----------------
    if "intent" in session:
        intent = session["intent"]
        item = data.get(intent, {})
        options = item.get("options", {})

        for key in options:
            if key in text:
                return jsonify({
                    "reply": f"Karla: {options[key]['answer']}"
                })

        return jsonify({
            "reply": f"Karla: {item.get('follow_up', 'Please choose a valid option.')}"
        })

    # ---------------- NEW INTENT ----------------
    intent = classify_intent(text)

    if intent in data:
        item = data[intent]

        if "question" in item:
            session["intent"] = intent
            return jsonify({
                "reply": f"Karla: {item['question']}"
            })

        return jsonify({
            "reply": f"Karla: {item['answer']}"
        })

    return jsonify({
        "reply": "Karla: I didn't understand. Can you rephrase?"
    })


# ---------------- RUN APP ----------------
if __name__ == "__main__":
    print("Karla chatbot running...")
    app.run(debug=True)