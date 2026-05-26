#!/usr/bin/env python3
"""
A minimal personal-automation agent that runs locally.

What it is: a transparent agent loop. It sends your request to Claude, and if
Claude decides to use a tool, this script runs that tool on YOUR machine, feeds
the result back, and repeats until Claude has a final answer. That loop is the
whole idea behind "agents" — everything else is just more/better tools.

SAFETY: All file operations are sandboxed to ./workspace. The email tool only
DRAFTS a .eml file to your disk — it never sends anything. Calendar is a local
.ics file. Nothing here can touch your real accounts until you wire those in.

Setup:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...      # get one at console.anthropic.com
    python agent.py

Then just talk to it, e.g.:
    "Make a file called groceries.txt with a weekly shopping list"
    "Read groceries.txt and draft an email to my spouse with it"
    "Add a dentist appointment to my calendar next Tuesday at 2pm"
"""

import os
import sys
import json
import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv
load_dotenv()  # reads .env and sets the env vars before the client starts
import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
MODEL = "claude-sonnet-4-20250514"          # swap to a smaller model to save cost while testing
MAX_TURNS = 25                     # safety cap so the loop can't run forever
WORKSPACE = Path("workspace")      # the ONLY folder file tools can touch
WORKSPACE.mkdir(exist_ok=True)

client = anthropic.Anthropic()     # reads ANTHROPIC_API_KEY from env


# ----------------------------------------------------------------------------
# Tools — each is a plain Python function. Add your own here; that's the point.
# ----------------------------------------------------------------------------
def _safe_path(filename: str) -> Path:
    """Keep every file operation inside ./workspace. No path traversal."""
    p = (WORKSPACE / filename).resolve()
    if not str(p).startswith(str(WORKSPACE.resolve())):
        raise ValueError("Path escapes the workspace sandbox — refused.")
    return p

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]

def get_gmail_service():
    """Authenticate once, then reuse a saved token on later runs."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", GMAIL_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())          # token expired -> refresh silently
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)   # opens browser, you click Allow
        with open("token.json", "w") as f:
            f.write(creds.to_json())          # save so next run is silent
    return build("gmail", "v1", credentials=creds)    

def send_email(to: str, subject: str, body: str) -> str:
    # --- the guardrail: a human authorizes the irreversible step ---
    print("\n  ┌─ Claude wants to SEND this email ─────────────")
    print(f"  │ To:      {to}")
    print(f"  │ Subject: {subject}")
    print(f"  │ Body:    {body}")
    print("  └────────────────────────────────────────────────")
    if input("  Type 'yes' to send, anything else to cancel ▸ ").strip().lower() != "yes":
        return "Cancelled by user — email NOT sent."

    service = get_gmail_service()
    msg = MIMEText(body)
    msg["to"] = to
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    sent = service.users().messages().send(
        userId="me", body={"raw": raw}).execute()
    return f"Sent! Message id: {sent['id']}"


def read_recent_emails(max_results: int = 5) -> str:
    """Read the most recent emails: sender, subject, and a short snippet."""
    service = get_gmail_service()
    resp = service.users().messages().list(
        userId="me", maxResults=max_results, labelIds=["INBOX"]).execute()
    messages = resp.get("messages", [])
    if not messages:
        return "Inbox is empty."

    out = []
    for m in messages:
        full = service.users().messages().get(
            userId="me", id=m["id"], format="metadata",
            metadataHeaders=["From", "Subject"]).execute()
        headers = {h["name"]: h["value"] for h in full["payload"]["headers"]}
        sender = headers.get("From", "(unknown)")
        subject = headers.get("Subject", "(no subject)")
        snippet = full.get("snippet", "")
        out.append(f"From: {sender}\nSubject: {subject}\nPreview: {snippet}\n")
    return "\n---\n".join(out)


def list_files() -> str:
    files = [f.name for f in WORKSPACE.iterdir() if f.is_file()]
    return "\n".join(files) if files else "(workspace is empty)"


def read_file(filename: str) -> str:
    p = _safe_path(filename)
    if not p.exists():
        return f"No such file: {filename}"
    return p.read_text()


def write_file(filename: str, content: str) -> str:
    p = _safe_path(filename)
    p.write_text(content)
    return f"Wrote {len(content)} chars to {filename}"


def draft_email(to: str, subject: str, body: str) -> str:
    """Writes a .eml draft you can double-click to open in your mail client."""
    fname = f"draft_{datetime.datetime.now():%Y%m%d_%H%M%S}.eml"
    eml = f"To: {to}\nSubject: {subject}\nContent-Type: text/plain\n\n{body}\n"
    _safe_path(fname).write_text(eml)
    return f"Drafted email to {to} as {fname} (not sent — open it to review/send)"


def add_calendar_event(title: str, start_iso: str, duration_minutes: int = 60) -> str:
    """Appends an event to workspace/calendar.ics (importable into any calendar app)."""
    start = datetime.datetime.fromisoformat(start_iso)
    end = start + datetime.timedelta(minutes=duration_minutes)
    fmt = "%Y%m%dT%H%M%S"
    event = (
        "BEGIN:VEVENT\n"
        f"DTSTART:{start:{fmt}}\n"
        f"DTEND:{end:{fmt}}\n"
        f"SUMMARY:{title}\n"
        "END:VEVENT\n"
    )
    cal = _safe_path("calendar.ics")
    if not cal.exists():
        cal.write_text("BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n")
    text = cal.read_text().replace("END:VCALENDAR\n", event + "END:VCALENDAR\n")
    cal.write_text(text)
    return f"Added '{title}' at {start_iso} to calendar.ics"


# Registry: maps the name Claude calls -> the actual function
TOOL_FUNCTIONS = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "draft_email": draft_email,
    "add_calendar_event": add_calendar_event,
    "send_email": send_email,
    "read_recent_emails": read_recent_emails,
}

# Schemas: how we DESCRIBE the tools to Claude so it knows when/how to call them
TOOLS = [
    {
        "name": "list_files",
        "description": "List all files in the workspace.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file in the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {"filename": {"type": "string"}},
            "required": ["filename"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a file in the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["filename", "content"],
        },
    },
    {
        "name": "draft_email",
        "description": "Draft an email as a local .eml file. Does NOT send.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "add_calendar_event",
        "description": "Add an event to a local .ics calendar file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start_iso": {
                    "type": "string",
                    "description": "ISO 8601, e.g. 2026-06-02T14:00:00",
                },
                "duration_minutes": {"type": "integer"},
            },
            "required": ["title", "start_iso"],
        },
    },
    {
        "name": "send_email",
        "description": "Send a real email via Gmail. The user will be asked to confirm before it actually sends.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "read_recent_emails",
        "description": "Read the most recent emails from Gmail inbox with sender, subject, and snippet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of emails to fetch (default: 5)"
                },
            },
            "required": [],
        },
    },
]


# ----------------------------------------------------------------------------
# The agent loop — this is the part worth reading twice
# ----------------------------------------------------------------------------
def run_agent(user_message: str, history: list) -> list:
    history.append({"role": "user", "content": user_message})

    for _ in range(MAX_TURNS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            tools=TOOLS + [{"type": "web_search_20250305", "name": "web_search"}],
            system=(
                "You are a personal automation assistant running locally on the "
                "user's machine. Today's date is "
                f"{datetime.date.today():%Y-%m-%d}. Use tools to actually do "
                "things rather than just describing them. Be concise."
            ),
            messages=history,
        )

        # Record what the assistant said/decided
        history.append({"role": "assistant", "content": response.content})

        # If Claude didn't ask for a tool, it's done — print and return.
        if response.stop_reason != "tool_use":
            final = "".join(b.text for b in response.content if b.type == "text")
            print(f"\n🤖 {final}\n")
            return history

        # Otherwise, run each requested tool and collect the results
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            fn = TOOL_FUNCTIONS.get(block.name)
            print(f"   ⚙️  {block.name}({json.dumps(block.input)})")
            try:
                result = fn(**block.input) if fn else f"Unknown tool: {block.name}"
            except Exception as e:
                result = f"Error: {e}"
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })

        # Feed the tool outputs back in and let the loop continue
        history.append({"role": "user", "content": tool_results})

    print("\n🤖 (stopped: hit the turn limit)\n")
    return history


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY first (export ANTHROPIC_API_KEY=sk-ant-...)")

    print("Local agent ready. Type a request, or 'quit' to exit.")
    print(f"Sandbox: {WORKSPACE.resolve()}\n")

    history = []
    while True:
        try:
            msg = input("you ▸ ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if msg.lower() in {"quit", "exit"}:
            break
        if msg:
            history = run_agent(msg, history)


if __name__ == "__main__":
    main()