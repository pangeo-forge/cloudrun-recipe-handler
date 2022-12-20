from fastapi import FastAPI, Request, status

app = FastAPI()

@app.post("/", status_code=status.HTTP_202_ACCEPTED)
async def hello_world(request: Request):
    payload = await request.json()
    name = payload["name"]
    return "Hello {}!".format(name)
