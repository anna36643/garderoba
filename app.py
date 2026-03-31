import os
from flask import Flask
from dotenv import load_dotenv
from database import init_db

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

init_db()


@app.route("/")
def index():
    return "działa"


if __name__ == "__main__":
    app.run(debug=True)
'''


---

Piąty plik: `.env`. Utwórz go w głównym folderze i wklej:
```
SECRET_KEY=zmien-to-na-dlugi-losowy-ciag-znakow
GEMINI_API_KEY=twoj-klucz-api-wklej-tutaj
```

---

Teraz instrukcja uruchomienia. W terminalu PyCharma wpisuj komendy jedna po drugiej, czekając aż każda się wykona:
```
pip install -r requirements.txt
```

Poczekaj aż się zainstaluje, może to chwilę potrwać. Kiedy wróci prompt, uruchom aplikację:
```
python app.py
```

Powinieneś zobaczyć coś w stylu `Running on http://127.0.0.1:5000`. Otwórz przeglądarkę i wejdź na:
```
http://127.0.0.1:5000
'''