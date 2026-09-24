#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate audio files for English review page. Two voices:
- 'A' = Andrew (deep, meeting-chair style, represents Lucas/Yoyo asking questions)
- 'B' = Brian (approachable male, represents you answering)
Each dialogue entry: {id, a: [en, zh], b: [en, zh]}
Also single-sentence drill items."""
import asyncio, edge_tts, json, os

OUT = "/mnt/openclaw/.openclaw/workspace/exclusivity/english_review/audio"
os.makedirs(OUT, exist_ok=True)

VOICES = {"A": "en-US-AndrewMultilingualNeural", "B": "en-US-BrianMultilingualNeural"}

# ── Section 1: 12 core question patterns (yoyo/lucas style) ──
questions = [
    ("q01", "What is the status of this case?"),
    ("q02", "Why did we lose this merchant?"),
    ("q03", "How much was the upfront money?"),
    ("q04", "How many stores are included in this deal?"),
    ("q05", "What is the KP's attitude toward us?"),
    ("q06", "Is he willing to sign, or still considering?"),
    ("q07", "What is our counter-offer?"),
    ("q08", "How many orders does he do per day on each platform?"),
    ("q09", "When did you last visit this merchant?"),
    ("q10", "Did he receive a formal contract or just a verbal offer?"),
    ("q11", "When does the contract expire?"),
    ("q12", "What is the risk level of this case — high, medium, or low?"),
    ("q13", "When did the merchant receive the offer, and when did he sign it?"),
    ("q14", "What are the details of the offer?"),
    ("q15", "How is the merchant performing on the competitor's platform?"),
    ("q16", "What is the merchant's attitude toward the offer?"),
    ("q17", "If the KP is still considering, do we need a Keeta counter-offer?"),
]

# ── Section 2: dialogues (A = reviewer/chair, B = you) ──
dialogues = [
    ("d01", "Let's go through the cases one by one. Can you start with the first one?",
          "Sure. This merchant is still considering our offer. He hasn't signed yet."),
    ("d02", "What is the upfront money from the competitor?",
          "The competitor offered two hundred K upfront, for three brands."),
    ("d03", "Why did we lose this case?",
          "We lost it because we didn't match the offer. Their money was too high for us to follow."),
    ("d04", "How many orders does he do per day?",
          "Around one hundred and sixty orders per day on Keeta, and about eighty on the competitor."),
    ("d05", "Did he receive a formal contract or just a verbal offer?",
          "Just a verbal offer — he never received the paper contract."),
    ("d06", "When did you last visit this merchant?",
          "I visited him last Friday. He is willing to sign if we come with a higher amount."),
    ("d07", "What is the KP's attitude?",
          "He is happy with us, but he heard his friends who signed with the competitor had bad experiences."),
    ("d08", "Is this case high risk?",
          "Yes, it's still high risk, because the competitor can come back with more money at any time."),
    ("d09", "When does the exclusivity contract expire?",
          "It's a three-year contract, signed about six months ago."),
    ("d10", "What is our counter-offer?",
          "We are preparing a package with upfront money plus guaranteed GMV."),
    ("d11", "Can you complete the missing information before Wednesday?",
          "Yes, I will fill in all the information in the dashboard by tomorrow morning."),
    ("d12", "Do you have any update on this merchant?",
          "Not yet. The BD will visit the store this week and collect more information."),
]

# ── Section 3: key sentences for fluency ──
sentences = [
    ("s01", "We need to complete the information for each case, one by one."),
    ("s02", "The merchant is still operating with us normally."),
    ("s03", "He dropped seventy percent of his order volume in one week."),
    ("s04", "This is a huge player in our district."),
    ("s05", "The BD never really visited the merchant. He was always communicating through WhatsApp."),
    ("s06", "The agent who signed the contract promised a lot of things and never showed up."),
    ("s07", "It was a lack of service to the merchant, that's why we lost him."),
    ("s08", "He is willing to sign, but he refused our offer for now."),
    ("s09", "We should keep the relationship and look for new opportunities in the future."),
    ("s10", "The competitor offered guaranteed GMV and a big upfront payment."),
]

async def gen(text, path, voice, rate="+0%", pitch="+0Hz"):
    tts = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, proxy="http://127.0.0.1:8118")
    await tts.save(path)

async def main():
    tasks = []
    for sid, en in questions:
        tasks.append(gen(en, f"{OUT}/{sid}.mp3", VOICES["A"]))
    for sid, a_en, b_en in dialogues:
        tasks.append(gen(a_en, f"{OUT}/{sid}_a.mp3", VOICES["A"]))
        tasks.append(gen(b_en, f"{OUT}/{sid}_b.mp3", VOICES["B"]))
    for sid, en in sentences:
        tasks.append(gen(en, f"{OUT}/{sid}.mp3", VOICES["B"]))
    # limit concurrency
    for i in range(0, len(tasks), 8):
        await asyncio.gather(*tasks[i:i+8])
        print(f"batch {i//8+1} done ({min(i+8,len(tasks))}/{len(tasks)})")

asyncio.run(main())
print("ALL AUDIO DONE")
