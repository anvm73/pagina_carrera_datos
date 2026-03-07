from __future__ import annotations

import json
import mimetypes
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from sqlalchemy import select

try:
    from app import db, models
except ModuleNotFoundError:
    import db
    import models


BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
DATA_DIR = BACKEND_DIR / "data"
CONTENT_DIR = DATA_DIR / "content"
UPLOADS_DIR = DATA_DIR / "uploads"
PRESENTATIONS_UPLOADS_DIR = UPLOADS_DIR / "presentations"
CENTERS_UPLOADS_DIR = UPLOADS_DIR / "centers"
ALUMNI_UPLOADS_DIR = UPLOADS_DIR / "alumni"
FRONTEND_PRESENTATIONS_DIR = FRONTEND_DIR / "public" / "presentaciones"

CENTERS_FILE = CONTENT_DIR / "centers.json"
PRESENTATIONS_FILE = CONTENT_DIR / "presentations.json"
ALUMNI_WALL_FILE = CONTENT_DIR / "alumni_wall.json"
STUDENT_ACCOUNTS_FILE = CONTENT_DIR / "student_accounts.json"

_storage_initialized = False
_BOOTSTRAP_FLAG_KEY = "storage_bootstrapped_v1"
_CREA_BOARD_KEY = "crea-global"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "item"


def unique_slug(base: str, existing_ids: set[str]) -> str:
    candidate = slugify(base)
    if candidate not in existing_ids:
        return candidate

    suffix = 2
    while f"{candidate}-{suffix}" in existing_ids:
        suffix += 1
    return f"{candidate}-{suffix}"


def ensure_directories() -> None:
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    PRESENTATIONS_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    CENTERS_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    ALUMNI_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def normalize_presentation_name(file_name: str) -> str:
    raw = re.sub(r"\.pdf$", "", file_name, flags=re.IGNORECASE)
    raw = raw.replace("_", " ").replace("-", " ")
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw or "Presentacion"


def build_media_url(*parts: str) -> str:
    return "/media/" + "/".join(quote(part) for part in parts if part)


def build_db_media_url(*parts: str) -> str:
    return "/media-db/" + "/".join(quote(part) for part in parts if part)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path, default_factory: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    ensure_directories()
    if not path.exists():
        data = default_factory()
        write_json(path, data)
        return data

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = default_factory()
        write_json(path, data)
        return data


def default_centers() -> dict[str, Any]:
    created_at = now_iso()
    return {
        "items": [
            {
                "id": "ce-iccd-2024-2026",
                "name": "Centro de Estudiantes ICCD",
                "period_label": "2024-2026",
                "description": "Representamos a la comunidad ICCD UTEM con foco en proyectos academicos, bienestar y vinculacion con la industria.",
                "is_active": True,
                "created_at": created_at,
                "members": [
                    {
                        "id": "andres-nicolas-vega-moraga",
                        "name": "Andres Nicolas Vega Moraga",
                        "role": "Presidente",
                        "bio": "",
                        "image_url": "/imagenes/andres.jpeg",
                        "linkedin_url": "",
                        "created_at": created_at,
                    },
                    {
                        "id": "bruno-eduardo-sainz-silva",
                        "name": "Bruno Eduardo Sainz Silva",
                        "role": "Vicepresidente",
                        "bio": "",
                        "image_url": "/imagenes/bruno.jpeg",
                        "linkedin_url": "https://www.linkedin.com/in/brunosainzsilva/",
                        "created_at": created_at,
                    },
                    {
                        "id": "juan-cristobal-toledo-fierro",
                        "name": "Juan Cristobal Toledo Fierro",
                        "role": "Tesorero",
                        "bio": "",
                        "image_url": "/imagenes/juan.jpeg",
                        "linkedin_url": "",
                        "created_at": created_at,
                    },
                    {
                        "id": "camilo-andres-cerda-sarabia",
                        "name": "Camilo Andres Cerda Sarabia",
                        "role": "Secretario",
                        "bio": "",
                        "image_url": "/imagenes/camilo.jpeg",
                        "linkedin_url": "",
                        "created_at": created_at,
                    },
                    {
                        "id": "diego-mauricio-gonzalez-vega",
                        "name": "Diego Mauricio Gonzalez Vega",
                        "role": "Genero estudiantil",
                        "bio": "",
                        "image_url": "/imagenes/diego.jpg",
                        "linkedin_url": "",
                        "created_at": created_at,
                    },
                    {
                        "id": "welinton-antonio-barrera-mondaca",
                        "name": "Welinton Antonio Barrera Mondaca",
                        "role": "Comunicaciones",
                        "bio": "",
                        "image_url": "/imagenes/welinton.jpeg",
                        "linkedin_url": "",
                        "created_at": created_at,
                    },
                    {
                        "id": "joaquin-ignacio-araya-bustos",
                        "name": "Joaquin Ignacio Araya Bustos",
                        "role": "Delegado de Recreacion",
                        "bio": "",
                        "image_url": "/imagenes/joaquin.jpeg",
                        "linkedin_url": "",
                        "created_at": created_at,
                    },
                ],
            }
        ]
    }


def default_presentations() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    existing_ids: set[str] = set()

    if FRONTEND_PRESENTATIONS_DIR.exists():
        pdfs = sorted(
            (
                entry
                for entry in FRONTEND_PRESENTATIONS_DIR.iterdir()
                if entry.is_file() and entry.suffix.lower() == ".pdf"
            ),
            key=lambda entry: entry.stat().st_mtime,
            reverse=True,
        )
        for pdf in pdfs:
            title = normalize_presentation_name(pdf.name)
            item_id = unique_slug(title, existing_ids)
            existing_ids.add(item_id)
            items.append(
                {
                    "id": item_id,
                    "title": title,
                    "description": "Documento PDF disponible para presentacion.",
                    "pdf_url": f"/presentaciones/{quote(pdf.name)}",
                    "storage": "frontend-public",
                    "file_name": pdf.name,
                    "created_at": datetime.fromtimestamp(
                        pdf.stat().st_mtime,
                        tz=timezone.utc,
                    ).isoformat(),
                }
            )

    return {"items": items}


def default_alumni_wall() -> dict[str, Any]:
    return {
        "intro": "Este es un muro conmemorativo para recordar a nuestros companeros titulados, como tambien estar conectados a traves de LinkedIn para una Red de Ciencia de Datos.",
        "items": [],
    }


def default_student_accounts() -> dict[str, Any]:
    return {"items": []}


def default_shared_board() -> dict[str, Any]:
    return {
        "version": 5,
        "brushColor": "#005DA4",
        "brushSize": 8,
        "eraserSize": 240,
        "strokes": [],
        "updatedAt": "",
        "updatedBy": "",
    }


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _serialize_center_member(member: models.CenterMember) -> dict[str, Any]:
    return {
        "id": member.id,
        "name": member.name,
        "role": member.role,
        "bio": member.bio,
        "image_url": member.image_url,
        "linkedin_url": member.linkedin_url,
        "created_at": member.created_at.isoformat(),
    }


def _serialize_center(center: models.Center) -> dict[str, Any]:
    return {
        "id": center.id,
        "name": center.name,
        "period_label": center.period_label,
        "description": center.description,
        "is_active": center.is_active,
        "created_at": center.created_at.isoformat(),
        "members": [_serialize_center_member(member) for member in center.members],
    }


def _serialize_presentation(item: models.Presentation) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "pdf_url": item.pdf_url,
        "storage": item.storage,
        "file_name": item.file_name,
        "created_at": item.created_at.isoformat(),
    }


def _serialize_alumni(item: models.AlumniProfile) -> dict[str, Any]:
    image_url = build_db_media_url("alumni", item.id) if item.image_blob else item.image_url
    return {
        "id": item.id,
        "full_name": item.full_name,
        "summary": item.summary,
        "graduation_year": item.graduation_year,
        "linkedin_url": item.linkedin_url,
        "image_url": image_url,
        "created_at": item.created_at.isoformat(),
    }


def _serialize_student(item: models.StudentAccount) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "email": item.email,
        "password_hash": item.password_hash,
        "created_at": item.created_at.isoformat(),
    }


def _legacy_centers_data() -> dict[str, Any]:
    return read_json(CENTERS_FILE, default_centers)


def _legacy_presentations_data() -> dict[str, Any]:
    return read_json(PRESENTATIONS_FILE, default_presentations)


def _legacy_alumni_data() -> dict[str, Any]:
    return read_json(ALUMNI_WALL_FILE, default_alumni_wall)


def _legacy_students_data() -> dict[str, Any]:
    return read_json(STUDENT_ACCOUNTS_FILE, default_student_accounts)


def _guess_content_type(value: str) -> str:
    guessed, _ = mimetypes.guess_type(value)
    return guessed or "image/jpeg"


def _resolve_upload_path_from_media_url(media_url: str) -> Path | None:
    if not media_url.startswith("/media/"):
        return None

    relative_path = Path(media_url.removeprefix("/media/"))
    target_path = (UPLOADS_DIR / relative_path).resolve()
    uploads_root = UPLOADS_DIR.resolve()
    if target_path == uploads_root or uploads_root not in target_path.parents:
        return None
    if not target_path.exists() or not target_path.is_file():
        return None
    return target_path


def _extract_alumni_image_storage(
    item_data: dict[str, Any],
    existing_images: dict[str, dict[str, Any]],
) -> tuple[str, str, bytes | None]:
    item_id = str(item_data.get("id", "") or "")
    raw_image_url = str(item_data.get("image_url", "") or "").strip()
    existing = existing_images.get(item_id)

    if existing and existing.get("image_blob") and (
        not raw_image_url
        or raw_image_url == existing.get("image_url", "")
        or raw_image_url.startswith("/media-db/alumni/")
    ):
        return (
            build_db_media_url("alumni", item_id),
            str(existing.get("image_content_type", "") or "image/jpeg"),
            existing.get("image_blob"),
        )

    upload_path = _resolve_upload_path_from_media_url(raw_image_url)
    if upload_path is not None:
        return (
            build_db_media_url("alumni", item_id),
            _guess_content_type(upload_path.name),
            upload_path.read_bytes(),
        )

    return raw_image_url, "", None


def initialize_storage() -> None:
    global _storage_initialized
    if _storage_initialized:
        return

    ensure_directories()
    db.initialize_database()
    _storage_initialized = True
    try:
        bootstrap_database()
    except Exception:
        _storage_initialized = False
        raise


def bootstrap_database() -> None:
    with db.SessionLocal() as session:
        bootstrapped = session.get(models.SiteSetting, _BOOTSTRAP_FLAG_KEY)
        if bootstrapped is not None:
            return

        has_centers = session.execute(select(models.Center.id).limit(1)).first() is not None
        has_presentations = session.execute(select(models.Presentation.id).limit(1)).first() is not None
        has_alumni = session.execute(select(models.AlumniProfile.id).limit(1)).first() is not None
        has_students = session.execute(select(models.StudentAccount.id).limit(1)).first() is not None
        has_intro = session.get(models.SiteSetting, "alumni_intro") is not None

    is_pristine = not any((has_centers, has_presentations, has_alumni, has_students, has_intro))

    if is_pristine:
        save_centers(_legacy_centers_data())
        save_presentations(_legacy_presentations_data())
        save_alumni_wall(_legacy_alumni_data())
        save_student_accounts(_legacy_students_data())

    with db.SessionLocal.begin() as session:
        session.merge(
            models.SiteSetting(
                key=_BOOTSTRAP_FLAG_KEY,
                value=now_iso(),
                updated_at=datetime.now(timezone.utc),
            )
        )


def load_centers() -> dict[str, Any]:
    initialize_storage()
    with db.SessionLocal() as session:
        centers = session.scalars(select(models.Center).order_by(models.Center.created_at)).unique().all()
        return {"items": [_serialize_center(center) for center in centers]}


def save_centers(data: dict[str, Any]) -> None:
    initialize_storage()
    items = data.get("items", [])
    with db.SessionLocal.begin() as session:
        session.query(models.Center).delete()
        for center_data in items:
            center = models.Center(
                id=center_data.get("id", ""),
                name=center_data.get("name", ""),
                period_label=center_data.get("period_label", ""),
                description=center_data.get("description", ""),
                is_active=bool(center_data.get("is_active", False)),
                created_at=_parse_dt(center_data.get("created_at")),
            )
            for member_data in center_data.get("members", []):
                center.members.append(
                    models.CenterMember(
                        id=member_data.get("id", ""),
                        name=member_data.get("name", ""),
                        role=member_data.get("role", ""),
                        bio=member_data.get("bio", ""),
                        image_url=member_data.get("image_url", ""),
                        linkedin_url=member_data.get("linkedin_url", ""),
                        created_at=_parse_dt(member_data.get("created_at")),
                    )
                )
            session.add(center)


def load_presentations() -> dict[str, Any]:
    initialize_storage()
    with db.SessionLocal() as session:
        items = session.scalars(select(models.Presentation).order_by(models.Presentation.created_at)).all()
        return {"items": [_serialize_presentation(item) for item in items]}


def save_presentations(data: dict[str, Any]) -> None:
    initialize_storage()
    items = data.get("items", [])
    with db.SessionLocal.begin() as session:
        session.query(models.Presentation).delete()
        for item_data in items:
            session.add(
                models.Presentation(
                    id=item_data.get("id", ""),
                    title=item_data.get("title", ""),
                    description=item_data.get("description", ""),
                    pdf_url=item_data.get("pdf_url", ""),
                    storage=item_data.get("storage", "media"),
                    file_name=item_data.get("file_name", ""),
                    created_at=_parse_dt(item_data.get("created_at")),
                )
            )


def load_alumni_wall() -> dict[str, Any]:
    initialize_storage()
    with db.SessionLocal() as session:
        intro_setting = session.get(models.SiteSetting, "alumni_intro")
        items = session.scalars(select(models.AlumniProfile).order_by(models.AlumniProfile.created_at)).all()
        return {
            "intro": intro_setting.value if intro_setting else default_alumni_wall()["intro"],
            "items": [_serialize_alumni(item) for item in items],
        }


def save_alumni_wall(data: dict[str, Any]) -> None:
    initialize_storage()
    items = data.get("items", [])
    intro = str(data.get("intro", default_alumni_wall()["intro"]))
    with db.SessionLocal() as session:
        existing_images = {
            item.id: {
                "image_url": item.image_url,
                "image_content_type": item.image_content_type,
                "image_blob": bytes(item.image_blob) if item.image_blob is not None else None,
            }
            for item in session.scalars(select(models.AlumniProfile)).all()
        }

    with db.SessionLocal.begin() as session:
        intro_setting = session.get(models.SiteSetting, "alumni_intro")
        if intro_setting is None:
            intro_setting = models.SiteSetting(key="alumni_intro", value=intro, updated_at=datetime.now(timezone.utc))
            session.add(intro_setting)
        else:
            intro_setting.value = intro
            intro_setting.updated_at = datetime.now(timezone.utc)

        session.query(models.AlumniProfile).delete()
        for item_data in items:
            image_url, image_content_type, image_blob = _extract_alumni_image_storage(item_data, existing_images)
            session.add(
                models.AlumniProfile(
                    id=item_data.get("id", ""),
                    full_name=item_data.get("full_name", ""),
                    summary=item_data.get("summary", ""),
                    graduation_year=int(item_data.get("graduation_year", 0) or 0),
                    linkedin_url=item_data.get("linkedin_url", ""),
                    image_url=image_url,
                    image_content_type=image_content_type,
                    image_blob=image_blob,
                    created_at=_parse_dt(item_data.get("created_at")),
                )
            )


def load_student_accounts() -> dict[str, Any]:
    initialize_storage()
    with db.SessionLocal() as session:
        items = session.scalars(select(models.StudentAccount).order_by(models.StudentAccount.created_at)).all()
        return {"items": [_serialize_student(item) for item in items]}


def save_student_accounts(data: dict[str, Any]) -> None:
    initialize_storage()
    items = data.get("items", [])
    with db.SessionLocal.begin() as session:
        session.query(models.StudentAccount).delete()
        for item_data in items:
            session.add(
                models.StudentAccount(
                    id=item_data.get("id", ""),
                    name=item_data.get("name", ""),
                    email=item_data.get("email", "").strip().lower(),
                    password_hash=item_data.get("password_hash", ""),
                    created_at=_parse_dt(item_data.get("created_at")),
                )
            )


def load_shared_board() -> dict[str, Any]:
    initialize_storage()
    fallback = default_shared_board()
    with db.SessionLocal() as session:
        board = session.get(models.SharedBoardState, _CREA_BOARD_KEY)
        if board is None:
            return fallback

        try:
            payload = json.loads(board.payload or "{}")
        except Exception:
            payload = {}

        if not isinstance(payload, dict):
            payload = {}

        return {
            "version": int(payload.get("version", fallback["version"])),
            "brushColor": str(payload.get("brushColor", fallback["brushColor"])),
            "brushSize": payload.get("brushSize", fallback["brushSize"]),
            "eraserSize": payload.get("eraserSize", fallback["eraserSize"]),
            "strokes": payload.get("strokes", fallback["strokes"]),
            "updatedAt": board.updated_at.isoformat() if board.updated_at else "",
            "updatedBy": board.updated_by or "",
        }


def save_shared_board(data: dict[str, Any], updated_by: str = "") -> dict[str, Any]:
    initialize_storage()
    fallback = default_shared_board()
    payload = {
        "version": int(data.get("version", fallback["version"])),
        "brushColor": str(data.get("brushColor", fallback["brushColor"])),
        "brushSize": data.get("brushSize", fallback["brushSize"]),
        "eraserSize": data.get("eraserSize", fallback["eraserSize"]),
        "strokes": data.get("strokes", fallback["strokes"]),
    }
    updated_at = datetime.now(timezone.utc)

    with db.SessionLocal.begin() as session:
        board = session.get(models.SharedBoardState, _CREA_BOARD_KEY)
        if board is None:
            board = models.SharedBoardState(
                key=_CREA_BOARD_KEY,
                payload=json.dumps(payload, ensure_ascii=False),
                updated_by=updated_by,
                updated_at=updated_at,
            )
            session.add(board)
        else:
            board.payload = json.dumps(payload, ensure_ascii=False)
            board.updated_by = updated_by
            board.updated_at = updated_at

    return {
        **payload,
        "updatedAt": updated_at.isoformat(),
        "updatedBy": updated_by,
    }
