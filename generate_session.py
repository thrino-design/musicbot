"""
Run this script ONCE on your local machine (or Termux) to generate
the Pyrogram string session for your assistant/userbot account.

    python generate_session.py

It will ask for your phone number and a verification code.
Copy the printed session string into your .env or Render env vars
as   STRING_SESSION=<the long string>
"""

from pyrogram import Client
import os

API_ID   = int(input("Enter API_ID  : "))
API_HASH =     input("Enter API_HASH: ").strip()

with Client(":memory:", api_id=API_ID, api_hash=API_HASH) as app:
    session = app.export_session_string()

print("\n" + "="*60)
print("✅  Your STRING_SESSION is:\n")
print(session)
print("\n" + "="*60)
print("Copy this into your .env / Render environment as STRING_SESSION=...")
print("Keep it secret — it gives full access to the Telegram account.")
