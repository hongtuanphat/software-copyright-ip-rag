from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from contextlib import asynccontextmanager

from pipeline import get_pipeline

ml_models = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load model 1 lần duy nhất khi worker thực sự khởi động
    ml_models["pipeline"] = get_pipeline()
    yield
    ml_models.clear()

app = FastAPI(
    title="IP RAG API",
    description="API cho hệ thống hỏi đáp bản quyền phần mềm",
    version="1.0.0",
    lifespan=lifespan
)

class ChatRequest(BaseModel):
    prompt: str

class Citation(BaseModel):
    citation_index: int
    law_code: str
    article_no: str
    clause_no: str
    status: str
    text: str
    law_name: str
    title: str

class Alert(BaseModel):
    message: str

class ChatResponse(BaseModel):
    answer: str
    cited_documents: List[dict]
    active_alerts: List[dict]

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    try:
        pipeline = ml_models.get("pipeline")
        if not pipeline:
            raise HTTPException(status_code=503, detail="Model is still loading")
            
        res = pipeline.query(request.prompt)
        return res.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Tắt reload=True để tránh việc Uvicorn spawn nhiều process phụ sinh ra nạp model nhiều lần
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=False)
