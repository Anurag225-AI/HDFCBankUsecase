import os
import re
from datetime import datetime
from pytz import timezone
from dotenv import load_dotenv

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableMap

from credit import process_credit_flow

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(SessionMiddleware, secret_key="SUPER_SECRET_KEY_123")

# Google API Key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Load FAISS index
embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
vector_store = FAISS.load_local("faiss_index_hdfc_google_emb", embeddings, allow_dangerous_deserialization=True)

# Prompt Template
prompt = PromptTemplate(
    input_variables=["context", "question"],
    template="""
You are EVA — a smart, helpful, and friendly virtual assistant for HDFC Bank.

You handle two types of user queries:
1. Credit Card-related questions (eligibility, benefits, types)
2. Small talk and general greetings

---

For Small Talk (like "Hi", "What’s your name?", "How are you?"):
- Respond briefly and politely.
- Do not ask the user for more information.
- Always keep tone friendly and light.

For Credit Card Queries:
- Answer only using the CONTEXT provided.
- Clearly list specific card names when eligible.
- Never say "you may be eligible" or "visit the website".
- Never ask the user for more info.
- Do not mention online forms or eligibility tools.
- Always use bullet points and short, helpful answers.

---

CONTEXT:
{context}

QUESTION:
{question}

---

Your response:
"""
)

# Setup LLM
model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.3)
parser = StrOutputParser()

rag_chain = (
    RunnableMap({
        "context": lambda x: "\n\n".join(doc.page_content for doc in x["input_documents"]),
        "question": lambda x: x["question"]
    }) | prompt | model | parser
)

# Clean and convert markdown to clean HTML
def format_response_html(response_text: str) -> str:
    lines = response_text.strip().split("\n")
    html_output = "<ul>"
    for line in lines:
        if not line.strip():
            continue
        content = line.strip()
        if content.startswith("*"):
            content = content.lstrip("* ").strip()
            content = re.sub(r"\*\*(.*?)\*\*", r"\1", content)  # remove bold
            content = re.sub(r"\*(.*?)\*", r"\1", content)      # remove italic
            html_output += f"<li>{content}</li>"
        else:
            content = re.sub(r"\*\*(.*?)\*\*", r"\1", content)
            content = re.sub(r"\*(.*?)\*", r"\1", content)
            html_output += f"<p>{content}</p>"
    html_output += "</ul>"
    return html_output

# === Home route ===
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    open_chat = request.query_params.get("reset") == "true" or request.query_params.get("open_chat") == "true"
    chat_history = request.session.get("chat_history", [])
    return templates.TemplateResponse("index.html", {
        "request": request,
        "chat_history": chat_history,
        "open_chat": open_chat,
        "extra_buttons": []
    })

# === Chat route ===
@app.post("/", response_class=HTMLResponse)
async def query(request: Request, user_query: str = Form(...)):
    session = request.session

    # Session init
    if "chat_history" not in session:
        session["chat_history"] = []
    if "user_state" not in session:
        session["user_state"] = { "credit_flow": False, "info_flow": False }

    chat_history = session["chat_history"]
    user_state = session["user_state"]
    user_input = user_query.strip()

    # Reset
    if user_input == "__reset__":
        request.session.clear()
        return RedirectResponse(url="/?reset=true", status_code=303)

    indian_time = datetime.now(timezone('Asia/Kolkata')).strftime("%I:%M %p")
    step = None
    extra_buttons = []

    # --- Flow Handling ---
    if user_input == "I want to check my eligibility for Credit card":
        user_state["credit_flow"] = True
        user_state["info_flow"] = False
        response, step = process_credit_flow("start")
    elif user_input == "I want to know more about Credit card and HDFC services":
        user_state["info_flow"] = True
        user_state["credit_flow"] = False
        response = "Hello Dear User, Please let me know your query related to HDFC credit card and other services."
    elif user_state["credit_flow"]:
        response, step = process_credit_flow(user_input)
        if step == "confirm":
            extra_buttons = ["✅ Yes", "❌ No"]
        elif step == "employment":
            extra_buttons = ["👔 Salaried", "🏢 Self-Employed"]
    else:
        # Default to RAG
        docs = vector_store.similarity_search(user_input, k=5)
        rag_response = rag_chain.invoke({"input_documents": docs, "question": user_input})
        response = format_response_html(rag_response)

    # Save to chat history
    chat_history.append({
        "query": user_input,
        "response": response,
        "time": indian_time,
        "step": step
    })

    session["chat_history"] = chat_history
    session["user_state"] = user_state

    return RedirectResponse(url="/?open_chat=true", status_code=303)
