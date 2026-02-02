from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "contract_mgmt.db"
UPLOAD_DIR = BASE_DIR / "uploads"
ALLOWED_STATES = ["Draft", "Active", "Expiring", "Terminated", "Archived"]

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
app.secret_key = "dev-secret"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    UPLOAD_DIR.mkdir(exist_ok=True)
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS vendors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                risk_profile TEXT,
                status TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                vendor_id INTEGER,
                owner TEXT NOT NULL,
                state TEXT NOT NULL,
                effective_date TEXT,
                termination_date TEXT,
                notice_period_days INTEGER,
                renewal_intent TEXT,
                sensitive INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (vendor_id) REFERENCES vendors (id)
            );

            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                version INTEGER NOT NULL,
                uploaded_at TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                FOREIGN KEY (contract_id) REFERENCES contracts (id)
            );

            CREATE TABLE IF NOT EXISTS extractions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id INTEGER NOT NULL,
                extracted_fields TEXT NOT NULL,
                status TEXT NOT NULL,
                approver TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (contract_id) REFERENCES contracts (id)
            );

            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS contract_tags (
                contract_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (contract_id, tag_id),
                FOREIGN KEY (contract_id) REFERENCES contracts (id),
                FOREIGN KEY (tag_id) REFERENCES tags (id)
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id INTEGER,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                created_at TEXT NOT NULL,
                details TEXT,
                FOREIGN KEY (contract_id) REFERENCES contracts (id)
            );
            """
        )


def now_ts() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def record_audit(contract_id: int | None, action: str, actor: str, details: str = "") -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO audit_events (contract_id, action, actor, created_at, details) VALUES (?, ?, ?, ?, ?)",
            (contract_id, action, actor, now_ts(), details),
        )


def list_vendors() -> list[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM vendors ORDER BY name").fetchall()


def get_contract(contract_id: int) -> sqlite3.Row | None:
    with get_db() as conn:
        return conn.execute(
            """
            SELECT contracts.*, vendors.name AS vendor_name
            FROM contracts
            LEFT JOIN vendors ON vendors.id = contracts.vendor_id
            WHERE contracts.id = ?
            """,
            (contract_id,),
        ).fetchone()


def get_contract_tags(contract_id: int) -> list[str]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT tags.name
            FROM tags
            JOIN contract_tags ON contract_tags.tag_id = tags.id
            WHERE contract_tags.contract_id = ?
            ORDER BY tags.name
            """,
            (contract_id,),
        ).fetchall()
    return [row["name"] for row in rows]


def upsert_tags(contract_id: int, tag_names: list[str]) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM contract_tags WHERE contract_id = ?", (contract_id,))
        for name in tag_names:
            cleaned = name.strip()
            if not cleaned:
                continue
            conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (cleaned,))
            tag_id = conn.execute("SELECT id FROM tags WHERE name = ?", (cleaned,)).fetchone()[0]
            conn.execute(
                "INSERT OR IGNORE INTO contract_tags (contract_id, tag_id) VALUES (?, ?)",
                (contract_id, tag_id),
            )


@app.route("/")
def index():
    with get_db() as conn:
        contracts = conn.execute(
            """
            SELECT contracts.*, vendors.name AS vendor_name
            FROM contracts
            LEFT JOIN vendors ON vendors.id = contracts.vendor_id
            ORDER BY contracts.updated_at DESC
            """
        ).fetchall()
        stats = conn.execute(
            """
            SELECT state, COUNT(*) as total
            FROM contracts
            GROUP BY state
            ORDER BY state
            """
        ).fetchall()
    return render_template("index.html", contracts=contracts, stats=stats)


@app.route("/contracts/new", methods=["GET", "POST"])
def contract_new():
    vendors = list_vendors()
    if request.method == "POST":
        form = request.form
        tags = [tag for tag in form.get("tags", "").split(",") if tag.strip()]
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO contracts
                (title, vendor_id, owner, state, effective_date, termination_date, notice_period_days,
                 renewal_intent, sensitive, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    form.get("title"),
                    form.get("vendor_id") or None,
                    form.get("owner"),
                    form.get("state"),
                    form.get("effective_date") or None,
                    form.get("termination_date") or None,
                    form.get("notice_period_days") or None,
                    form.get("renewal_intent") or None,
                    1 if form.get("sensitive") else 0,
                    now_ts(),
                    now_ts(),
                ),
            )
            contract_id = cursor.lastrowid
            upsert_tags(contract_id, tags)
        record_audit(contract_id, "Created contract", form.get("actor") or "system")
        flash("Contract created.")
        return redirect(url_for("contract_detail", contract_id=contract_id))

    return render_template(
        "contract_form.html",
        contract=None,
        vendors=vendors,
        tags="",
        states=ALLOWED_STATES,
        title="New Contract",
    )


@app.route("/contracts/<int:contract_id>")
def contract_detail(contract_id: int):
    contract = get_contract(contract_id)
    if not contract:
        flash("Contract not found.")
        return redirect(url_for("index"))
    with get_db() as conn:
        documents = conn.execute(
            "SELECT * FROM documents WHERE contract_id = ? ORDER BY version DESC", (contract_id,)
        ).fetchall()
        extractions = conn.execute(
            "SELECT * FROM extractions WHERE contract_id = ? ORDER BY created_at DESC", (contract_id,)
        ).fetchall()
        audits = conn.execute(
            "SELECT * FROM audit_events WHERE contract_id = ? ORDER BY created_at DESC", (contract_id,)
        ).fetchall()
    tags = get_contract_tags(contract_id)
    return render_template(
        "contract_detail.html",
        contract=contract,
        documents=documents,
        extractions=extractions,
        audits=audits,
        tags=tags,
    )


@app.route("/contracts/<int:contract_id>/edit", methods=["GET", "POST"])
def contract_edit(contract_id: int):
    contract = get_contract(contract_id)
    if not contract:
        flash("Contract not found.")
        return redirect(url_for("index"))
    vendors = list_vendors()
    if request.method == "POST":
        form = request.form
        tags = [tag for tag in form.get("tags", "").split(",") if tag.strip()]
        with get_db() as conn:
            conn.execute(
                """
                UPDATE contracts
                SET title = ?, vendor_id = ?, owner = ?, state = ?, effective_date = ?,
                    termination_date = ?, notice_period_days = ?, renewal_intent = ?, sensitive = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    form.get("title"),
                    form.get("vendor_id") or None,
                    form.get("owner"),
                    form.get("state"),
                    form.get("effective_date") or None,
                    form.get("termination_date") or None,
                    form.get("notice_period_days") or None,
                    form.get("renewal_intent") or None,
                    1 if form.get("sensitive") else 0,
                    now_ts(),
                    contract_id,
                ),
            )
            upsert_tags(contract_id, tags)
        record_audit(contract_id, "Updated contract", form.get("actor") or "system")
        flash("Contract updated.")
        return redirect(url_for("contract_detail", contract_id=contract_id))

    tags = ", ".join(get_contract_tags(contract_id))
    return render_template(
        "contract_form.html",
        contract=contract,
        vendors=vendors,
        tags=tags,
        states=ALLOWED_STATES,
        title=f"Edit Contract {contract['title']}",
    )


@app.route("/vendors")
def vendor_list():
    vendors = list_vendors()
    return render_template("vendor_list.html", vendors=vendors)


@app.route("/vendors/new", methods=["GET", "POST"])
def vendor_new():
    if request.method == "POST":
        form = request.form
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO vendors (name, risk_profile, status, created_at) VALUES (?, ?, ?, ?)",
                (
                    form.get("name"),
                    form.get("risk_profile") or None,
                    form.get("status") or None,
                    now_ts(),
                ),
            )
            vendor_id = cursor.lastrowid
        record_audit(None, "Created vendor", form.get("actor") or "system", f"Vendor {vendor_id}")
        flash("Vendor created.")
        return redirect(url_for("vendor_list"))
    return render_template("vendor_form.html", vendor=None, title="New Vendor")


@app.route("/vendors/<int:vendor_id>/edit", methods=["GET", "POST"])
def vendor_edit(vendor_id: int):
    with get_db() as conn:
        vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
    if not vendor:
        flash("Vendor not found.")
        return redirect(url_for("vendor_list"))
    if request.method == "POST":
        form = request.form
        with get_db() as conn:
            conn.execute(
                "UPDATE vendors SET name = ?, risk_profile = ?, status = ? WHERE id = ?",
                (
                    form.get("name"),
                    form.get("risk_profile") or None,
                    form.get("status") or None,
                    vendor_id,
                ),
            )
        record_audit(None, "Updated vendor", form.get("actor") or "system", f"Vendor {vendor_id}")
        flash("Vendor updated.")
        return redirect(url_for("vendor_list"))
    return render_template("vendor_form.html", vendor=vendor, title=f"Edit Vendor {vendor['name']}")


@app.route("/contracts/<int:contract_id>/documents/new", methods=["GET", "POST"])
def document_new(contract_id: int):
    contract = get_contract(contract_id)
    if not contract:
        flash("Contract not found.")
        return redirect(url_for("index"))
    if request.method == "POST":
        file = request.files.get("document")
        actor = request.form.get("actor") or "system"
        if not file or not file.filename:
            flash("Select a document to upload.")
            return redirect(request.url)
        filename = secure_filename(file.filename)
        with get_db() as conn:
            version_row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 AS next_version FROM documents WHERE contract_id = ?",
                (contract_id,),
            ).fetchone()
            version = version_row["next_version"]
        stored_name = f"{contract_id}_{version}_{filename}"
        storage_path = UPLOAD_DIR / stored_name
        file.save(storage_path)
        sha256 = hashlib.sha256(storage_path.read_bytes()).hexdigest()
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO documents (contract_id, filename, storage_path, version, uploaded_at, sha256)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (contract_id, filename, stored_name, version, now_ts(), sha256),
            )
        record_audit(contract_id, "Uploaded document", actor, f"Document {filename} v{version}")
        flash("Document uploaded.")
        return redirect(url_for("contract_detail", contract_id=contract_id))
    return render_template("document_form.html", contract=contract)


@app.route("/documents/<path:filename>")
def document_download(filename: str):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)


@app.route("/contracts/<int:contract_id>/extractions/new", methods=["GET", "POST"])
def extraction_new(contract_id: int):
    contract = get_contract(contract_id)
    if not contract:
        flash("Contract not found.")
        return redirect(url_for("index"))
    if request.method == "POST":
        form = request.form
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO extractions (contract_id, extracted_fields, status, approver, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    contract_id,
                    form.get("extracted_fields"),
                    form.get("status"),
                    form.get("approver") or None,
                    now_ts(),
                ),
            )
        record_audit(contract_id, "Logged extraction", form.get("actor") or "system")
        flash("Extraction logged.")
        return redirect(url_for("contract_detail", contract_id=contract_id))
    return render_template("extraction_form.html", contract=contract)


@app.route("/audit")
def audit_log():
    with get_db() as conn:
        audits = conn.execute(
            """
            SELECT audit_events.*, contracts.title AS contract_title
            FROM audit_events
            LEFT JOIN contracts ON contracts.id = audit_events.contract_id
            ORDER BY audit_events.created_at DESC
            """
        ).fetchall()
    return render_template("audit_log.html", audits=audits)


init_db()

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
