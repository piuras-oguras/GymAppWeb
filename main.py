from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models import Klient, Czlonkostwo
from database import engine, SessionLocal
from datetime import datetime, timedelta
import models

# Tworzenie tabel w bazie danych
models.Base.metadata.create_all(bind=engine)

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
        imie: str = Form(...),
        nazwisko: str = Form(...),
        data_urodzenia: str = Form(...),  # Oczekuje formatu YYYY-MM-DD
        numer_telefonu: str = Form(...),
        email: str = Form(...),
        typ_czlonkostwa: str = Form(...),
        db: Session = Depends(get_db)
):
    # Przetwarzanie dat
    try:
        data_urodzenia_date = datetime.strptime(data_urodzenia, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Nieprawidłowy format daty urodzenia.")

    # Obliczanie dat zakończenia na podstawie typu członkostwa
    dzisiaj = datetime.utcnow().date()
    if typ_czlonkostwa == "miesieczne":
        data_zakonczenia = dzisiaj + timedelta(days=30)
    elif typ_czlonkostwa == "roczne":
        data_zakonczenia = dzisiaj + timedelta(days=365)
    else:
        raise HTTPException(status_code=400, detail="Nieprawidłowy typ członkostwa.")

    # Tworzenie nowego klienta
    nowy_klient = Klient(
        imie=imie,
        nazwisko=nazwisko,
        data_urodzenia=data_urodzenia_date,
        numer_telefonu=numer_telefonu,
        email=email
    )

    try:
        db.add(nowy_klient)
        db.commit()
        db.refresh(nowy_klient)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Klient z podanym emailem już istnieje.")

    # Tworzenie nowego członkostwa
    nowe_czlonkostwo = Czlonkostwo(
        id_klienta=nowy_klient.id_klienta,
        typ_czlonkostwa=typ_czlonkostwa,
        data_rozpoczecia=dzisiaj,
        data_zakonczenia=data_zakonczenia,
        status="Aktywnu"
    )

    db.add(nowe_czlonkostwo)
    db.commit()
    db.refresh(nowe_czlonkostwo)

    return RedirectResponse(url="/success", status_code=303)

@app.get("/success", response_class=HTMLResponse)
async def success(request: Request):
    return templates.TemplateResponse("success.html", {"request": request})
