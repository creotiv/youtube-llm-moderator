#!/usr/bin/env python3
import argparse
import requests
import sys
import csv

# ─── CONFIG ────────────────────────────────────────────────────────────────────
LMSTUDIO_API_URL = 'http://localhost:1234/v1/chat/completions'
LLM_MODEL_NAME    = 'google/gemma-3-12b'
seed = "223423423"
#mistralai/mistral-7b-instruct-v0.3

# LLM_SYSTEM_PROMPT = """
# Ты — модератор чата YouTube. Твоя задача — анализировать пользовательские комментарии.

# Если комментарий оскорбляет автора YouTube-трансляции, отвечай только словом «DELETE1».
# Если в комментарии оскорбляет рассу или национальность, отвечай только словом «DELETE2».
# Если в комментарии содержится угроза, отвечай только словом «DELETE3».
# Если в комментарии славит Россию, отвечай только словом «DELETE4».

# Если комментарий приемлем или ты сомневаешся в его приемлемости, отвечай только словом «KEEP».

# Не добавляйте никаких объяснений.
# """.strip()

# LLM_SYSTEM_PROMPT = """
# You are an AI YouTube chat moderator of ukrainian/russian channel

# Your task is to analyze live chat messages and decide whether they should be deleted or kept.

# Respond with:

# DELETE – only if the comment contains:
# * Personal insults (e.g. name-calling, direct verbal abuse)
# * Explicit hate speech or threats
# * Blatant spam (e.g. links to scams, repetitive ads)
# * Aggressive or coordinated support for Russian aggression, war crimes, or propaganda

# KEEP – for all other messages, including:
# * Criticism, opinions, jokes, or sarcasm
# * Political discussions, even if heated, unless they contain direct personal attacks or disinformation propaganda
# * Mentions of war, army, or politics that do not violate the above conditions


# Do not overreact to passive or vague statements. Only delete content if it is clearly harmful or in violation.

# Respond with only the word: KEEP or DELETE.
# """.strip()

LLM_SYSTEM_PROMPT = """
You are an AI YouTube chat moderator for a Ukrainian/Russian language channel. Your primary goal is to maintain a respectful and engaging live chat environment while minimizing censorship of legitimate discussion.

Your task is to analyze live chat messages and decide whether they should be deleted or kept. Focus on identifying content that actively harms the community, not on policing opinions.

Respond with:

DELETE – only if the comment insult someone or support Russian aggression or include Russia with capital letter
KEEP – for all other messages

Important Guidelines:
* When in Doubt, DELETE


Respond with only the word: KEEP or DELETE.
""".strip()

LLM_SYSTEM_PROMPT = """
You are an AI YouTube chat moderator for a Ukrainian/Russian language channel. Your primary goal is to maintain a respectful and engaging live chat environment while minimizing censorship of legitimate discussion.

Your task is to analyze live chat messages and decide whether they should be deleted or kept. Focus on identifying content that actively harms the community, not on policing opinions.

Respond with:

DELETE – only if the comment:
* insult someone
* support Russian aggression 
* include Russia with capital letter (in any language)
* include Ukraine with lover letter (in any language)
KEEP – for all other messages

Important Guidelines:
* When in Doubt, DELETE


Respond with only the word: KEEP or DELETE.
""".strip()
LLM_SYSTEM_PROMPT = """
You are an AI YouTube chat moderator for a Ukrainian/Russian language channel. Your primary goal is to maintain a respectful and engaging live chat environment while minimizing censorship of legitimate discussion.

Your task is to analyze live chat messages and decide whether they should be deleted or kept. Focus on identifying content that actively harms the community, not on policing opinions.

Respond with:

DELETE – only if the comment:

Directly insults or threatens an individual. (e.g., name-calling, abusive language)
Explicitly supports Russian aggression or war crimes in Ukraine. (e.g., glorifying violence, denying atrocities)
KEEP – for all other messages.

Important Guidelines:

When in doubt, KEEP the message.
Respond with only the word: KEEP or DELETE.
""".strip()
# LLM_SYSTEM_PROMPT = """
# You are an AI YouTube chat moderator for a Ukrainian/Russian language channel. Your primary goal is to maintain a respectful and engaging live chat environment while minimizing censorship of legitimate discussion.

# Your task is to analyze live chat messages and decide whether they should be deleted or kept. Focus on identifying content that actively promotes violence, hatred, or disinformation related to the conflict in Ukraine.

# DELETE – only if the message contains:
# * Direct threats of violence or harm against individuals or groups. (e.g., "I will kill you," "All Ukrainians should be eliminated.")
# * Explicit hate speech targeting individuals or groups based on protected characteristics (e.g., race, religion, ethnicity) in the context of the conflict.
# * Spam or malicious links.

# KEEP – for all other messages, including:
# * Political discussions.
# * Criticism and opinions.
# * General conversation.
# * Important Guideline:

# When in doubt, DELETE the message.

# Respond with only the word: KEEP or DELETE.
# """.strip()

# ─── MODERATION CALL ─────────────────────────────────────────────────────────
def moderate_message_with_llm(message_text: str) -> str:
    if not message_text.strip():
        return "KEEP"
    payload = {
        "model": LLM_MODEL_NAME,
        "messages": [
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {"role": "user",   "content": message_text},
        ],
        "temperature": 0.1,
        "max_tokens": 10
    }
    try:
        resp = requests.post(LMSTUDIO_API_URL, json=payload, timeout=30)
        resp.raise_for_status()
        choice = resp.json()['choices'][0]['message']['content'].strip().upper()
        if choice in ("DELETE","KEEP"):
            return choice
        else:
            return "KEEP"
    except Exception as e:
        print(f"[ERROR] LLM request failed for \"{message_text}\": {e}", file=sys.stderr)
        return "KEEP"

# ─── MAIN / CLI ───────────────────────────────────────────────────────────────
def test(input, preds, context=None):
    global LLM_SYSTEM_PROMPT

    if context:
        LLM_SYSTEM_PROMPT = context

    try:
        csvfile = open(preds, 'w', newline='')
        spamwriter = csv.writer(csvfile, delimiter=',', quotechar="'")
        with open(input, encoding='utf-8') as f:
            for raw in f:
                comment = raw.rstrip("\n")
                if not comment:
                    continue
                decision = moderate_message_with_llm(comment)
                # Output in the requested format:
                spamwriter.writerow([decision, comment])
    except FileNotFoundError:
        print(f"[ERROR] File not found: {input}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Test your YouTube chat moderator context on a local file of comments."
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Path to a text file with one comment per line."
    )
    parser.add_argument("--preds", required=True,
                        help="Path to new predictions file (output of test script).")
    args = parser.parse_args()

    test(args.input, args.preds)

if __name__ == "__main__":
    main()
