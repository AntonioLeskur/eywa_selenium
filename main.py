from selenium import webdriver
import eywa
import asyncio
import os
from selenium.webdriver.common.by import By
from sqlalchemy import create_engine, Column, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import uuid



#print(dir(eywa))
os.environ['EYWA_ROBOTICS_ENDPOINT'] = "https://www.eywaonline.com/graphql"
#print(os.environ['EYWA_ROBOTICS_ENDPOINT'])

# Definicija modela - samo nužni dijelovi
Base = declarative_base()
class WeatherData(Base):
    __tablename__ = 'weather_data'
    id = Column(String, primary_key=True)
    postaja = Column(String)
    vijetar_smijer = Column(String)
    vijetar_brzina = Column(Float)
    temperatura_zraka = Column(Float)
    relativna_vlaznost = Column(Float)
    tlak_zraka = Column(Float)
    tendencija_tlaka = Column(String)
    stanje_vremena = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Postavke baze
engine = create_engine("postgresql://postgres:postgres@localhost:5432/postgres")
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

# Selenium postavke
chrome_options = webdriver.ChromeOptions()
#chrome_options.add_experimental_option("detach", True)

driver = webdriver.Chrome(options=chrome_options)
driver.get("https://meteo.hr/naslovnica_aktpod.php?tab=aktpod")

# Dohvaćanje podataka
data = []
rows = driver.find_elements(By.XPATH, "//table[@id='table-aktualni-podaci']/tbody/tr")
for row in rows:
    cells = [cell.text.strip() for cell in row.find_elements(By.XPATH, "./td")]
    if len(cells) >= 8:
        data.append(cells)

# Spremanje u bazu
def save_to_db():
    session = SessionLocal()
    try:
        session.query(WeatherData).delete()
        for row in data:
            # Čišćenje podataka od zvjezdica, crtica i ostalih znakova
            def clean_number(value):
                if not value.strip() or value == '-':
                    return None
                return float(value.replace(',', '.').replace('*', ''))

            session.add(WeatherData(
                id=str(uuid.uuid4()),
                postaja=row[0],
                vijetar_smijer=row[1],
                vijetar_brzina=clean_number(row[2]),
                temperatura_zraka=clean_number(row[3]),
                relativna_vlaznost=clean_number(row[4]),
                tlak_zraka=clean_number(row[5]),
                tendencija_tlaka=row[6],
                stanje_vremena=row[7]
            ))
        session.commit()
    except Exception as e:
        print(f"Greška: {e}")
        session.rollback()
    finally:
        session.close()

save_to_db()
driver.quit()

# Ispis podataka iz baze
def print_db_data():
    session = SessionLocal()
    try:
        results = session.query(WeatherData).all()
        print("\nPodaci u bazi:")
        print("-" * 50)
        for row in results:
            print(f"Postaja: {row.postaja}")
            print(f"Vjetar: {row.vijetar_smijer}")
            print(f"Vjetar brzina: {row.vijetar_brzina}")
            print(f"Temperatura: {row.temperatura_zraka}°C")
            print(f"Vlažnost: {row.relativna_vlaznost}%")
            print(f"Tlak: {row.tlak_zraka} hPa")
            print(f"Tendencija tlaka: {row.tendencija_tlaka}")
            print(f"Stanje vremena: {row.stanje_vremena}")
            print("-" * 50)
    finally:
        session.close()

# Prvo napravimo jednostavan query test da vidimo radi li povezivanje
query_test = """
query {
  searchProject {
    name
    description
  }
}
"""

async def test_connection():
    try:
        print("Testiram povezivanje s GraphQL serverom...")
        response = await eywa.graphql({
            'query': query_test
        })
        print(f"Test odgovor: {response}")
        return response
    except Exception as e:
        print(f"Greška pri testiranju: {str(e)}")
        print(f"Tip greške: {type(e)}")
        raise

# Potpuna mutacija za vremenske podatke
mutation = """
mutation ($weatherData: [WeatherDataInput!]!) {
    stackWeatherData(data: $weatherData) {
        euuid
        postaja
        vijetar_smijer
        vijetar_brzina
        temperatura_zraka
        relativna_vlaznost
        tlak_zraka
        tendencija_tlaka
        stanje_vremena
        timestamp
    }
}
"""

async def send_data_to_server(data):
    try:
        print("Priprema podataka za slanje...")
        
        # Pretvaranje podataka u format koji očekuje DatasetInput
        dataset_input = {
            "dataset": {
                "name": "weather_data",
                "description": "Meteorološki podaci s meteo.hr",
                "data": [
                    {
                        "postaja": row[0],
                        "vijetar_smijer": row[1],
                        "vijetar_brzina": row[2],
                        "temperatura_zraka": row[3],
                        "relativna_vlaznost": row[4],
                        "tlak_zraka": row[5],
                        "tendencija_tlaka": row[6],
                        "stanje_vremena": row[7]
                    } for row in data
                ]
            }
        }

        print("Šaljem podatke...")
        print(f"Mutation: {mutation}")
        print(f"Podaci: {dataset_input}")
        
        # Pozivanje GraphQL mutation-a
        response = await eywa.graphql({
            'query': mutation,
            'variables': dataset_input
        })

        print(f"Odgovor servera: {response}")
        return response
        
    except Exception as e:
        print(f"Greška pri slanju: {str(e)}")
        print(f"Tip greške: {type(e)}")
        raise

# Pokrenite asinkronu funkciju

asyncio.run(send_data_to_server(data))

#print(data)
#print_db_data()

