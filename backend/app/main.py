from fastapi import FastAPI

app = FastAPI(
    title="Personal KB",
    version="1.1.0",
    description="Historical project document knowledge base. Source code analysis is out of scope.",
)

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.1.0"}
