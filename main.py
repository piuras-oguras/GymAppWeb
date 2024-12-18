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
async def index(request: Request):
    return templates.TemplateResponse("raports.html", {"request": request})

@app.get("/raport/raport-czlonkostw", response_class=HTMLResponse)
def raport_czlonkostw(

):
#     data_poczatkowa: datetime = Query(..., description="Data początkowa w formacie YYYY-MM-DD"),
# data_zakonczenia: datetime = Query(..., description="Data zakończenia w formacie YYYY-MM-DD"),
#     """
#     Endpoint do przekierowywania do raportu członkostw.
#     """
#     # Konwersja dat do formatu YYYY-MM-DD
#     data_poczatkowa_str = data_poczatkowa.strftime('%Y-%m-%d')
#     data_zakonczenia_str = data_zakonczenia.strftime('%Y-%m-%d')
#
#     # Sprawdzenie logicznej poprawności dat
#     if data_poczatkowa > data_zakonczenia:
#         raise HTTPException(status_code=400, detail="Data początkowa nie może być późniejsza niż data zakończenia.")
#
#     # Ścieżka do raportu w SSRS
#     report_path = "/Reports/RaportCzlonkostw"
#
#     # Parametry raportu
#     params = {
#         "Data_poczatkowa": data_poczatkowa_str,
#         "Data_koncowa": data_zakonczenia_str,
#     }

    # Budowanie URL raportu
    ssrs_url = f"http://asus-x15-szymon/Reports/report/czlonkostwo?Data_poczatkowa=2023-01-01&Data_koncowa=2023-12-31"

    return RedirectResponse(url=ssrs_url)

# @app.get("/statystyki-zajec", response_class=HTMLResponse)
# def statystyki_zajec(
#         data_od: datetime = Query(..., description="Początek zakresu dat (YYYY-MM-DD)"),
#         data_do: datetime = Query(..., description="Koniec zakresu dat (YYYY-MM-DD)")
# ):
#     """
#     Endpoint do wyświetlania raportu statystyk zajęć z wykresem w przeglądarce.
#
#     - data_od: Początek zakresu dat (YYYY-MM-DD)
#     - data_do: Koniec zakresu dat (YYYY-MM-DD)
#     """
#     report_path = "/Reports/StatystykiZajec"  # Dostosuj do rzeczywistej ścieżki raportu
#     parameters = {
#         'Data_od': data_od.strftime('%Y-%m-%d'),
#         'Data_do': data_do.strftime('%Y-%m-%d')
#     }
#
#     try:
#         report_content = ssrs_client.get_report(report_path, format='HTML4.0', parameters=parameters)
#         report_html = report_content.decode('utf-8')
#         return HTMLResponse(content=report_html)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Błąd podczas generowania raportu: {str(e)}")
#
# @app.get("/formularz-klienta", response_class=HTMLResponse)
# def formularz_klienta(
#         id_klienta: int = Query(..., description="ID klienta"),
#         data_od_platnosci: datetime = Query(None, description="Początek zakresu dat płatności (YYYY-MM-DD)"),
#         data_do_platnosci: datetime = Query(None, description="Koniec zakresu dat płatności (YYYY-MM-DD)")
# ):
#     """
#     Endpoint do wyświetlania formularza klienta w przeglądarce.
#
#     - id_klienta: ID klienta
#     - data_od_platnosci: Początek zakresu dat płatności (YYYY-MM-DD)
#     - data_do_platnosci: Koniec zakresu dat płatności (YYYY-MM-DD)
#     """
#     report_path = "/Reports/FormularzKlienta"  # Dostosuj do rzeczywistej ścieżki raportu
#     parameters = {
#         'Id_klienta': id_klienta
#     }
#     if data_od_platnosci and data_do_platnosci:
#         parameters['Data_od_platnosci'] = data_od_platnosci.strftime('%Y-%m-%d')
#         parameters['Data_do_platnosci'] = data_do_platnosci.strftime('%Y-%m-%d')
#
#     try:
#         report_content = ssrs_client.get_report(report_path, format='HTML4.0', parameters=parameters)
#         report_html = report_content.decode('utf-8')
#         return HTMLResponse(content=report_html)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Błąd podczas generowania raportu: {str(e)}")
#
# @app.get("/raport-czlonkostw/download")
# def raport_czlonkostw_download(
#         data_poczatkowa: datetime = Query(..., description="Data początkowa w formacie YYYY-MM-DD"),
#         data_zakonczenia: datetime = Query(..., description="Data zakończenia w formacie YYYY-MM-DD"),
#         typ_czlonkostwa: str = Query('Wszystkie', description="Typ członkostwa, np. 'Standard', 'Premium', 'VIP'"),
#         format: str = Query('PDF', description="Format raportu, np. 'PDF', 'EXCEL'")
# ):
#     """
#     Endpoint do pobierania raportu członkostw jako plik.
#
#     - data_poczatkowa: Data początkowa (YYYY-MM-DD)
#     - data_zakonczenia: Data zakończenia (YYYY-MM-DD)
#     - typ_czlonkostwa: Typ członkostwa
#     - format: Format raportu
#     """
#     report_path = "/Reports/RaportCzlonkostw"  # Dostosuj do rzeczywistej ścieżki raportu
#     parameters = {
#         'Data_początkowa': data_poczatkowa.strftime('%Y-%m-%d'),
#         'Data_zakonczenia': data_zakonczenia.strftime('%Y-%m-%d'),
#         'Typ_członkostwa': typ_czlonkostwa
#     }
#
#     try:
#         report_content = ssrs_client.get_report(report_path, format=format, parameters=parameters)
#         filename = f"RaportCzlonkostw.{format.lower()}"
#         return StreamingResponse(
#             iter([report_content]),
#             media_type=f'application/{format.lower()}',
#             headers={'Content-Disposition': f'attachment; filename="{filename}"'}
#         )
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Błąd podczas pobierania raportu: {str(e)}")