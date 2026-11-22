"""WebApp API (task3): serves the website and a small guestbook stored in MySQL.

Reads go to the MySQL *read* service, writes go to the MySQL *write* service.
All settings come from environment variables, so the same image runs anywhere:
  - app settings (title, environment, MySQL addresses) -> ConfigMap
  - MySQL user and password                           -> Secret
"""
import os
import socket
from pathlib import Path

import pymysql
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

APP_VERSION = os.getenv("APP_VERSION", "task3")
APP_TITLE = os.getenv("APP_TITLE", "WebApp")
APP_ENV = os.getenv("APP_ENV", "local")

DB_NAME = os.getenv("MYSQL_DATABASE", "webapp")
DB_USER = os.getenv("MYSQL_USER", "webapp")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD", "webapp123")
DB_PORT = int(os.getenv("MYSQL_PORT", "3306"))
WRITE_HOST = os.getenv("MYSQL_WRITE_HOST", "localhost")
READ_HOST = os.getenv("MYSQL_READ_HOST", WRITE_HOST)

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="WebApp API", version=APP_VERSION)


class MessageIn(BaseModel):
    author: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1, max_length=255)


def connect(host: str) -> pymysql.connections.Connection:
    """Open a new connection to the given MySQL host."""
    return pymysql.connect(
        host=host,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        connect_timeout=3,
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


@app.get("/health")
def health():
    """Liveness/readiness check. Does not touch the database."""
    return {"status": "ok"}


@app.get("/api/info")
def info():
    """Which Pod answered, its configuration, and which MySQL servers it reaches."""
    result = {
        "pod": socket.gethostname(),
        "version": APP_VERSION,
        "title": APP_TITLE,
        "environment": APP_ENV,
        "write_host": WRITE_HOST,
        "read_host": READ_HOST,
    }
    for key, host in (("write_db", WRITE_HOST), ("read_db", READ_HOST)):
        try:
            with connect(host) as conn, conn.cursor() as cur:
                cur.execute("SELECT @@hostname AS server, @@read_only AS read_only")
                result[key] = cur.fetchone()
        except pymysql.MySQLError as err:
            result[key] = {"error": str(err)}
    return result


@app.get("/api/messages")
def list_messages(limit: int = Query(20, ge=1, le=100)):
    """Read the latest messages from the READ database."""
    try:
        with connect(READ_HOST) as conn, conn.cursor() as cur:
            cur.execute("SELECT @@hostname AS server")
            server = cur.fetchone()["server"]
            cur.execute(
                "SELECT id, author, content, created_at FROM messages ORDER BY id DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
    except pymysql.MySQLError as err:
        raise HTTPException(status_code=503, detail=f"read database unavailable: {err}")
    return {"served_by": server, "messages": rows}


@app.post("/api/messages", status_code=201)
def create_message(message: MessageIn):
    """Write a new message to the WRITE database."""
    try:
        with connect(WRITE_HOST) as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (author, content) VALUES (%s, %s)",
                (message.author, message.content),
            )
            new_id = cur.lastrowid
            cur.execute("SELECT @@hostname AS server")
            server = cur.fetchone()["server"]
    except pymysql.MySQLError as err:
        raise HTTPException(status_code=503, detail=f"write database unavailable: {err}")
    return {"id": new_id, "written_to": server}


# The website (index.html + style.css). Mounted last, so the API routes above win.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="website")
