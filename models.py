from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Float, Text
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Klient(Base):
    __tablename__ = "klienci"

    id_klienta = Column(Integer, primary_key=True, index=True)
    imie = Column(String, index=True, nullable=False)
    nazwisko = Column(String, index=True, nullable=False)
    data_urodzenia = Column(Date, nullable=False)
    data_rejestracji = Column(DateTime, default=datetime.utcnow)
    numer_telefonu = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)

    czlonkostwa = relationship("Czlonkostwo", back_populates="klient")
    rezerwacje_sprzetu = relationship("RezerwacjaSprzetu", back_populates="klient")
    platnosci = relationship("Platnosc", back_populates="klient")
    anulowania_czlonkostwa = relationship("AnulowanieCzlonkostwa", back_populates="klient")
    oceny_instruktorow = relationship("OcenaInstruktorow", back_populates="klient")


class Placowka(Base):
    __tablename__ = "placowki"

    id_placowki = Column(Integer, primary_key=True, index=True)
    nazwa = Column(String, nullable=False)
    adres = Column(String, nullable=False)
    godziny_otwarcia = Column(String, nullable=False)
    numer_telefonu = Column(String, nullable=False)

    pracownicy = relationship("Pracownik", back_populates="placowka")


class Pracownik(Base):
    __tablename__ = "pracownicy"

    id_pracownika = Column(Integer, primary_key=True, index=True)
    imie = Column(String, index=True, nullable=False)
    nazwisko = Column(String, index=True, nullable=False)
    adres = Column(String, nullable=False)
    data_urodzenia = Column(Date, nullable=False)
    data_zatrudnienia = Column(DateTime, nullable=False)
    data_zakonczenia_zatrudnienia = Column(DateTime, nullable=True)
    stawka_godzinowa = Column(Float, nullable=False)
    email = Column(String, unique=True, nullable=False)
    numer_telefonu = Column(String, nullable=False)
    status = Column(String, nullable=False)
    id_placowki = Column(Integer, ForeignKey("placowki.id_placowki"), nullable=False)

    placowka = relationship("Placowka", back_populates="pracownicy")
    instruktor = relationship("Instruktor", uselist=False, back_populates="pracownik")
    biurowy = relationship("Biurowy", uselist=False, back_populates="pracownik")
    grafik_pracy = relationship("GrafikPracownikow", back_populates="pracownik")
    # Usunięto niepotrzebną relację zajecia = relationship("Zajecia", back_populates="instruktor")


class Instruktor(Base):
    __tablename__ = "instruktorzy"

    id_pracownika = Column(Integer, ForeignKey("pracownicy.id_pracownika"), primary_key=True)
    specjalizacja = Column(String, nullable=False)
    certyfikaty = Column(Text, nullable=True)

    pracownik = relationship("Pracownik", back_populates="instruktor")
    zajecia = relationship("Zajecia", back_populates="instruktor")
    oceny_instruktorow = relationship("OcenaInstruktorow", back_populates="instruktor")


class Biurowy(Base):
    __tablename__ = "biurowy"

    id_pracownika = Column(Integer, ForeignKey("pracownicy.id_pracownika"), primary_key=True)
    dzial = Column(String, nullable=False)
    szkolenia = Column(Text, nullable=True)

    pracownik = relationship("Pracownik", back_populates="biurowy")


class Czlonkostwo(Base):
    __tablename__ = "czlonkostwa"

    id_czlonkostwa = Column(Integer, primary_key=True, index=True)
    id_klienta = Column(Integer, ForeignKey("klienci.id_klienta"), nullable=False)
    typ_czlonkostwa = Column(String, nullable=False)
    data_rozpoczecia = Column(Date, default=datetime.utcnow)
    data_zakonczenia = Column(Date, nullable=False)
    status = Column(String, default="active", nullable=False)

    klient = relationship("Klient", back_populates="czlonkostwa")
    platnosci = relationship("Platnosc", back_populates="czlonkostwo")


class Zajecia(Base):
    __tablename__ = "zajecia"

    id_zajec = Column(Integer, primary_key=True, index=True)
    nazwa_zajec = Column(String, nullable=False)
    data_i_godzina = Column(DateTime, nullable=False)
    maksymalna_ilosc_uczestnikow = Column(Integer, nullable=False)
    lokalizacja_w_silowni = Column(String, nullable=False)
    id_instruktora = Column(Integer, ForeignKey("instruktorzy.id_pracownika"), nullable=False)

    instruktor = relationship("Instruktor", back_populates="zajecia")


class Sprzet(Base):
    __tablename__ = "sprzet"

    id_sprzetu = Column(Integer, primary_key=True, index=True)
    nazwa = Column(String, nullable=False)
    typ = Column(String, nullable=False)
    stan = Column(String, nullable=False)
    data_zakupu = Column(Date, nullable=False)
    lokalizacja_w_silowni = Column(String, nullable=False)

    rezerwacje = relationship("RezerwacjaSprzetu", back_populates="sprzet")


class RezerwacjaSprzetu(Base):
    __tablename__ = "rezerwacja_sprzetu"

    id_rezerwacji = Column(Integer, primary_key=True, index=True)
    data_i_godzina = Column(DateTime, nullable=False)
    czas_trwania_rezerwacji = Column(Integer, nullable=False)  # Czas w minutach lub godzinach
    id_klienta = Column(Integer, ForeignKey("klienci.id_klienta"), nullable=False)
    id_sprzetu = Column(Integer, ForeignKey("sprzet.id_sprzetu"), nullable=False)

    klient = relationship("Klient", back_populates="rezerwacje_sprzetu")
    sprzet = relationship("Sprzet", back_populates="rezerwacje")


class Platnosc(Base):
    __tablename__ = "platnosc"

    id_platnosci = Column(Integer, primary_key=True, index=True)
    data_platnosci = Column(DateTime, nullable=False, default=datetime.utcnow)
    kwota = Column(Float, nullable=False)
    metoda_platnosci = Column(String, nullable=False)
    id_klienta = Column(Integer, ForeignKey("klienci.id_klienta"), nullable=False)
    id_czlonkostwa = Column(Integer, ForeignKey("czlonkostwa.id_czlonkostwa"), nullable=False)

    klient = relationship("Klient", back_populates="platnosci")
    czlonkostwo = relationship("Czlonkostwo", back_populates="platnosci")


class Wydarzenia(Base):
    __tablename__ = "wydarzenia"

    id_wydarzenia = Column(Integer, primary_key=True, index=True)
    nazwa = Column(String, nullable=False)
    opis = Column(Text, nullable=False)
    data = Column(DateTime, nullable=False)
    liczba_uczestnikow = Column(Integer, nullable=False)
    lokalizacja_w_silowni = Column(String, nullable=False)


class AnulowanieCzlonkostwa(Base):
    __tablename__ = "anulowanie_czlonkostwa"

    id_anulowania = Column(Integer, primary_key=True, index=True)
    powod_zamkniecia = Column(String, nullable=False)
    id_klienta = Column(Integer, ForeignKey("klienci.id_klienta"), nullable=False)

    klient = relationship("Klient", back_populates="anulowania_czlonkostwa")


class OcenaInstruktorow(Base):
    __tablename__ = "ocena_instruktorow"

    id_oceny = Column(Integer, primary_key=True, index=True)
    data_oceny = Column(DateTime, nullable=False, default=datetime.utcnow)
    ocena = Column(Integer, nullable=False)  # Zakładam ocenę jako liczbę całkowitą
    komentarz = Column(Text, nullable=True)
    id_klienta = Column(Integer, ForeignKey("klienci.id_klienta"), nullable=False)
    id_instruktora = Column(Integer, ForeignKey("instruktorzy.id_pracownika"), nullable=False)

    klient = relationship("Klient", back_populates="oceny_instruktorow")
    instruktor = relationship("Instruktor", back_populates="oceny_instruktorow")


class GrafikPracownikow(Base):
    __tablename__ = "grafik_pracownikow"

    id_grafiku = Column(Integer, primary_key=True, index=True)
    data = Column(Date, nullable=False)
    godzina_rozpoczecia = Column(DateTime, nullable=False)
    godzina_zakonczenia = Column(DateTime, nullable=False)
    id_pracownika = Column(Integer, ForeignKey("pracownicy.id_pracownika"), nullable=False)

    pracownik = relationship("Pracownik", back_populates="grafik_pracy")
