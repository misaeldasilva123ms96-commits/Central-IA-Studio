"""Inicie com: python run.py"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("studio.app:app", host="127.0.0.1", port=8765, log_level="info")
