from fastapi import FastAPI
import redis

app = FastAPI(title="IoT Platform Test", version="1.0.0")

# Test Redis connection
try:
    r = redis.Redis(host='localhost', port=6380, decode_responses=True)
    r.ping()
    REDIS_STATUS = "Connected"
except:
    REDIS_STATUS = "Failed to connect"

@app.get("/")
async def root():
    return {
        "status": "IoT Platform Device Registry Test",
        "redis": REDIS_STATUS
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)