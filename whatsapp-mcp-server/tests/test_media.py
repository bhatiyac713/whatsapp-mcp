"""get_media: path checks, size cap, content types. Uses a temp DB and a fake bridge; no real media."""
import asyncio
import os
import sqlite3
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32
PDF = b"%PDF-1.4\n" + b"x" * 32


@pytest.fixture
def env(tmp_path, monkeypatch):
    db = tmp_path / "messages.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE messages (id TEXT, chat_jid TEXT, media_type TEXT, filename TEXT, file_length INTEGER)")
    conn.commit()
    conn.close()
    monkeypatch.setenv("WHATSAPP_MESSAGES_DB", str(db))
    monkeypatch.setenv("WHATSAPP_STORE_DIR", str(tmp_path))
    for mod in ("whatsapp", "main"):
        sys.modules.pop(mod, None)
    import whatsapp
    files = {}

    def add(mid, media_type, filename, data, size=None, path=None):
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO messages VALUES (?, 'c@s.whatsapp.net', ?, ?, ?)",
                     (mid, media_type, filename, len(data) if size is None else size))
        conn.commit()
        conn.close()
        files[mid] = (path or str(tmp_path / "c@s.whatsapp.net" / filename), data)

    def fake_download(mid, chat):
        path, data = files[mid]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

    monkeypatch.setattr(whatsapp, "download_media", fake_download)
    return whatsapp, add, files, tmp_path


def test_image_returned_and_deleted(env):
    wa, add, files, _ = env
    add("m1", "image", "image_1.jpg", PNG)
    r = wa.fetch_media("m1", "c@s.whatsapp.net")
    assert r["ok"] and r["mime"] == "image/png" and r["data"] == PNG
    assert not os.path.exists(files["m1"][0])


def test_pdf_and_text(env):
    wa, add, _, _ = env
    add("p", "document", "report.pdf", PDF)
    add("t", "document", "notes.csv", b"a,b\n1,2\n")
    assert wa.fetch_media("p", "c@s.whatsapp.net")["mime"] == "application/pdf"
    r = wa.fetch_media("t", "c@s.whatsapp.net")
    assert wa.content_kind(r["mime"]) == "text" and r["data"] == b"a,b\n1,2\n"


def test_audio_is_metadata_only(env):
    wa, add, files, _ = env
    add("a", "audio", "audio_1.ogg", b"OggS" + b"\0" * 20)
    r = wa.fetch_media("a", "c@s.whatsapp.net")
    assert r["ok"] and r["data"] is None and r["mime"] == "audio/ogg"
    assert not os.path.exists(files["a"][0])


def test_size_cap_skips_download(env):
    wa, add, files, _ = env
    add("big", "image", "big.jpg", PNG, size=10**9)
    r = wa.fetch_media("big", "c@s.whatsapp.net", max_bytes=1000)
    assert r["ok"] and r["data"] is None and "limit" in r["error"]
    assert not os.path.exists(files["big"][0])  # never downloaded


def test_size_cap_after_download(env):
    wa, add, files, _ = env
    add("big2", "image", "big2.jpg", PNG + b"\0" * 2000, size=0)  # size unknown up front
    r = wa.fetch_media("big2", "c@s.whatsapp.net", max_bytes=1000)
    assert r["data"] is None and r["meta"]["size"] > 1000
    assert not os.path.exists(files["big2"][0])


def test_path_outside_store_refused(env, tmp_path_factory):
    wa, add, files, _ = env
    outside = tmp_path_factory.mktemp("outside") / "x.png"
    add("evil", "image", "x.png", PNG, path=str(outside))
    r = wa.fetch_media("evil", "c@s.whatsapp.net")
    assert not r["ok"] and "outside" in r["error"]
    assert outside.exists()  # not read, not deleted


def test_not_media(env):
    wa, *_ = env
    assert not wa.fetch_media("nope", "c@s.whatsapp.net")["ok"]


def test_tool_content_blocks(env):
    wa, add, _, _ = env
    add("m1", "image", "image 1.jpg", PNG)
    add("p", "document", "report.pdf", PDF)
    add("a", "audio", "a.ogg", b"OggS")
    from fastmcp import Client
    import main

    async def run():
        async with Client(main.mcp) as c:
            assert "get_media" in [t.name for t in await c.list_tools()]
            img = await c.call_tool("get_media", {"message_id": "m1", "chat_jid": "c@s.whatsapp.net"})
            pdf = await c.call_tool("get_media", {"message_id": "p", "chat_jid": "c@s.whatsapp.net"})
            aud = await c.call_tool("get_media", {"message_id": "a", "chat_jid": "c@s.whatsapp.net"})
            return img, pdf, aud

    img, pdf, aud = asyncio.run(run())
    assert [b.type for b in img.content] == ["text", "image"]
    assert img.content[1].mimeType == "image/png"
    assert [b.type for b in pdf.content] == ["text", "resource"]
    assert pdf.content[1].resource.mimeType == "application/pdf"
    assert [b.type for b in aud.content] == ["text"]
