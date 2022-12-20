from fastapi import FastAPI, status
from pydantic import BaseModel

app = FastAPI()


class Payload(BaseModel):
    name: str


@app.post("/", status_code=status.HTTP_202_ACCEPTED)
async def main(payload: Payload):
    return "Hello {}!".format(payload.name)
