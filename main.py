from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import os
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableMap
from datetime import datetime

# Initialize FastAPI app
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set Google API Key (consider using dotenv or secrets manager in production)
os.environ["GOOGLE_API_KEY"] = "AIzaSyBJLgcXQBIjSjAyU2nzjCHeQ1V7GLxeCoo"

# Load FAISS vector index
embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
vector_store = FAISS.load_local("faiss_index_hdfc_google_emb", embeddings, allow_dangerous_deserialization=True)

# Define the prompt template
prompt = PromptTemplate(
    input_variables=["context", "question"],
    template="""
You are EVA — a smart, friendly virtual assistant for HDFC Bank. Your job is to answer queries related to HDFC credit cards using the provided document context, and also handle small talk or greetings politely.

Behavior guide:
1. If the user greets you (e.g., "Hi", "Hello", "Good morning"), respond warmly.
2. If the user makes small talk (e.g., "What's your name?", "How are you?"), respond kindly and stay brief.
3. If the user asks about credit cards, answer based ONLY on the given CONTEXT.
4. If the context does not contain the answer, respond with this fallback:

""

Now, use the above rules and answer the question:

CONTEXT:
{context}

QUESTION:
{question}
"""
)


# Define the model and RAG pipeline
model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.3)
parser = StrOutputParser()

rag_chain = (
    RunnableMap({
        "context": lambda x: "\n\n".join(doc.page_content for doc in x["input_documents"]),
        "question": lambda x: x["question"]
    })
    | prompt
    | model
    | parser
)

# Route: Homepage
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "response": None})

# Route: Handle form submission
current_time = datetime.now().strftime("%I:%M %p")

from datetime import datetime

chat_history = []

@app.post("/", response_class=HTMLResponse)
async def query(request: Request, user_query: str = Form(...)):
    docs = vector_store.similarity_search(user_query, k=5)
    answer = rag_chain.invoke({"input_documents": docs, "question": user_query})

    current_time = datetime.now().strftime("%I:%M %p")  # 12-hour format

    chat_history.append({
        "query": user_query,
        "response": answer,
        "time": current_time
    })

    return templates.TemplateResponse("index.html", {
        "request": request,
        "chat_history": chat_history,
        "open_chat": True
    })
