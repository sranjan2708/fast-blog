from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from database import get_connection

app = FastAPI()

templates = Jinja2Templates(directory="templates")


@app.get("/")
def home(request: Request):

    username = "Sudhansu"

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "username": username
        }
    )


