import json
import re
import os
from flask import Flask, render_template, request, jsonify, session

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- LOAD DATA ----------------
with open("data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# ---------------- NORMALIZE ----------------
def normalize(text):
    return re.sub(r"[^a-zA-ZæøåÆØÅ\s]", "", text.lower()).strip()

# ---------------- LANGUAGE DETECTION (FIXED) ----------------
def detect_language(text):
    # Danish letters → Danish
    if any(c in text for c in "æøå"):
        return "da"

    # ONLY real Danish words (no items like pizza!)
    danish_words = [
        "hej", "hejsa", "goddag",
        "hvad", "hvor", "tak", "hvordan",
        "jeg", "mener", "må", "kan",
        "spørg", "spørger", "spørgsmål",
        "godnat", "selvfølgelig"
    ]

    for word in text.split():
        if word in danish_words:
            return "da"

    return "en"

# ---------------- HELPER ----------------
def get_text(field, lang):
    if isinstance(field, dict):
        return field.get(lang, field.get("en", ""))
    return field

# ---------------- MATCH ITEM ----------------
def match_item(text):
    waste_items = data.get("waste_items", {})

    # exact match
    for key, item in waste_items.items():
        for q in item.get("questions", []):
            if text == q:
                return key

    # partial match
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

# ---------------- IMAGE UPLOAD ----------------
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/image", methods=["POST"])
def handle_image():
    file = request.files["image"]
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    return jsonify({
        "reply": "Karla: I think this is plastic. Put it in plastic.",
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

    # ---------------- GREETING ----------------
    if is_greeting(text):
        if text in ["hej", "hejsa", "goddag", "hallo"]:
            return jsonify({"reply": "Karla: Hej 👋 Hvad vil du smide ud?"})
        else:
            return jsonify({"reply": "Karla: Hello 👋 What do you want to throw away?"})

    # ---------------- LANGUAGE ----------------
    lang = detect_language(text)

    current_intent = session.get("intent")
    last_intent = session.get("last_intent")

    # 🔥 FIX: reset context if new item detected
    new_item = match_item(text)
    if new_item:
        session.pop("intent", None)
        session.pop("last_intent", None)
        current_intent = None
        last_intent = None

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
    item_key = new_item

    if item_key:
        item = data["waste_items"][item_key]

        # Old flow with question/options
        if "question" in item:
            session["intent"] = item_key
            question = get_text(item["question"], lang)

            return jsonify({
                "reply": f"Karla: {question}"
            })

        # Direct answer flow
        if "answer" in item:
            session.pop("intent", None)

            answer = get_text(item["answer"], lang)

            # Build conditions in correct language
            conditions = []

            for condition in item.get("conditions", []):
                conditions.append({
                    "label": condition.get(
                        f"label_{lang}",
                        condition.get("label_en", "")
                    ),
                    "image": condition.get("image")
                })

            return jsonify({
                "reply": f"Karla: {answer}",
                    "image": item.get("image"),
                "conditions": conditions
            })

    # ---------------- FALLBACK ----------------
    return jsonify({
        "reply": "Karla: Jeg forstod det ikke. Kan du formulere det anderledes?"
        if lang == "da"
        else "Karla: I didn't understand that. Can you rephrase or call ?"
    })

# ---------------- RUN ----------------
if __name__ == "__main__":
    print("🚀 Karla chatbot running...")
    app.run(debug=True)