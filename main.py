from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models import Klient, Czlonkostwo
from database import engine, SessionLocal
from datetime import datetime, timedelta
from starlette.middleware.sessions import SessionMiddleware  # Ensure this import is correct
from typing import Optional

import models

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Add SessionMiddleware with a secret key
app.add_middleware(SessionMiddleware, secret_key="your-very-secure-secret-key")  # Replace with a secure key

# Configure static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/index")

@app.get("/index", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/login", response_class=RedirectResponse)
async def check_login(
        request: Request,
        numer_telefonu: str = Form(...),
        email: str = Form(...),
        db: Session = Depends(get_db)
):
    # Query the database for a client with the provided phone number and email
    klient: Optional[Klient] = db.query(Klient).filter(
        Klient.numer_telefonu == numer_telefonu,
        Klient.email == email
    ).first()

    if klient:
        # If client exists, store their ID in the session
        request.session['user_id'] = klient.id_klienta
        return RedirectResponse(url="/dashboard", status_code=303)
    else:
        # If authentication fails, redirect back to login with an error
        return RedirectResponse(url="/index?error=Invalid credentials", status_code=303)

def get_current_user(request: Request, db: Session = Depends(get_db)) -> Klient:
    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    klient = db.query(Klient).filter(Klient.id_klienta == user_id).first()
    if not klient:
        raise HTTPException(status_code=401, detail="User not found")

    return klient

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, current_user: Klient = Depends(get_current_user)):
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": current_user})

@app.get("/buy_pass", response_class=HTMLResponse)
async def buy_pass_form(request: Request):
    return templates.TemplateResponse("buy_pass.html", {"request": request})

@app.post("/buy_pass", response_class=RedirectResponse)
async def buy_pass(
        request: Request,
        imie: str = Form(...),
        nazwisko: str = Form(...),
        data_urodzenia: str = Form(...),  # Expecting format YYYY-MM-DD
        numer_telefonu: str = Form(...),
        email: str = Form(...),
        typ_czlonkostwa: str = Form(...),
        db: Session = Depends(get_db)
):
    # Process dates
    try:
        data_urodzenia_date = datetime.strptime(data_urodzenia, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format for birth date.")

    # Calculate end date based on membership type
    today = datetime.utcnow().date()
    if typ_czlonkostwa == "miesieczne":
        data_zakonczenia = today + timedelta(days=30)
    elif typ_czlonkostwa == "roczne":
        data_zakonczenia = today + timedelta(days=365)
    else:
        raise HTTPException(status_code=400, detail="Invalid membership type.")

    # Create a new client
    new_client = Klient(
        imie=imie,
        nazwisko=nazwisko,
        data_urodzenia=data_urodzenia_date,
        numer_telefonu=numer_telefonu,
        email=email
    )

    try:
        db.add(new_client)
        db.commit()
        db.refresh(new_client)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="A client with this email already exists.")

    # Create a new membership
    new_membership = Czlonkostwo(
        id_klienta=new_client.id_klienta,
        typ_czlonkostwa=typ_czlonkostwa,
        data_rozpoczecia=today,
        data_zakonczenia=data_zakonczenia,
        status="Aktywnu"
    )

    db.add(new_membership)
    db.commit()
    db.refresh(new_membership)

    return RedirectResponse(url="/success", status_code=303)

@app.get("/success", response_class=HTMLResponse)
async def success(request: Request):
    return templates.TemplateResponse("success.html", {"request": request})

@app.get("/logout", response_class=RedirectResponse)
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/index", status_code=303)
