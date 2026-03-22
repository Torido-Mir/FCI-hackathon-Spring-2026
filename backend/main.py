from fastapi import FastAPI

app = FastAPI()

# boilerplate

@app.get("/")
async def root():
    return {"message": "Hello World"}
