from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
from dotenv import load_dotenv
from datetime import datetime

from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableMap

from credit import process_credit_flow

# Load .env
load_dotenv()

# Initialize FastAPI app
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set Google API Key securely
os.environ["GOOGLE_API_KEY"] = "AIzaSyBJLgcXQBIjSjAyU2nzjCHeQ1V7GLxeCoo"

# Load FAISS vector index
embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
vector_store = FAISS.load_local("faiss_index_hdfc_google_emb", embeddings, allow_dangerous_deserialization=True)

# Prompt template
prompt = PromptTemplate(
    input_variables=["context", "question"],
    template="""
You are EVA — a smart, friendly virtual assistant for HDFC Bank. Your job is to answer queries related to HDFC credit cards using the provided document context, and also handle small talk or greetings politely.

Behavior guide:
1. If the user greets you (e.g., "Hi", "Hello", "Good morning"), respond warmly.
2. If the user makes small talk (e.g., "What's your name?", "How are you?"), respond kindly and stay brief.
3. If the user asks about credit cards, answer based ONLY on the given CONTEXT.
4. If the context does not contain the answer, respond with this fallback:

I'm sorry, I don't have enough information from the provided documents to answer that.

Now, use the above rules and answer the question:

CONTEXT:
{context}

QUESTION:
{question}
"""
)

# RAG setup
model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.3)
parser = StrOutputParser()

rag_chain = (
    RunnableMap({
        "context": lambda x: "\n\n".join(doc.page_content for doc in x["input_documents"]),
        "question": lambda x: x["question"]
    }) | prompt | model | parser
)

# Chat state
chat_history = []
user_state = {
    "credit_flow": False,
    "info_flow": False
}

# === GET route for initial launch ===
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "chat_history": [],
        "open_chat": False,
        "extra_buttons": []
    })

# === POST route for conversation ===
@app.post("/", response_class=HTMLResponse)
async def query(request: Request, user_query: str = Form(...)):
    user_input = user_query.strip()
    current_time = datetime.now().strftime("%I:%M %p")

    extra_buttons = []
    step = None

    if user_input == "I want to check my eligibility for Credit card":
        user_state["credit_flow"] = True
        user_state["info_flow"] = False
        response, step = process_credit_flow("start")
        extra_buttons = []

    elif user_input == "I want to know more about Credit card and HDFC services":
        user_state["info_flow"] = True
        user_state["credit_flow"] = False
        response = "Hello Dear User, Please let me know your query related to HDFC credit card and other services."
        extra_buttons = []

    elif user_state["credit_flow"]:
        response, step = process_credit_flow(user_input)

        # Determine which buttons to show
        if step == "confirm":
            extra_buttons = ["✅ Yes", "❌ No"]
        elif step == "employment":
            extra_buttons = ["👔 Salaried", "🏢 Self-Employed"]
        else:
            extra_buttons = []

    elif user_state["info_flow"]:
        docs = vector_store.similarity_search(user_input, k=5)
        response = rag_chain.invoke({"input_documents": docs, "question": user_input})
        extra_buttons = []

    else:
        docs = vector_store.similarity_search(user_input, k=5)
        response = rag_chain.invoke({"input_documents": docs, "question": user_input})
        extra_buttons = []

    chat_history.append({
        "query": user_input,
        "response": response,
        "time": current_time,
        "step": step
    })

    return templates.TemplateResponse("index.html", {
        "request": request,
        "chat_history": chat_history,
        "open_chat": True,
        "extra_buttons": extra_buttons
    })
