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
You are an expert financial analyst for HDFC Bank. Your task is to provide accurate and concise answers based on the given context.

CONTEXT:
{context}

QUESTION:
{question}

Answer the question based *only* on the provided context. If the information is not in the context, state that you "don't have enough information from the provided documents." Do not make up information.
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
chat_history = []

@app.post("/", response_class=HTMLResponse)
async def query(request: Request, user_query: str = Form(...)):
    docs = vector_store.similarity_search(user_query, k=5)
    answer = rag_chain.invoke({"input_documents": docs, "question": user_query})
    chat_history.append({"query": user_query, "response": answer})
    return templates.TemplateResponse("index.html", {
        "request": request,
        "chat_history": chat_history,
        "open_chat": True
    })

