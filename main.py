from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import os
from langchain.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.chains.question_answering import load_qa_chain

# Initialize FastAPI app
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set your Google API key here (or load from .env)
os.environ["GOOGLE_API_KEY"] = "AIzaSyBJLgcXQBIjSjAyU2nzjCHeQ1V7GLxeCoo"

# Load the FAISS vector store
embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
vector_store = FAISS.load_local("faiss_index_hdfc_google_emb", embeddings, allow_dangerous_deserialization=True)

# Define the prompt and model
prompt_template = """
You are an expert financial analyst for HDFC Bank. Your task is to provide accurate and concise answers based on the given context.

CONTEXT:
{context}

QUESTION:
{question}

Answer the question based *only* on the provided context. If the information is not in the context, state that you "don't have enough information from the provided documents." Do not make up information.
"""
prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.3)
chain = load_qa_chain(llm=model, chain_type="stuff", prompt=prompt)

# Homepage with form
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "response": None})

# Handle form submission
@app.post("/", response_class=HTMLResponse)
async def query(request: Request, user_query: str = Form(...)):
    docs = vector_store.similarity_search(user_query, k=5)
    response = chain({"input_documents": docs, "question": user_query}, return_only_outputs=True)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "response": response["output_text"],
        "query": user_query
    })
