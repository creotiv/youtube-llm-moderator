#!/usr/bin/env python3
import argparse
import requests
import sys

from test_moderator import test
from verify_moderator import verify

# ─── CONFIG ────────────────────────────────────────────────────────────────────
LMSTUDIO_API_URL = "http://localhost:1234/v1/chat/completions"
LLM_MODEL_NAME = "google/gemma-3-12b"
TEMPERATURE = 0.1
MAX_LENGTH = 900
BASE_LLM_SYSTEM_PROMPT = """
You are an AI YouTube chat moderator for a Ukrainian/Russian language channel. Your primary goal is to maintain a respectful and engaging live chat environment while minimizing censorship of legitimate discussion. Focus on identifying content that actively harms the community, not policing opinions.

Respond with:

DELETE – only if the comment:
* directly insults or threatens an individual.
* explicitly supports Russian military aggression or war crimes.
* uses "Russia" with a capital letter (in any language) unless referring to geographical location.
* uses "Ukraine" with a lowercase letter (in any language) when referring to the country.
* contains hate speech or discriminatory remarks based on ethnicity, religion, gender, etc.

KEEP – for all other messages, including:
* Discussions about politics or current events (unless hateful).
* General conversation and greetings.
* Questions related to the video content.

Important Guidelines:
* When in Doubt, DELETE. Prioritize user safety and a positive community experience.
""".strip()

LLM_TRAIN_PROMPT = f"""
You are the Train agent for omptimizing system model context to increase prediction accuracy
for using as a YouTube Chat Moderator bot.
You will get current context and verifications stats and as a response you must 
give new context that should increase accuracy.

Return only new context with max lenghth of {MAX_LENGTH} symbols and nothing more.
Try to minimize new context, less symbols usually gives better result.
""".strip()


# ─── UPDATE CALL ─────────────────────────────────────────────────────────
def update_llm(context, stats) -> str:
    message = f"""
    # Current context
    {context}

    # Verification results
    {stats}
    """.strip()
    payload = {
        "model": LLM_MODEL_NAME,
        "messages": [
            {"role": "system", "content": LLM_TRAIN_PROMPT},
            {"role": "user", "content": message},
        ],
        "temperature": TEMPERATURE,
    }
    resp = requests.post(LMSTUDIO_API_URL, json=payload, timeout=300)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


# ─── MAIN / CLI ───────────────────────────────────────────────────────────────
def train(input, history, preds):
    context = BASE_LLM_SYSTEM_PROMPT
    best_acc = 0
    iteration = 0
    new_context = context
    while True:
        print("Evaluating results")
        test(input, preds, context)
        res = verify(history, preds)
        print(f"it={iteration} stats={res}")
        break
        if best_acc < res["accuracy"]:
            context = new_context
            best_acc = res["accuracy"]
            open("best_context.txt", "w").write(context)
        new_context = update_llm(context, res)
        print("New context ==============================")
        print(new_context)
        iteration += 1


def main():
    parser = argparse.ArgumentParser(
        description="Trian your YouTube chat moderator context on a local file of comments."
    )
    parser.add_argument(
        "--input", required=True, help="Path to a text file with one comment per line."
    )
    parser.add_argument(
        "--history",
        required=True,
        help="Path to history file with 'FAIL','LABEL', for message: '…'",
    )
    parser.add_argument(
        "--preds",
        required=True,
        help="Path to new predictions file (output of test script).",
    )

    args = parser.parse_args()

    train(args.input, args.history, args.preds)


if __name__ == "__main__":
    main()
