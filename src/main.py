import os

from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def hello_world():
    name = os.environ.get("NAME", "World")
    return "Hello {}!".format(name)
