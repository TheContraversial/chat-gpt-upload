from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uuid
import openai
import os
from dotenv import load_dotenv
from docx import Document
from io import BytesIO
import traceback
from sqlmodel import SQLModel, Field, create_engine, Session, select
from datetime import datetime

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Database setup
db_file = "chat.db"
db_engine = create_engine(f"sqlite:///{db_file}")

class ChatMessage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    chat_id: str
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

SQLModel.metadata.create_all(db_engine)

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

@app.get("/ping")
def ping():
    return {"status": "ok"}

@app.post("/start-chat")
def start_chat():
    chat_id = str(uuid.uuid4())
    return {"chat_id": chat_id}

@app.post("/upload-docx")
async def upload_docx(file: UploadFile = File(...), chat_id: str = Form(...)):
    try:
        contents = await file.read()
        document = Document(BytesIO(contents))
        text = "\n".join([p.text for p in document.paragraphs])

        with Session(db_engine) as session:
            msg = ChatMessage(chat_id=chat_id, role="system", content=f"Document uploaded: {file.filename}. Content:\n{text}")
            session.add(msg)
            session.commit()

        print(f"[UPLOAD] chat_id={chat_id} file={file.filename} chars={len(text)}")
        return {"status": "success", "filename": file.filename}
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/ask")
async def ask(request: Request):
    data = await request.json()
    chat_id = data.get("chat_id")
    message = data.get("message")

    if not chat_id:
        raise HTTPException(status_code=400, detail="Invalid or missing chat_id")
    if not message:
        raise HTTPException(status_code=400, detail="Missing message")

    with Session(db_engine) as session:
        messages = session.exec(select(ChatMessage).where(ChatMessage.chat_id == chat_id).order_by(ChatMessage.timestamp)).all()
        history = [{"role": m.role, "content": m.content} for m in messages]
        history.append({"role": "user", "content": message})

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=history,
            )
            reply = response.choices[0].message["content"]

            session.add(ChatMessage(chat_id=chat_id, role="user", content=message))
            session.add(ChatMessage(chat_id=chat_id, role="assistant", content=reply))
            session.commit()

            return {"response": reply}
        except Exception as e:
            traceback.print_exc()
            return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/history/{chat_id}")
def get_history(chat_id: str):
    with Session(db_engine) as session:
        messages = session.exec(select(ChatMessage).where(ChatMessage.chat_id == chat_id).order_by(ChatMessage.timestamp)).all()
        return {"messages": [{"role": m.role, "content": m.content, "timestamp": str(m.timestamp)} for m in messages]}
