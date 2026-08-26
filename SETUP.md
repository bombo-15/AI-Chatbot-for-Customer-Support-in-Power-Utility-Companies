# Kanea Chatbot — How to Run It & Make Changes

A simple guide: how to start the app, how to open the chatbot, and where to
go in the code if you want to change something.

---

## 1. What you need installed

- **Python 3.10+** (for the backend)
- **Node.js 18+** (for the frontend)
- An **Anthropic (Claude) API key** from https://console.anthropic.com/settings/keys
  — this is what powers the chatbot's replies. Requires billing to be set up
  (no perpetual free tier), but costs only cents for typical usage. It goes
  in `backend/.env` as `ANTHROPIC_API_KEY`.

If this is your first time running the project, install the dependencies once:

```bash
cd backend
pip install -r requirements.txt

cd ../frontend
npm install
```

---

## 2. Start the backend

The backend is the "brain" — it classifies messages, talks to the AI model,
and stores everything in the database.

Open a terminal and run:

```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

Leave this terminal open. You'll know it worked when you see:

```
Uvicorn running on http://127.0.0.1:8000
```

---

## 3. Start the frontend

The frontend is the actual chat screen the customer sees.

Open a **second, separate** terminal (keep the backend one running) and run:

```bash
cd frontend
npm run dev
```

You'll see a message with a local URL, usually:

```
Local:   http://localhost:5173/
```

**Important:** the frontend needs the backend running first, otherwise the
chat won't connect.

---

## 4. Open the chatbot

Open your browser and go to:

### 👉 http://localhost:5173

You'll see three tabs:
- **Chat Support** — talk to Kanea, the AI assistant
- **Outage Status** — see live power outages
- **Report a Fault** — submit a fault report

---

## 5. Stopping everything

In each terminal, press `Ctrl + C`.

If a port is still stuck ("in use") afterward, on Windows you can free it with:

```bash
netstat -ano | findstr :8000
taskkill /PID <the number you see> /F
```

(Same for port `5173` if the frontend gets stuck.)

---

## 6. (Optional) Admin dashboard

There's a separate admin site for viewing analytics, fault reports, and
escalations. It's a different app in the `frontend-admin` folder:

```bash
cd frontend-admin
npm install     # first time only
npm run dev
```

It opens on its own port (check the terminal output) and asks for a
password — that password is set in `backend/.env` as `ADMIN_PASSWORD`.

---

## 7. Where to go if you want to change something

Everything the chatbot does lives in a small number of files. Here's what
each one is for, in plain terms:

### Backend files (`backend/`)

| File | What it does |
|---|---|
| `chatbot.py` | The actual "thinking" of the bot: figures out what the customer wants (billing? outage? emergency?), decides how to answer, and builds the message sent to the AI model. **This is the file you'll edit most.** |
| `knowledge_base.py` | Searches `ecg_knowledge.txt` for the most relevant facts to answer a question. |
| `ecg_knowledge.txt` | Plain text file of everything the bot "knows" about ECG — billing, safety, connections, etc. **No coding needed to update this** — just edit the text. |
| `database.py` | Saves and reads everything from the database: chat history, ratings, fault reports, outages. |
| `main.py` | Connects everything together as a web server — this is what the frontend actually talks to. |
| `ecg_scraper.py` | Automatically checks ecg.com.gh once an hour for real outage updates. |
| `eval/` | A testing tool that checks how accurate the bot is — not part of the live chatbot, just for measuring quality. |

### Frontend files (`frontend/src/`)

| File | What it does |
|---|---|
| `components/ChatWindow.jsx` | The actual chat box — messages, typing indicator, quick-reply buttons, star ratings. |
| `App.jsx` | The page around the chat box — header, tabs, footer. |
| `components/FaultForm.jsx` | The "Report a Fault" form. |
| `components/OutageBoard.jsx` | The "Outage Status" list. |
| `tailwind.config.js` | All the brand colors (navy/red/yellow) in one place. |
| `config.js` | Where the frontend looks for the backend — only touch this if you change the backend's address/port. |

---

## 8. Quick "I want to change X" cheat sheet

| I want to... | Go to... |
|---|---|
| Change how the bot talks / its personality | `chatbot.py` |
| Teach the bot new facts / FAQs | `ecg_knowledge.txt` |
| Change when it hands off to a human | `chatbot.py` (the danger/escalation keywords near the top) |
| Change the colors | `tailwind.config.js` |
| Change how chat messages look | `ChatWindow.jsx` |
| Change the fault report form | `FaultForm.jsx` |
| Add a new backend feature/endpoint | `main.py` |
| Change what's saved in the database | `database.py` |
