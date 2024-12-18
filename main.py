from fastapi import FastAPI, Request, Form, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.functions import current_user

from models import Klient, Czlonkostwo, Placowka, Zajecia, RezerwacjaSprzetu, Sprzet
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
async def dashboard(
        request: Request,
        current_user: Klient = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # Pobierz status członkostwa użytkownika
    czlonkostwo = db.query(Czlonkostwo).filter(Czlonkostwo.id_klienta == current_user.id_klienta).first()
    button_status_reserved_things = False
    if not czlonkostwo:
        membership_status = "Brak aktywnego członkostwa"
    else:
        membership_status = f"{czlonkostwo.typ_czlonkostwa.capitalize()} (ważne do {czlonkostwo.data_zakonczenia})"
        button_status_reserved_things = True

    # Pobierz wszystkie placówki
    placowki = db.query(Placowka).all()

    # Pobierz dostępne zajęcia
    teraz = datetime.now()
    zajecia = db.query(Zajecia).options(joinedload(Zajecia.instruktor)).all()

    # Czy użytkownik jest zapisany na zajęcia
    czyZapisany = db.query(Klient).filter(Klient.id_klienta == current_user.id_klienta).first()
    status_zajec = czyZapisany.id_zajec if czyZapisany else None

    if status_zajec:
        zajecia_pojedyncze = db.query(Zajecia).filter(Zajecia.id_zajec == status_zajec).first()
        zajecia_aktualne = f"Jesteś zapisany na zajęcia {zajecia_pojedyncze.nazwa_zajec}, które odbywają się w dniu {zajecia_pojedyncze.data_i_godzina} w lokalizacji {zajecia_pojedyncze.lokalizacja_w_silowni}"
    else:
        zajecia_aktualne = "Aktualnie nie jesteś przypisany do zajęć"

    # Pobierz bieżącą rezerwację sprzętu
    current_rezerwacja = db.query(RezerwacjaSprzetu).filter(RezerwacjaSprzetu.id_klienta == current_user.id_klienta).first()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user,
        "membership_status": membership_status,
        "placowki": placowki,
        "aktualne_zajecia": zajecia_aktualne,
        "zajecia": zajecia,
        "show_button_sprzet": button_status_reserved_things,
        "current_rezerwacja": current_rezerwacja
    })

@app.get("/rezerwacja_sprzetu", response_class=HTMLResponse)
async def rezerwacja_sprzetu(
        request: Request,
        db: Session = Depends(get_db),
        current_user: Klient = Depends(get_current_user)
):
    # Pobierz wszystkie dostępne sprzęty (stan = "dostepne")
    sprzet_dostepny = db.query(Sprzet).filter(Sprzet.stan == "Działa").all()
    return templates.TemplateResponse("rezerwacja_sprzetu.html", {
        "request": request,
        "sprzet": sprzet_dostepny
    })

@app.post("/rezerwacja_sprzetu", response_class=RedirectResponse)
async def rezerwacja_sprzetu_submit(
        request: Request,
        id_sprzetu: int = Form(...),
        data_i_godzina: str = Form(...),  # Format: YYYY-MM-DD HH:MM
        czas_trwania_rezerwacji: int = Form(...),  # Czas w minutach
        db: Session = Depends(get_db),
        current_user: Klient = Depends(get_current_user)
):
    # Parsowanie daty i godziny
    try:
        data_i_godzina_dt = datetime.strptime(data_i_godzina, "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Nieprawidłowy format daty i godziny.")

    # Oblicz koniec rezerwacji
    end_time = data_i_godzina_dt + timedelta(minutes=czas_trwania_rezerwacji)

    # Utwórz nową rezerwację
    new_rezerwacja = RezerwacjaSprzetu(
        data_i_godzina=data_i_godzina_dt,
        czas_trwania_rezerwacji=czas_trwania_rezerwacji,
        id_klienta=current_user.id_klienta,
        id_sprzetu=id_sprzetu
    )

    try:
        db.add(new_rezerwacja)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Błąd podczas tworzenia rezerwacji.")

    return RedirectResponse(url="/dashboard?success=Sprzęt został zarezerwowany.", status_code=303)

@app.get("/cancel_rezerwacja", response_class=RedirectResponse)
async def cancel_rezerwacja(
        request: Request,
        db: Session = Depends(get_db),
        current_user: Klient = Depends(get_current_user)
):
    # Pobierz bieżącą rezerwację użytkownika
    reservation = db.query(RezerwacjaSprzetu).filter(RezerwacjaSprzetu.id_klienta == current_user.id_klienta).first()

    if reservation:
        db.delete(reservation)
        db.commit()
        return RedirectResponse(url="/dashboard?success=Rezerwacja została anulowana.", status_code=303)
    else:
        return RedirectResponse(url="/dashboard?error=Nie znaleziono rezerwacji.", status_code=303)


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

    # Aktualizuj id_zajec klienta
    current_user.id_zajec = zajecia.id_zajec
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Błąd podczas zapisywania na zajęcia.")

    return RedirectResponse(url="/dashboard?success=Zostałeś zapisany na zajęcia.", status_code=303)

@app.get("/wypisz_sie", response_class=RedirectResponse)
async def wypisz_sie_z_zajec(
        request: Request,
        db: Session = Depends(get_db),
        current_user: Klient = Depends(get_current_user)
):

    # Aktualizuj id_zajec klienta
    current_user.id_zajec = None
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Błąd podczas zapisywania na zajęcia.")

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