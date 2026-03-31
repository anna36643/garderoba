import secrets
import sqlite3

DATABASE = "garderoba.db"

code = secrets.token_urlsafe(16)

conn = sqlite3.connect(DATABASE)
conn.execute("INSERT INTO invite_codes (code) VALUES (?)", (code,))
conn.commit()
conn.close()

print(f"Kod zaproszenia: {code}")
'''

---

Teraz uruchom serwer i wygeneruj pierwszy kod zaproszenia. W terminalu wpisz:
```
python generate_invite.py
```

Terminal wypisze coś w stylu `Kod zaproszenia: abc123xyz`. Skopiuj ten kod, będzie potrzebny za chwilę. Potem uruchom serwer:
```
python app.py
'''