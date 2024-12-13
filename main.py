from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import models
from database import engine, SessionLocal
from models import Pass

# Tworzenie tabel w bazie danych
# models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Konfiguracja statycznych plików i szablonów
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Dependency do uzyskania sesji bazy danych
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/buy_pass")

@app.get("/buy_pass", response_class=HTMLResponse)
async def buy_pass_form(request: Request):
    return templates.TemplateResponse("buy_pass.html", {"request": request})

@app.post("/buy_pass", response_class=RedirectResponse)
async def buy_pass(
        request: Request,
        name: str = Form(...),
        email: str = Form(...),
        pass_type: str = Form(...),
        db: Session = Depends(get_db)
):
    new_pass = Pass(name=name, email=email, pass_type=pass_type)
    db.add(new_pass)
    db.commit()
    db.refresh(new_pass)
    return RedirectResponse(url="/success", status_code=303)

@app.get("/success", response_class=HTMLResponse)
async def success(request: Request):
    return templates.TemplateResponse("success.html", {"request": request})
# main.py
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import models
from database import engine, SessionLocal
from models import Pass

# Tworzenie tabel w bazie danych
# models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Konfiguracja statycznych plików i szablonów
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Dependency do uzyskania sesji bazy danych
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/buy_pass")

@app.get("/buy_pass", response_class=HTMLResponse)
async def buy_pass_form(request: Request):
    return templates.TemplateResponse("buy_pass.html", {"request": request})

@app.post("/buy_pass", response_class=RedirectResponse)
async def buy_pass(
        request: Request,
        name: str = Form(...),
        email: str = Form(...),
        pass_type: str = Form(...),
        db: Session = Depends(get_db)
):
    new_pass = Pass(name=name, email=email, pass_type=pass_type)
    db.add(new_pass)
    db.commit()
    db.refresh(new_pass)
    return RedirectResponse(url="/success", status_code=303)

@app.get("/success", response_class=HTMLResponse)
async def success(request: Request):
    return templates.TemplateResponse("success.html", {"request": request})
