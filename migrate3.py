import sqlite3

DATABASE = "garderoba.db"
conn = sqlite3.connect(DATABASE)

try:
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("""
        CREATE TABLE furniture_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT,
            type TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.execute("""
        INSERT INTO furniture_new (id, user_id, name, type, created_at)
        SELECT id, user_id, name, type, created_at FROM furniture
    """)
    conn.execute("DROP TABLE furniture")
    conn.execute("ALTER TABLE furniture_new RENAME TO furniture")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()
    print("Migracja 3: tabela furniture przebudowana, name jest teraz opcjonalne.")
except Exception as e:
    print("Błąd:", e)
finally:
    conn.close()

