"""Tests d'intégration de la bibliothèque de documents (CV / LM) + FK SET NULL."""

from __future__ import annotations

import io

import pytest

import app.api.routes.main as routes

pytestmark = pytest.mark.asyncio


def _pdf_bytes(size: int = 0) -> bytes:
    base = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    if size and size > len(base):
        base = base + b"0" * (size - len(base))
    return base


def _upload(doc_type: str = "cv", label: str = "CV_quant_v2", filename: str = "cv.pdf",
            content: bytes | None = None, content_type: str = "application/pdf"):
    return {
        "data": {"doc_type": doc_type, "label": label},
        "files": {"file": (filename, io.BytesIO(content or _pdf_bytes()), content_type)},
    }


# ─── Upload ───────────────────────────────────────────────
async def test_upload_valid_pdf(client):
    u = _upload(label="CV_finance")
    r = await client.post("/documents", data=u["data"], files=u["files"])
    assert r.status_code == 201
    doc = r.json()
    assert doc["id"] > 0
    assert doc["doc_type"] == "cv"
    assert doc["label"] == "CV_finance"
    assert doc["original_filename"] == "cv.pdf"
    assert doc["file_size"] > 0


async def test_upload_rejects_non_pdf_type(client):
    u = _upload(filename="x.txt", content=b"hello", content_type="text/plain")
    r = await client.post("/documents", data=u["data"], files=u["files"])
    assert r.status_code == 400


async def test_upload_rejects_fake_pdf_content(client):
    u = _upload(content=b"not really a pdf")
    r = await client.post("/documents", data=u["data"], files=u["files"])
    assert r.status_code == 400


async def test_upload_rejects_too_large(client):
    old = routes.settings.max_upload_bytes
    routes.settings.max_upload_bytes = 200
    try:
        u = _upload(content=_pdf_bytes(500))
        r = await client.post("/documents", data=u["data"], files=u["files"])
        assert r.status_code == 413
    finally:
        routes.settings.max_upload_bytes = old


async def test_upload_rejects_empty_label(client):
    u = _upload(label="   ")
    r = await client.post("/documents", data=u["data"], files=u["files"])
    assert r.status_code == 400


# ─── List / filter / get ──────────────────────────────────
async def test_list_filter_by_doc_type(client):
    for u in (_upload("cv", "CV1"), _upload("cv", "CV2"), _upload("lm", "LM1")):
        await client.post("/documents", data=u["data"], files=u["files"])

    assert len((await client.get("/documents")).json()) == 3
    cvs = (await client.get("/documents", params={"doc_type": "cv"})).json()
    assert len(cvs) == 2 and all(d["doc_type"] == "cv" for d in cvs)
    lms = (await client.get("/documents", params={"doc_type": "lm"})).json()
    assert len(lms) == 1 and lms[0]["label"] == "LM1"


async def test_get_and_download(client):
    u = _upload()
    doc = (await client.post("/documents", data=u["data"], files=u["files"])).json()

    assert (await client.get(f"/documents/{doc['id']}")).json()["label"] == "CV_quant_v2"

    r = await client.get(f"/documents/{doc['id']}/download")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")

    assert (await client.get("/documents/9999")).status_code == 404


# ─── Rename ───────────────────────────────────────────────
async def test_rename_document(client):
    u = _upload()
    doc = (await client.post("/documents", data=u["data"], files=u["files"])).json()
    r = await client.patch(f"/documents/{doc['id']}", json={"label": "CV_v3"})
    assert r.status_code == 200
    assert r.json()["label"] == "CV_v3"
    assert (await client.get(f"/documents/{doc['id']}")).json()["label"] == "CV_v3"


# ─── Liaison sur offres / contacts + exposition dans *Out ──
async def test_link_document_to_offer_and_contact(client):
    cv = (await client.post("/documents", **_upload("cv", "CV_link"))).json()
    lm = (await client.post("/documents", **_upload("lm", "LM_link"))).json()

    o = (await client.post(
        "/offers",
        json={"title": "A", "company": "X", "cv_document_id": cv["id"], "lm_document_id": lm["id"]},
    )).json()
    assert o["cv_document_id"] == cv["id"]
    assert o["cv_document"]["label"] == "CV_link"
    assert o["lm_document"]["label"] == "LM_link"

    c = (await client.post(
        "/contacts", json={"name": "Jean", "cv_document_id": cv["id"]}
    )).json()
    assert c["cv_document"]["label"] == "CV_link"

    # Unset via update (null explicite).
    o2 = (await client.put(f"/offers/{o['id']}", json={"cv_document_id": None})).json()
    assert o2["cv_document_id"] is None
    assert o2["cv_document"] is None


async def test_link_rejects_unknown_document(client):
    r = await client.post("/offers", json={"title": "A", "company": "X", "cv_document_id": 4242})
    assert r.status_code == 400


async def test_link_rejects_wrong_doc_type(client):
    lm = (await client.post("/documents", **_upload("lm", "LM"))).json()
    # Mettre une LM dans le slot CV doit être refusé.
    r = await client.post("/offers", json={"title": "A", "company": "X", "cv_document_id": lm["id"]})
    assert r.status_code == 400


# ─── Suppression document référencé → FK SET NULL + count ──
async def test_delete_document_sets_null_and_counts(client):
    cv = (await client.post("/documents", **_upload("cv", "CV_shared"))).json()

    o = (await client.post(
        "/offers", json={"title": "A", "company": "X", "cv_document_id": cv["id"]}
    )).json()
    c = (await client.post(
        "/contacts", json={"name": "Jean", "cv_document_id": cv["id"]}
    )).json()

    r = await client.delete(f"/documents/{cv['id']}")
    assert r.status_code == 200
    # 1 offre + 1 contact = 2 fiches affectées.
    assert r.json()["affected"] == 2

    # Le document a disparu, les liens sont nullifiés (SET NULL).
    assert (await client.get(f"/documents/{cv['id']}")).status_code == 404
    assert (await client.get(f"/offers/{o['id']}")).json()["cv_document_id"] is None
    assert (await client.get(f"/contacts/{c['id']}")).json()["cv_document_id"] is None


async def test_delete_unreferenced_document_counts_zero(client):
    doc = (await client.post("/documents", **_upload())).json()
    r = await client.delete(f"/documents/{doc['id']}")
    assert r.status_code == 200
    assert r.json()["affected"] == 0
