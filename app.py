import json
import re
import os
from flask import Flask, render_template, request, jsonify, session

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- LOAD DATA ----------------
with open("data.json", "r") as f:
    data = json.load(f)

# ---------------- NORMALIZE ----------------
def normalize(text):
    return re.sub(r"[^a-zA-ZæøåÆØÅ\s]", "", text.lower()).strip()

# ---------------- LANGUAGE DETECTION ----------------
def detect_language(text):
    if any(c in text for c in "æøå"):
        return "da"

    danish_words = [
        "hej", "hejsa", "goddag",
        "hvad", "hvor", "tak", "hvordan",
        "blomst", "blomster", "ble", "bleer",
        "chipsposer", "tandbørste",
        "pizza", "ren", "fedtet",
        "godnat", "nej", "jeg", "mener",
        "må", "kan", "spørg", "spørger", "spørgsmål"
    ]

    for word in text.split():
        if word in danish_words:
            return "da"

    return "en"

# ---------------- MATCH ITEM ----------------
def match_item(text):
    waste_items = data.get("waste_items", {})

    # 1️⃣ EXACT MATCH FIRST
    for key, item in waste_items.items():
        for q in item.get("questions", []):
            if text == q:
                return key

    # 2️⃣ PARTIAL MATCH
    for key, item in waste_items.items():
        for q in item.get("questions", []):
            if q in text:
                return key

    return None

# ---------------- MATCH OPTION ----------------
def match_option(text, options):
    words = text.split()
    for key, value in options.items():
        for keyword in value.get("keywords", []):
            if keyword in words:
                return key
    return None

# ---------------- SMALL TALK ----------------
def is_greeting(text):
    greetings = ["hi", "hello", "hey", "hej", "hejsa", "goddag", "hallo"]
    return any(word == text for word in greetings)

def is_thanks(text):
    return any(w in text for w in ["thank", "thanks", "tak"])

def is_good_night(text):
    return any(w in text for w in ["good night", "night", "gn", "godnat"])

def is_continue(text):
    keywords = ["spørg", "spørger", "spørgsmål", "må jeg", "kan jeg"]
    return any(k in text for k in keywords)

# ---------------- HELPER ----------------
def get_text(field, lang):
    if isinstance(field, dict):
        return field.get(lang, field.get("en", ""))
    return field

# ---------------- IMAGE UPLOAD ----------------
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/image", methods=["POST"])
def handle_image():
    file = request.files["image"]
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    # 🔥 Demo detection (replace later with AI)
    detected_item = "plastic bottle"

    return jsonify({
        "reply": f"Karla: I think this is {detected_item}. Put it in plastic.",
        "image": "/static/images/plastic.png"
    })

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json["message"]
    text = normalize(user_input)

    print("\n🧠 USER:", text)

    # ---------------- GREETING FIRST ----------------
    if is_greeting(text):
        if text in ["hej", "hejsa", "goddag", "hallo"]:
            return jsonify({
                "reply": "Karla: Hej 👋 Hvad vil du smide ud?"
            })
        else:
            return jsonify({
                "reply": "Karla: Hello 👋 What do you want to throw away?"
            })

    # ---------------- LANGUAGE ----------------
    lang = detect_language(text)

    current_intent = session.get("intent")
    last_intent = session.get("last_intent")

    # ---------------- SMALL TALK ----------------
    if is_good_night(text):
        session.clear()
        return jsonify({
            "reply": "Karla: Godnat 😴" if lang == "da" else "Karla: Good night 😴"
        })

    if is_thanks(text):
        session.clear()
        return jsonify({
            "reply": "Karla: Selv tak 😊 Du kan spørge igen når som helst!"
            if lang == "da"
            else "Karla: Glad I could help 😊 You can ask again anytime!"
        })

    if is_continue(text):
        session.clear()
        return jsonify({
            "reply": "Karla: Selvfølgelig 😊 Hvad vil du smide ud?"
            if lang == "da"
            else "Karla: Of course 😊 What do you want to throw away?"
        })

    # ---------------- CONTEXT FLOW ----------------
    if current_intent:
        item = data.get("waste_items", {}).get(current_intent)

        if item and "options" in item:
            option = match_option(text, item["options"])

            if option:
                session["last_intent"] = current_intent
                session.pop("intent", None)

                answer = get_text(item["options"][option]["answer"], lang)
                image = item["options"][option].get("image")

                return jsonify({
                    "reply": f"Karla: {answer}",
                    "image": image
                })

            follow_up = get_text(item.get("follow_up", ""), lang)

            return jsonify({
                "reply": f"Karla: {follow_up}"
            })

    # ---------------- CORRECTION ----------------
    if last_intent:
        item = data.get("waste_items", {}).get(last_intent)

        if item and "options" in item:
            option = match_option(text, item["options"])

            if option:
                answer = get_text(item["options"][option]["answer"], lang)
                image = item["options"][option].get("image")

                return jsonify({
                    "reply": f"Karla: {answer}",
                    "image": image
                })

    # ---------------- NEW MATCH ----------------
    item_key = match_item(text)

    if item_key:
        item = data["waste_items"][item_key]

        if "question" in item:
            session["intent"] = item_key
            question = get_text(item["question"], lang)

            return jsonify({
                "reply": f"Karla: {question}"
            })

        if "answer" in item:
            answer = get_text(item["answer"], lang)
            image = item.get("image")

            session.pop("intent", None)

            return jsonify({
                "reply": f"Karla: {answer}",
                "image": image
            })

    # ---------------- FALLBACK ----------------
    return jsonify({
        "reply": "Karla: Jeg forstod det ikke. Kan du formulere det anderledes?"
        if lang == "da"
        else "Karla: I didn't understand that. Can you rephrase?"
    })


# ---------------- RUN ----------------
if __name__ == "__main__":
    print("🚀 Karla chatbot running...")
    app.run(debug=True)