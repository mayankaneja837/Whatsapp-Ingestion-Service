from multiprocessing import Value
import aiosqlite

CREATE_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    from_msisdn TEXT NOT NULL,
    to_msisdn TEXT NOT NULL,
    ts TEXT NOT NULL,
    text TEXT,
    created_at TEXT NOT NULL
);
"""

async def init_db(db_url:str):
    if not db_url.startswith("sqlite:///"):
        return ValueError("DATABASE_URL must start with sqlite:///")
    
    db_path = db_url.replace("sqlite:///","")

    conn = await aiosqlite.connect(db_path)
    await conn.execute(CREATE_MESSAGES_TABLE)
    await conn.commit()

    return conn