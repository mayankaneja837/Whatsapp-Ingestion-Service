import aiosqlite
from sqlite3 import IntegrityError

INSERT_MESSAGE_QUERY = """
INSERT INTO messages (message_id, from_msisdn, to_msisdn, ts, text, created_at)
VALUES (:message_id, :from_msisdn, :to_msisdn, :ts, :text, :created_at);
"""

#Insert message Helper function
async def insert_message(conn:aiosqlite.Connection,msg:dict)->bool:
    try:
        await conn.execute(INSERT_MESSAGE_QUERY,msg)
        await conn.commit()
        return True
    except IntegrityError:
        return False


#Paginated Messages Helper Function
async def fetch_messages(conn,limit,offset,from_filter = None,since=None,q=None):

    conditions = []
    params = {}

    if from_filter:
        conditions.append("from_msisdn = :from_filter")
        params["from_filter"] = from_filter
    
    if since:
        conditions.append("ts >= :since")
        params["since"] = since

    if q:
        conditions.append("LOWER(text) LIKE :q")
        params["q"] = f"%{q.lower()}%"

    where_clause = " "
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

     # Paginated Query
    query = f"""
    SELECT message_id, from_msisdn, to_msisdn, ts, text, created_at
    FROM messages
    {where_clause}
    ORDER BY ts ASC, message_id ASC
    LIMIT :limit OFFSET :offset;
    """

    params["limit"] = limit
    params["offset"] = offset

    cursor = await conn.execute(query,params)
    rows = await cursor.fetchall()

    messages = []
    for row in rows:
        messages.append({
            "message_id":row[0],
            "from":row[1],
            "to":row[2],
            "ts":row[3],
            "text":row[4],
            "created_at":row[5]  
        })

    count_query = f"""
    SELECT COUNT(*) FROM messages
    {where_clause};
    """
    cursor = await conn.execute(count_query, {k: v for k, v in params.items() if k not in ("limit", "offset")})
    total = (await cursor.fetchone())[0]

    return messages, total


#Stats endpoint Helper functions
async def get_stats(conn):
    cursor = await conn.execute("SELECT COUNT(*) FROM messages;")
    total_messages = (await cursor.fetchone())[0]

    cursor = await conn.execute("SELECT COUNT(DISTINCT from_msisdn) FROM messages;")
    senders_count = (await cursor.fetchone())[0]

    cursor = await conn.execute("""
        SELECT from_msisdn, COUNT(*) AS count
        FROM messages
        GROUP BY from_msisdn
        ORDER BY count DESC
        LIMIT 10;
    """)

    rows = await cursor.fetchall()
    messages_per_sender = [
        {"from": row[0], "count": row[1]} for row in rows
    ]

    cursor = await conn.execute("""
        SELECT ts FROM messages ORDER BY ts ASC LIMIT 1;
    """)
    row = await cursor.fetchone()
    first_ts = row[0] if row else None

    cursor = await conn.execute("""
        SELECT ts FROM messages ORDER BY ts DESC LIMIT 1;
    """)
    row = await cursor.fetchone()
    last_ts = row[0] if row else None

    return {
        "total_messages":total_messages,
        "senders_count":senders_count,
        "messages_per_sender":messages_per_sender,
        "first_message_ts":first_ts,
        "last_message_ts":last_ts
    }


   
    