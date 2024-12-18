from fastapi import FastAPI, Request, Form, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models import Klient, Czlonkostwo, Placowka, Zajecia
from database import engine, SessionLocal
from datetime import datetime, timedelta
from starlette.middleware.sessions import SessionMiddleware  # Ensure this import is correct
from typing import Optional
from sqlalchemy.orm import joinedload
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
async def dashboard(request: Request, current_user: Klient = Depends(get_current_user), db: Session = Depends(get_db)):
    # Pobierz status członkostwa użytkownika
    czlonkostwo = db.query(Czlonkostwo).filter(Czlonkostwo.id_klienta == current_user.id_klienta).first()

    if not czlonkostwo:
        membership_status = "Brak aktywnego członkostwa"
    else:
        membership_status = f"{czlonkostwo.typ_czlonkostwa.capitalize()} (ważne do {czlonkostwo.data_zakonczenia})"

    # Pobierz wszystkie placówki
    placowki = db.query(Placowka).all()

    # Pobierz dostępne zajęcia (np. te, które są jeszcze nie rozpoczęte)
    teraz = datetime.utcnow()
    zajecia = db.query(Zajecia).filter(Zajecia.data_i_godzina > teraz).options(joinedload(Zajecia.instruktor)).all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user,
        "membership_status": membership_status,
        "placowki": placowki,
        "zajecia": zajecia
    })

@app.post("/zapisz_sie_na_zajecia", response_class=RedirectResponse)
async def zapisz_sie_na_zajecia(
        request: Request,
        id_zajec: int = Form(...),
        db: Session = Depends(get_db),
        current_user: Klient = Depends(get_current_user)
):
    # Sprawdź, czy zajęcia istnieją
    zajecia = db.query(Zajecia).filter(Zajecia.id_zajec == id_zajec).first()
    if not zajecia:
        raise HTTPException(status_code=404, detail="Zajęcia nie zostały znalezione.")

    # Możesz dodać logikę rezerwacji lub inny sposób zapisania użytkownika na zajęcia
    # Ponieważ nie mamy tabeli rezerwacji zajęć, możemy np. dodać komentarz lub inną metodę
    # W tym przykładzie dodamy informację do komentarzy (zakładając, że taka opcja istnieje)

    # Przykład: Dodanie wydarzenia do listy uczestnictwa (jeśli istnieje taka relacja)
    # Jeśli nie ma takiej tabeli, można pominąć lub dostosować do istniejących modeli

    # Przekierowanie na dashboard z komunikatem sukcesu
    return RedirectResponse(url="/dashboard?success=Zostałeś zapisany na zajęcia.", status_code=303)


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

@app.get("/raport", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    klienci=db.query(Klient).all()
    return templates.TemplateResponse("raports.html", {"request": request,"klienci": klienci})

@app.post("/raport/raport-czlonkostw", response_class=HTMLResponse)
def raport_czlonkostw(request: Request, data_poczatkowa: str = Form(...), data_koncowa: str = Form(...)):
    # Budowanie URL raportu
    base_url = f"http://asus-x15-szymon/Reports/report/czlonkostwo"
    link = f"{base_url}?Data_poczatkowa={data_poczatkowa}&Data_koncowa={data_koncowa}"
    return RedirectResponse(url=link)


@app.post("/raport/raport-platnosci", response_class=HTMLResponse)
def raport_platnosci(request: Request, data_od: str = Form(...), data_do: str = Form(...)):
    # Budowanie URL raportu
    base_url = f"http://asus-x15-szymon/Reports/report/statystyki%20platnosci"
    link = f"{base_url}?Data_od={data_od}&Data_do={data_do}"
    return RedirectResponse(url=link)

@app.post("/raport/formularz-klienta", response_class=HTMLResponse)
def raport_klienta(request: Request,klient_id: int = Form(...), data_platnosci_od: str = Form(...), data_platnosci_do: str = Form(...)):
    # Budowanie URL raportu
    base_url = f"http://asus-x15-szymon/Reports/report/formularz"





    link = f"{base_url}?Id_klienta_par={klient_id}&Data_platnosci_od={data_platnosci_od}&Data_platnosci_do={data_platnosci_do}"

    return RedirectResponse(url=link)