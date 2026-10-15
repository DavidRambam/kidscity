"""`python -m alerts setup`: asks for the alert channels and writes them to .env."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

KEYS = ("SMTP_USER", "SMTP_PASSWORD", "EMAIL_TO", "WHATSAPP_PHONE", "CALLMEBOT_APIKEY",
        "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")


def read_env(path: Path) -> dict[str, str]:
    values = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def write_env(path: Path, updates: dict[str, str]) -> None:
    """Set keys in .env, keeping comments and any other lines as they are."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    done = set()
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if "=" in line and not line.lstrip().startswith("#") and key in updates:
            lines[i] = f"{key}={updates[key]}"
            done.add(key)
    lines += [f"{key}={value}" for key, value in updates.items() if key not in done]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def normalize_phone(phone: str) -> str:
    """'050-123 4567' -> '+972501234567' (CallMeBot wants international format)."""
    digits = re.sub(r"[^\d+]", "", phone or "")
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if digits.startswith("0"):
        digits = "+972" + digits[1:]
    if digits and not digits.startswith("+"):
        digits = "+" + digits
    return digits


def interactive(path: Path, ask: Callable[[str], str] = input, say: Callable[[str], None] = print) -> dict:
    current = read_env(path)

    def question(prompt: str, key: str, hint: str = "") -> str:
        old = current.get(key, "")
        shown = f" [{old}]" if old and "PASSWORD" not in key and "TOKEN" not in key else (
            " [already set]" if old else "")
        if hint:
            say(hint)
        answer = ask(f"{prompt}{shown}: ").strip()
        return answer or old

    say("\n=== Email ===")
    say("Alerts are sent from your Gmail to your Gmail.")
    user = question("Your Gmail address", "SMTP_USER")
    password = question(
        "Gmail app password", "SMTP_PASSWORD",
        "Create one at https://myaccount.google.com/apppasswords (needs 2-Step Verification). "
        "It's 16 letters - paste it here.") if user else ""
    to = question("Send alerts to (Enter = the same Gmail)", "EMAIL_TO") or user

    say("\n=== WhatsApp (via the free CallMeBot service) ===")
    say("1. Open https://www.callmebot.com/blog/free-api-whatsapp-messages/ and add their number to your contacts.")
    say('2. Send it the WhatsApp message:  I allow callmebot to send me messages')
    say("3. It answers with your API key. (Press Enter to skip WhatsApp for now.)")
    phone = normalize_phone(question("Your WhatsApp number, e.g. 050-1234567", "WHATSAPP_PHONE"))
    apikey = question("CallMeBot API key", "CALLMEBOT_APIKEY") if phone else ""

    updates = {"SMTP_USER": user, "SMTP_PASSWORD": password.replace(" ", ""), "EMAIL_TO": to,
               "WHATSAPP_PHONE": phone, "CALLMEBOT_APIKEY": apikey}
    write_env(path, updates)
    say(f"\nSaved to {path}")
    return updates
