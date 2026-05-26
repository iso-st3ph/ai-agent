# Local AI Agent — Full Project Notes

Two working AI agents, built from scratch to *see* how agents actually work
instead of hiding the mechanics behind a framework.

- **`agent.py`** — an interactive agent. You chat with it; it uses tools
  (files, calendar, Gmail, web search) to actually do things.
- **`daily_digest.py`** — an autonomous, scheduled agent. Runs unattended once
  a day, searches the web for mentions of you, and emails you a digest.

Both live in the same folder and share the same virtual environment.

## Quick Start

```bash
# Clone and setup
git clone https://github.com/iso-st3ph/ai-agent.git
cd ai-agent

# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Add your Anthropic API key
echo 'ANTHROPIC_API_KEY=sk-ant-your-key-here' > .env

# Run the interactive agent
python agent.py
```

For Gmail features, see **Gmail OAuth setup** below.

---

## The mental model (read this first)

An agent is just a **loop**:

  1. Send the whole conversation to Claude
  2. Did it ask to use a tool? If no -> print the answer, done.
  3. If yes -> run the tool, append the result to the conversation
  4. Go back to step 1

The loop is the agent. **Tools** are what give it abilities. You don't build a
new agent per task — you add tools to the one you have. Everything fancier
(frameworks, Claude Desktop, Copilot, MCP servers) is this same loop with tools
someone else wrote and a UI on top.

### Two kinds of tools

- **Client-side tools** (the ones you write): Claude requests them, the request
  comes back to *your* loop, your Python runs them, you feed the result back.
  Example: `send_email`, `read_file`.
- **Server-side tools** (e.g. web search): Claude runs them on Anthropic's
  servers before the response ever returns to you. You just switch them on in
  the API call — no function to write, no result to handle.

### Adding a client-side tool = 3 edits

1. Write a plain Python function.
2. Register it in `TOOL_FUNCTIONS` (name -> function).
3. Describe it in the `TOOLS` list (so Claude knows when/how to call it).

Claude decides when to call it based on the description.

---

## What each agent can do

**`agent.py`** tools:
- `list_files`, `read_file`, `write_file` — sandboxed to `./workspace`
- `draft_email` — writes a local `.eml` (never sends)
- `add_calendar_event` — appends to a local `.ics`
- `send_email` — sends real Gmail, **with a confirmation prompt** before sending
- `read_recent_emails` — reads your inbox (sender, subject, preview)
- web search — built-in, server-side (added to the API call)

**`daily_digest.py`**:
- Uses Claude + web search to find recent public mentions of you
- Emails a digest to a **hardcoded** address (an unattended job must never
  choose its own recipient)
- Treats search results as data to summarize, never as instructions
  (prompt-injection guard)

---

## Safety choices baked in

- File ops sandboxed to `./workspace` (path traversal blocked)
- `send_email` requires you to type `yes` before anything sends (human-in-the-loop)
- `daily_digest.py` recipient is hardcoded — it can only ever email you
- Least-privilege OAuth scopes (gmail.send + gmail.readonly only)
- Secrets (`.env`, `credentials.json`, `token.json`) kept out of git via `.gitignore`
- `MAX_TURNS` caps the interactive loop so it can't run forever

> Keep all of this on a **personal** Google account. Never point these scripts
> at anything that touches work / contract / government systems.

---

# COMMAND REFERENCE (copy-paste)

## 1. One-time project setup

```bash
# Make the project folder and open it in VS Code
mkdir ~/ai-agent && cd ~/ai-agent
code .

# Create + activate the virtual environment
python3 -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate

# Install all dependencies from requirements.txt
pip install -r requirements.txt

# Or install individually (same result):
# pip install anthropic python-dotenv \
#   google-auth google-auth-oauthlib google-api-python-client

# Put your Anthropic API key in .env (edit the placeholder afterward!)
echo 'ANTHROPIC_API_KEY=sk-ant-your-key-here' > .env
```

Get the API key at console.anthropic.com and load a few dollars of credit.
Then open `.env` in VS Code and replace the placeholder with your real key.

## 2. Create the .gitignore (keeps secrets out of git)

```bash
cat > .gitignore << 'EOF'
# Secrets — never commit these
.env
credentials.json
token.json

# Python
.venv/
__pycache__/
*.pyc

# The agent's working sandbox
workspace/

# Digest log
digest.log
EOF
```

## 3. Gmail OAuth setup (one-time, in the browser)

Done in the Google Cloud Console (console.cloud.google.com), no commands:
1. Create a project; enable the **Gmail API**.
2. OAuth consent screen: External; add yourself as a **test user**.
3. Add scopes: `gmail.send` and `gmail.readonly`.
4. Create an **OAuth client ID** -> type **Desktop App** -> download the JSON.

Then move/rename the downloaded file to `credentials.json`:

```bash
cd ~/ai-agent
mv client_secret_*.json credentials.json     # rename Google's long filename
ls -la ~/ai-agent/*.json                      # confirm: should show credentials.json
```

First run triggers a browser consent screen (click Advanced -> Go to app ->
Allow). That writes `token.json`, and every run after is silent.

If you ADD a scope later (e.g. adding read after send), delete the token so it
re-consents with the new scope:
```bash
rm ~/ai-agent/token.json
python agent.py        # re-authorizes with both scopes
```

## 4. Run the interactive agent

```bash
cd ~/ai-agent && source .venv/bin/activate
python agent.py
```

Example requests to type at the `you ▸` prompt:
```
Make a file called groceries.txt with a weekly shopping list
Read groceries.txt and draft an email to my spouse with the list
What are my 3 most recent emails? Anything that needs a reply?
Find pediatricians within 15 miles of 00000 with 10+ years experience, then email me the shortlist
```

## 5. Test the auth helper directly (debugging)

```bash
python -c "from agent import get_gmail_service; get_gmail_service()"
```
- Browser opens -> auth works.
- `FileNotFoundError: credentials.json` -> file missing/misnamed (see step 3).

## 6. Run the daily digest manually (always test before scheduling)

```bash
cd ~/ai-agent && source .venv/bin/activate
python daily_digest.py
```

## 7. Schedule the daily digest with cron

```bash
crontab -e        # opens editor; press i to insert, Esc then :wq to save (vim)
```

Add this line (runs 8am daily, logs output):
```
0 8 * * * cd ~/ai-agent/ai-agent && ~/ai-agent/ai-agent/.venv/bin/python daily_digest.py >> digest.log 2>&1
```

```bash
crontab -l         # list scheduled jobs to confirm it's set
cat digest.log     # see what happened on past runs
```

> macOS note: cron won't fire if the Mac is asleep at the scheduled time.
> If that's a problem, switch to `launchd` (it can run jobs on wake).

---

## Working with the virtual environment

```bash
# Activate / deactivate (per terminal session)
source ~/ai-agent/.venv/bin/activate
deactivate

# Where am I? Which Python?
which python              # path to active python (venv vs system)
python --version
echo $VIRTUAL_ENV         # active venv path, or empty if none

# What's installed here?
pip list
pip show anthropic

# List Python versions on the system (different from venvs)
which -a python python3
ls /opt/homebrew/bin/python*    # Homebrew (Apple Silicon)
```

Note: both scripts share the **same** venv and folder. You don't "switch
environments" between them — you just run a different file:
```bash
python agent.py            # interactive agent
python daily_digest.py     # scheduled digest
```

---

## How web search was added to agent.py

In `run_agent()`, the `client.messages.create(...)` call passes:
```python
tools=TOOLS + [{"type": "web_search_20250305", "name": "web_search"}],
```
That one addition gives the agent server-side web search. It combines with your
client-side tools, so "research something AND email it to me" works in one request.

---

## Cost tip

While experimenting, switch `MODEL` to a smaller/cheaper model. Bump it back up
for harder tasks.

---

## Where to go next

- **Smarter guardrails** — auto-allow sends to yourself, require confirmation
  for anyone else (encode judgment into the tool instead of always asking).
- **A read-only work-flavored tool** — e.g. a sandboxed `kubectl get` or
  log-grep wrapper. Keep it strictly read-only and isolated from personal stuff.
- **Revisit the Google Calendar MCP server** — now that you've hand-rolled
  OAuth and seen server-side vs client-side tools, the managed MCP version reads
  as a hosted version of what you built, not magic.