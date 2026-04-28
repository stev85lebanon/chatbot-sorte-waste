import os
import json
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

model = genai.GenerativeModel("gemini-2.5-flash")

app = Flask(__name__)

with open("data.json", "r") as f:
    data = json.load(f)

intents = list(data.keys())


def classify_intent(user_input):
    prompt = f"""
Choose ONE category from:
{intents}

Return only category name.

User: {user_input}
"""
    response = model.generate_content(prompt)
    return response.text.strip()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json["message"]

    intent = classify_intent(user_input)

    if intent in data:
        reply = data[intent]["answer"]
    else:
        reply = "Sorry, I don't understand."

    return jsonify({"reply": reply})


if __name__ == "__main__":
    app.run(debug=True)