from __future__ import annotations

import html
import json
import math
import mimetypes
import os
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

import requests
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field

try:
    from app import admin_auth, content_store, db, models, student_auth
except ModuleNotFoundError:
    import admin_auth
    import content_store
    import db
    import models
    import student_auth

chatbot = None
chatbot_import_error: str | None = None

try:
    try:
        from app import chatbot as chatbot_module
    except ModuleNotFoundError:
        import chatbot as chatbot_module
    chatbot = chatbot_module
except Exception as exc:
    chatbot_import_error = str(exc)


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SUBMISSIONS_DIR = DATA_DIR / "project_submissions"
SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)
content_store.initialize_storage()

UTEM_EMAIL_PATTERN = re.compile(r"^[^@\s]+@utem\.cl$", flags=re.IGNORECASE)
LINKEDIN_URL_PATTERN = re.compile(r"^https?://([a-z]{2,3}\.)?linkedin\.com/", flags=re.IGNORECASE)
META_TAG_PATTERN = re.compile(
    r"<meta\b[^>]*(?:property|name)=['\"](?P<key>[^'\"]+)['\"][^>]*content=['\"](?P<content>[^'\"]*)['\"][^>]*>",
    flags=re.IGNORECASE,
)
META_TAG_REVERSED_PATTERN = re.compile(
    r"<meta\b[^>]*content=['\"](?P<content>[^'\"]*)['\"][^>]*(?:property|name)=['\"](?P<key>[^'\"]+)['\"][^>]*>",
    flags=re.IGNORECASE,
)
TITLE_TAG_PATTERN = re.compile(r"<title>(?P<title>.*?)</title>", flags=re.IGNORECASE | re.DOTALL)
JSON_LD_PATTERN = re.compile(
    r"<script[^>]+type=['\"]application/ld\+json['\"][^>]*>(?P<payload>.*?)</script>",
    flags=re.IGNORECASE | re.DOTALL,
)
TAG_PATTERN = re.compile(r"<[^>]+>")

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
REQUEST_TIMEOUT_S = int(os.getenv("OUTBOUND_REQUEST_TIMEOUT_S", "12"))
MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_MB", "12")) * 1024 * 1024
MAX_REQUEST_SIZE_BYTES = int(os.getenv("MAX_REQUEST_SIZE_MB", "20")) * 1024 * 1024
TRUSTED_HOSTS = [
    host.strip()
    for host in os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
DEFAULT_REMOTE_IMAGE_HOSTS = [
    "media.licdn.com",
    "media-exp1.licdn.com",
    "media-exp2.licdn.com",
    "static.licdn.com",
    "linkedin.com",
    "www.linkedin.com",
]
ALLOWED_REMOTE_IMAGE_HOSTS = {
    host.strip().lower()
    for host in os.getenv(
        "ALLOWED_REMOTE_IMAGE_HOSTS",
        ",".join(DEFAULT_REMOTE_IMAGE_HOSTS),
    ).split(",")
    if host.strip()
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
PDF_CONTENT_TYPES = {"application/pdf"}
CREA_STORAGE_VERSION = 5
CREA_WORLD_WIDTH = 60000
CREA_WORLD_HEIGHT = 60000
CREA_MAX_STROKES = 7000
CREA_MAX_POINTS = 220000
CREA_BRUSH_MIN = 1
CREA_BRUSH_MAX = 420
CREA_ERASER_MIN = 20
CREA_ERASER_MAX = 1200
CREA_MIN_IMAGE_SIDE = 80
CREA_MAX_IMAGE_SIDE = 8000
CREA_MAX_IMAGE_DATA_URL_CHARS = 12_000_000


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "item"


def ensure_utem_email(email: str) -> str:
    email_clean = email.strip().lower()
    if not UTEM_EMAIL_PATTERN.match(email_clean):
        raise HTTPException(status_code=400, detail="Debes usar un correo @utem.cl")
    return email_clean


def safe_relative_path(raw_name: str) -> Path:
    candidate = Path(raw_name.replace("\\", "/"))
    sanitized_parts = [part for part in candidate.parts if part not in {"", ".", ".."}]
    if not sanitized_parts:
        return Path("archivo.bin")
    return Path(*sanitized_parts)


def build_submission_id(title: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-{slugify(title)[:48]}"


def sanitize_optional_text(value: str | None) -> str:
    return (value or "").strip()


def parse_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "on", "yes", "si"}


def parse_year(value: int) -> int:
    current_year = datetime.now(timezone.utc).year + 1
    if value < 1900 or value > current_year:
        raise HTTPException(status_code=400, detail="Ano de titulacion invalido")
    return value


def clamp_float(value: Any, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return minimum
    if not math.isfinite(number):
        return minimum
    return min(max(number, minimum), maximum)


def is_hex_color(value: str) -> bool:
    return bool(re.fullmatch(r"#[\da-fA-F]{6}", value))


def model_to_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def normalize_crea_image_placement(x: Any, y: Any, width: Any, height: Any) -> dict[str, float]:
    safe_width = clamp_float(width, CREA_MIN_IMAGE_SIDE, min(CREA_MAX_IMAGE_SIDE, CREA_WORLD_WIDTH))
    safe_height = clamp_float(height, CREA_MIN_IMAGE_SIDE, min(CREA_MAX_IMAGE_SIDE, CREA_WORLD_HEIGHT))
    max_x = max(0.0, CREA_WORLD_WIDTH - safe_width)
    max_y = max(0.0, CREA_WORLD_HEIGHT - safe_height)

    return {
        "x": clamp_float(x, 0, max_x),
        "y": clamp_float(y, 0, max_y),
        "width": safe_width,
        "height": safe_height,
    }


def sanitize_crea_board_element(raw_element: Any) -> dict[str, Any] | None:
    if not isinstance(raw_element, dict):
        return None

    if raw_element.get("mode") == "image":
        src = str(raw_element.get("src", "") or "").strip()
        if not src.startswith("data:image/") or len(src) > CREA_MAX_IMAGE_DATA_URL_CHARS:
            return None

        placement = normalize_crea_image_placement(
            raw_element.get("x", 0),
            raw_element.get("y", 0),
            raw_element.get("width", CREA_MIN_IMAGE_SIDE),
            raw_element.get("height", CREA_MIN_IMAGE_SIDE),
        )
        return {
            "mode": "image",
            "src": src,
            "x": placement["x"],
            "y": placement["y"],
            "width": placement["width"],
            "height": placement["height"],
        }

    raw_points = raw_element.get("points")
    if not isinstance(raw_points, list):
        return None

    mode = "erase" if raw_element.get("mode") == "erase" else "draw"
    size = clamp_float(
        raw_element.get("size"),
        CREA_ERASER_MIN if mode == "erase" else CREA_BRUSH_MIN,
        CREA_ERASER_MAX if mode == "erase" else CREA_BRUSH_MAX,
    )
    color = "#FFFFFF" if mode == "erase" else "#005DA4"
    raw_color = str(raw_element.get("color", "") or "").strip()
    if mode != "erase" and is_hex_color(raw_color):
        color = raw_color

    points: list[dict[str, float]] = []
    for raw_point in raw_points:
        if not isinstance(raw_point, dict):
            continue
        x = raw_point.get("x")
        y = raw_point.get("y")
        try:
            point_x = float(x)
            point_y = float(y)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(point_x) or not math.isfinite(point_y):
            continue
        points.append(
            {
                "x": clamp_float(point_x, 0, CREA_WORLD_WIDTH),
                "y": clamp_float(point_y, 0, CREA_WORLD_HEIGHT),
            }
        )

    if not points:
        return None

    return {
        "mode": mode,
        "color": color,
        "size": size,
        "points": points,
    }


def sanitize_crea_board_payload(raw_payload: dict[str, Any]) -> dict[str, Any]:
    raw_strokes = raw_payload.get("strokes", [])
    strokes: list[dict[str, Any]] = []
    total_points = 0

    if isinstance(raw_strokes, list):
        candidates = raw_strokes[-CREA_MAX_STROKES:]
    else:
        candidates = []

    for raw_element in candidates:
        element = sanitize_crea_board_element(raw_element)
        if element is None:
            continue

        if element["mode"] != "image":
            remaining_points = CREA_MAX_POINTS - total_points
            if remaining_points <= 0:
                break

            if len(element["points"]) > remaining_points:
                element["points"] = element["points"][:remaining_points]
            total_points += len(element["points"])
            if not element["points"]:
                break

        strokes.append(element)

    raw_color = str(raw_payload.get("brushColor", "") or "").strip()
    return {
        "version": CREA_STORAGE_VERSION,
        "brushColor": raw_color if is_hex_color(raw_color) else "#005DA4",
        "brushSize": clamp_float(raw_payload.get("brushSize"), CREA_BRUSH_MIN, CREA_BRUSH_MAX),
        "eraserSize": clamp_float(raw_payload.get("eraserSize"), CREA_ERASER_MIN, CREA_ERASER_MAX),
        "strokes": strokes,
    }


def ensure_upload_size(raw_bytes: bytes) -> None:
    if len(raw_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="El archivo excede el tamano permitido")


def validate_upload_metadata(
    upload: UploadFile,
    *,
    allowed_extensions: set[str],
    allowed_content_types: set[str],
    detail: str,
) -> None:
    suffix = Path(upload.filename or "").suffix.lower()
    content_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
    if suffix not in allowed_extensions:
        raise HTTPException(status_code=400, detail=detail)
    if content_type and content_type not in allowed_content_types:
        raise HTTPException(status_code=400, detail=detail)


def validate_runtime_configuration(allowed_origins: list[str]) -> None:
    if APP_ENV != "production":
        return

    insecure_values: list[str] = []
    if admin_auth.ADMIN_PASSWORD_IS_IMPLICIT_DEFAULT:
        insecure_values.append("ADMIN_PASSWORD")
    if admin_auth.ADMIN_TOKEN_SECRET == "ce-iccd-admin-secret-change-me":
        insecure_values.append("ADMIN_TOKEN_SECRET")
    if student_auth.STUDENT_TOKEN_SECRET == "ce-iccd-student-secret-change-me":
        insecure_values.append("STUDENT_TOKEN_SECRET")
    if allowed_origins == ["*"]:
        insecure_values.append("CORS_ALLOW_ORIGINS")

    if insecure_values:
        raise RuntimeError(
            "Configuracion insegura para produccion. Revisa: "
            + ", ".join(insecure_values)
        )


def is_allowed_remote_host(host: str) -> bool:
    host_clean = host.strip().lower()
    if not host_clean:
        return False
    return any(
        host_clean == allowed_host or host_clean.endswith(f".{allowed_host}")
        for allowed_host in ALLOWED_REMOTE_IMAGE_HOSTS
    )


def metadata_to_public_item(data: dict[str, Any], folder_name: str) -> dict[str, str]:
    return {
        "id": data.get("id", folder_name),
        "title": data.get("title", "Proyecto"),
        "description": data.get("description", ""),
        "author_name": data.get("author_name", ""),
        "utem_email": data.get("utem_email", ""),
        "submission_type": data.get("submission_type", ""),
        "repo_url": data.get("repo_url", ""),
        "files_count": str(len(data.get("files", []))),
        "created_at": data.get("created_at", ""),
    }


def read_submission_metadata(metadata_path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def read_public_submissions() -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for metadata_path in SUBMISSIONS_DIR.glob("*/metadata.json"):
        data = read_submission_metadata(metadata_path)
        if not data:
            continue
        items.append(metadata_to_public_item(data, metadata_path.parent.name))

    items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return items


def get_submission_metadata_path(project_id: str) -> Path:
    candidate = (SUBMISSIONS_DIR / project_id / "metadata.json").resolve()
    if SUBMISSIONS_DIR.resolve() not in candidate.parents or not candidate.exists():
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return candidate


async def store_media_upload(upload: UploadFile, category: str, prefix: str) -> str:
    if not upload.filename:
        raise HTTPException(status_code=400, detail="Archivo invalido")

    folder_map = {
        "presentations": content_store.PRESENTATIONS_UPLOADS_DIR,
        "centers": content_store.CENTERS_UPLOADS_DIR,
        "alumni": content_store.ALUMNI_UPLOADS_DIR,
    }
    target_dir = folder_map[category]
    if category == "presentations":
        validate_upload_metadata(
            upload,
            allowed_extensions={".pdf"},
            allowed_content_types=PDF_CONTENT_TYPES,
            detail="Debes subir un archivo PDF valido",
        )
    else:
        validate_upload_metadata(
            upload,
            allowed_extensions=IMAGE_EXTENSIONS,
            allowed_content_types=IMAGE_CONTENT_TYPES,
            detail="Debes subir una imagen valida",
        )

    original_name = Path(upload.filename).name
    suffix = Path(original_name).suffix.lower() or ".bin"
    safe_stem = slugify(Path(original_name).stem or prefix)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    final_name = f"{slugify(prefix)}-{safe_stem}-{timestamp}{suffix}"
    target_path = target_dir / final_name
    content = await upload.read()
    ensure_upload_size(content)
    target_path.write_bytes(content)
    await upload.close()
    return content_store.build_media_url(category, final_name)


def remote_image_extension(url: str, content_type: str) -> str:
    guessed = mimetypes.guess_extension((content_type or "").split(";", 1)[0].strip())
    if guessed:
        return guessed

    suffix = Path(url.split("?", 1)[0]).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return suffix
    return ".jpg"


def store_remote_media(url: str, category: str, prefix: str) -> str:
    remote_url = sanitize_optional_text(url)
    if not remote_url.startswith(("http://", "https://")):
        return remote_url

    parsed_url = urlparse(remote_url)
    host = parsed_url.hostname.lower() if parsed_url.hostname else ""
    if not is_allowed_remote_host(host):
        return remote_url

    try:
        response = requests.get(
            remote_url,
            timeout=REQUEST_TIMEOUT_S,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            },
        )
    except requests.RequestException:
        return remote_url

    if response.status_code >= 400:
        return remote_url

    content_type = response.headers.get("content-type", "")
    if not content_type.lower().startswith("image/"):
        return remote_url
    ensure_upload_size(response.content)

    folder_map = {
        "presentations": content_store.PRESENTATIONS_UPLOADS_DIR,
        "centers": content_store.CENTERS_UPLOADS_DIR,
        "alumni": content_store.ALUMNI_UPLOADS_DIR,
    }
    target_dir = folder_map[category]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    extension = remote_image_extension(remote_url, content_type)
    final_name = f"{slugify(prefix)}-remote-{timestamp}{extension}"
    target_path = target_dir / final_name
    target_path.write_bytes(response.content)
    return content_store.build_media_url(category, final_name)


def delete_media_asset(media_url: str) -> None:
    if not media_url.startswith("/media/"):
        return

    relative_path = Path(media_url.removeprefix("/media/"))
    target_path = (content_store.UPLOADS_DIR / relative_path).resolve()
    uploads_root = content_store.UPLOADS_DIR.resolve()
    if target_path == uploads_root or uploads_root not in target_path.parents:
        return
    if target_path.exists() and target_path.is_file():
        target_path.unlink()


def require_admin(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sesion de administrador requerida")

    token = authorization.split(" ", 1)[1].strip()
    payload = admin_auth.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token de administrador invalido o expirado")
    return payload


def require_student(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sesion de estudiante requerida")

    token = authorization.split(" ", 1)[1].strip()
    payload = student_auth.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token de estudiante invalido o expirado")
    return payload


def require_editor(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Debes iniciar sesion para editar la pizarra")

    token = authorization.split(" ", 1)[1].strip()
    student_payload = student_auth.verify_token(token)
    if student_payload:
        return {
            "role": "student",
            "sub": str(student_payload.get("sub", "")),
            "name": str(student_payload.get("name", "")),
        }

    admin_payload = admin_auth.verify_token(token)
    if admin_payload:
        return {
            "role": "admin",
            "sub": str(admin_payload.get("sub", "")),
            "name": str(admin_payload.get("sub", "")),
        }

    raise HTTPException(status_code=401, detail="Sesion invalida o expirada")


def sort_centers(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            0 if item.get("is_active") else 1,
            item.get("created_at", ""),
        ),
    )


def sort_presentations(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: item.get("created_at", ""), reverse=True)


def sort_alumni(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            -(int(item.get("graduation_year", 0) or 0)),
            item.get("created_at", ""),
            item.get("full_name", "").lower(),
        ),
    )


def find_center(data: dict[str, Any], center_id: str) -> tuple[int, dict[str, Any]]:
    for index, item in enumerate(data.get("items", [])):
        if item.get("id") == center_id:
            return index, item
    raise HTTPException(status_code=404, detail="Centro no encontrado")


def find_member(center: dict[str, Any], member_id: str) -> tuple[int, dict[str, Any]]:
    for index, item in enumerate(center.get("members", [])):
        if item.get("id") == member_id:
            return index, item
    raise HTTPException(status_code=404, detail="Integrante no encontrado")


def find_alumni(data: dict[str, Any], alumni_id: str) -> tuple[int, dict[str, Any]]:
    for index, item in enumerate(data.get("items", [])):
        if item.get("id") == alumni_id:
            return index, item
    raise HTTPException(status_code=404, detail="Persona no encontrada")


def ensure_single_active_center(data: dict[str, Any], active_id: str | None) -> None:
    for center in data.get("items", []):
        center["is_active"] = center.get("id") == active_id if active_id else False


def extract_meta_value(html_text: str, key: str) -> str:
    for pattern in (META_TAG_PATTERN, META_TAG_REVERSED_PATTERN):
        for match in pattern.finditer(html_text):
            if match.group("key").strip().lower() == key.lower():
                return html.unescape(match.group("content").strip())
    return ""


def extract_title(html_text: str) -> str:
    match = TITLE_TAG_PATTERN.search(html_text)
    if not match:
        return ""
    return html.unescape(TAG_PATTERN.sub("", match.group("title"))).strip()


def collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_og_title(raw_title: str) -> dict[str, str]:
    clean_title = collapse_whitespace(raw_title.replace("| LinkedIn", ""))
    parts = [part.strip() for part in clean_title.split(" - ") if part.strip()]
    parsed = {"full_name": "", "headline": "", "company": ""}
    if not parts:
        return parsed

    parsed["full_name"] = parts[0]
    if len(parts) == 2:
        parsed["headline"] = parts[1]
    elif len(parts) >= 3:
        parsed["headline"] = " - ".join(parts[1:-1])
        parsed["company"] = parts[-1]
    return parsed


def extract_json_ld_person(html_text: str) -> dict[str, str]:
    for match in JSON_LD_PATTERN.finditer(html_text):
        raw_payload = match.group("payload").strip()
        if not raw_payload:
            continue
        try:
            data = json.loads(raw_payload)
        except Exception:
            continue

        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("@type", "")).lower()
            if "person" not in item_type:
                continue

            works_for = item.get("worksFor")
            company = ""
            if isinstance(works_for, dict):
                company = sanitize_optional_text(str(works_for.get("name", "")))

            address = item.get("address")
            location = ""
            if isinstance(address, dict):
                location = sanitize_optional_text(
                    str(address.get("addressLocality", "") or address.get("addressRegion", ""))
                )

            image_url = ""
            image_value = item.get("image")
            if isinstance(image_value, dict):
                image_url = sanitize_optional_text(str(image_value.get("url", "")))
            elif isinstance(image_value, str):
                image_url = sanitize_optional_text(image_value)

            return {
                "full_name": sanitize_optional_text(str(item.get("name", ""))),
                "headline": sanitize_optional_text(str(item.get("jobTitle", ""))),
                "company": company,
                "summary": sanitize_optional_text(str(item.get("description", ""))),
                "location": location,
                "image_url": image_url,
            }
    return {
        "full_name": "",
        "headline": "",
        "company": "",
        "summary": "",
        "location": "",
        "image_url": "",
    }


def fetch_linkedin_preview(url: str) -> dict[str, str]:
    linkedin_url = sanitize_optional_text(url)
    if not LINKEDIN_URL_PATTERN.match(linkedin_url):
        raise HTTPException(status_code=400, detail="Debes ingresar un enlace de LinkedIn valido")

    try:
        response = requests.get(
            linkedin_url,
            timeout=REQUEST_TIMEOUT_S,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
            },
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="No se pudo consultar LinkedIn") from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="LinkedIn no devolvio un perfil accesible")

    html_text = response.text
    og_title = extract_meta_value(html_text, "og:title")
    og_description = extract_meta_value(html_text, "og:description")
    og_image = extract_meta_value(html_text, "og:image")
    twitter_image = extract_meta_value(html_text, "twitter:image")
    title_text = extract_title(html_text)
    ld_person = extract_json_ld_person(html_text)
    title_bits = parse_og_title(og_title or title_text)

    preview = {
        "linkedin_url": linkedin_url,
        "full_name": ld_person["full_name"] or title_bits["full_name"],
        "headline": ld_person["headline"] or title_bits["headline"],
        "company": ld_person["company"] or title_bits["company"],
        "location": ld_person["location"],
        "summary": ld_person["summary"] or collapse_whitespace(og_description),
        "image_url": og_image or twitter_image or ld_person["image_url"],
    }

    if not any(
        [
            preview["full_name"],
            preview["headline"],
            preview["company"],
            preview["summary"],
        ]
    ):
        raise HTTPException(
            status_code=422,
            detail="No se pudo extraer informacion publica del perfil. Completa los datos manualmente.",
        )

    if preview["full_name"].lower().startswith("linkedin"):
        raise HTTPException(
            status_code=422,
            detail="LinkedIn devolvio una pagina generica. Revisa que el perfil sea publico.",
        )

    return preview


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[Message] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class AdminLoginResponse(BaseModel):
    token: str
    email: str


class StudentRegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class StudentLoginRequest(BaseModel):
    email: str
    password: str


class StudentAuthResponse(BaseModel):
    token: str
    email: str
    name: str


class ProjectUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    author_name: str | None = None
    utem_email: str | None = None
    repo_url: str | None = None


class LinkedInPreviewRequest(BaseModel):
    url: str


class AlumniIntroUpdateRequest(BaseModel):
    intro: str


class SharedBoardUpdateRequest(BaseModel):
    version: int = Field(default=CREA_STORAGE_VERSION)
    brushColor: str = Field(default="#005DA4")
    brushSize: float = Field(default=8)
    eraserSize: float = Field(default=240)
    strokes: list[dict[str, Any]] = Field(default_factory=list)


app = FastAPI(title="Chatbot CE ICCD UTEM")

allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
    if origin.strip()
]
validate_runtime_configuration(allowed_origins)

trusted_hosts = TRUSTED_HOSTS or ["localhost", "127.0.0.1"]
if "*" not in trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def harden_http(request: Request, call_next) -> Response:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_REQUEST_SIZE_BYTES:
                raise HTTPException(status_code=413, detail="La solicitud excede el tamano permitido")
        except ValueError:
            pass

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-site"
    csp_value = (
        "default-src 'self'; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline' https:; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; "
        "font-src 'self' data: https:; "
        "connect-src 'self' https: http:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    response.headers["Content-Security-Policy"] = csp_value
    if APP_ENV == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.mount("/media", StaticFiles(directory=content_store.UPLOADS_DIR), name="media")

index = None
meta = None
texts = None

if chatbot is not None:
    try:
        index, meta, texts = chatbot.load_store()
    except Exception as exc:
        chatbot = None
        chatbot_import_error = str(exc)


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    if chatbot is None or index is None or meta is None or texts is None:
        detail = "Chatbot no disponible en este entorno."
        if chatbot_import_error:
            detail = f"{detail} {chatbot_import_error}"
        raise HTTPException(status_code=503, detail=detail)

    history_dicts: List[Dict[str, str]] = [
        {"role": m.role, "content": m.content} for m in payload.history
    ]

    reply = chatbot.answer(
        user_msg=payload.message,
        history=history_dicts,
        index=index,
        meta=meta,
        texts=texts,
    )

    return ChatResponse(reply=reply)


@app.get("/projects/public")
def list_public_projects() -> Dict[str, List[Dict[str, str]]]:
    return {"items": read_public_submissions()}


@app.post("/projects/submit")
async def submit_project(
    nombre: str = Form(...),
    correo_utem: str = Form(...),
    titulo: str = Form(...),
    descripcion: str = Form(""),
    tipo_envio: str = Form(...),
    repo_url: str = Form(""),
    files: List[UploadFile] | None = File(default=None),
) -> Dict[str, str]:
    name_clean = nombre.strip()
    title_clean = titulo.strip()
    description_clean = descripcion.strip()
    email_clean = ensure_utem_email(correo_utem)
    kind = tipo_envio.strip().lower()
    repo_clean = repo_url.strip()

    if not name_clean:
        raise HTTPException(status_code=400, detail="Nombre es obligatorio")
    if not title_clean:
        raise HTTPException(status_code=400, detail="Titulo es obligatorio")
    if kind not in {"repo", "carpeta"}:
        raise HTTPException(status_code=400, detail="tipo_envio invalido")
    if kind == "repo" and not repo_clean:
        raise HTTPException(status_code=400, detail="Debes incluir URL del repositorio")

    uploads = files or []
    if kind == "carpeta" and len(uploads) == 0:
        raise HTTPException(status_code=400, detail="Debes adjuntar una carpeta")

    submission_id = build_submission_id(title_clean)
    submission_dir = SUBMISSIONS_DIR / submission_id
    suffix = 1
    while submission_dir.exists():
        submission_dir = SUBMISSIONS_DIR / f"{submission_id}-{suffix}"
        suffix += 1
    submission_dir.mkdir(parents=True, exist_ok=False)

    saved_files: List[str] = []
    for upload in uploads:
        if not upload.filename:
            continue

        relative_path = safe_relative_path(upload.filename)
        target_path = (submission_dir / relative_path).resolve()
        if submission_dir.resolve() not in target_path.parents:
            relative_path = Path(relative_path.name)
            target_path = (submission_dir / relative_path).resolve()

        target_path.parent.mkdir(parents=True, exist_ok=True)
        content = await upload.read()
        target_path.write_bytes(content)
        saved_files.append(str(relative_path).replace("\\", "/"))
        await upload.close()

    metadata = {
        "id": submission_dir.name,
        "author_name": name_clean,
        "utem_email": email_clean,
        "title": title_clean,
        "description": description_clean,
        "submission_type": kind,
        "repo_url": repo_clean if kind == "repo" else "",
        "files": saved_files,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    (submission_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "ok": "true",
        "message": "Proyecto enviado correctamente",
        "id": submission_dir.name,
    }


@app.get("/content/centers")
def get_centers() -> dict[str, Any]:
    data = content_store.load_centers()
    return {"items": sort_centers(data.get("items", []))}


@app.get("/content/presentations")
def get_presentations() -> dict[str, Any]:
    data = content_store.load_presentations()
    return {"items": sort_presentations(data.get("items", []))}


@app.get("/content/alumni-wall")
def get_alumni_wall() -> dict[str, Any]:
    data = content_store.load_alumni_wall()
    return {
        "intro": data.get("intro", ""),
        "items": sort_alumni(data.get("items", [])),
    }


@app.get("/crea/board")
def get_shared_crea_board() -> dict[str, Any]:
    return content_store.load_shared_board()


@app.put("/crea/board")
def update_shared_crea_board(
    payload: SharedBoardUpdateRequest,
    editor: dict[str, Any] = Depends(require_editor),
) -> dict[str, Any]:
    sanitized_payload = sanitize_crea_board_payload(model_to_dict(payload))
    updated_by = str(editor.get("name") or editor.get("sub") or "").strip()
    return content_store.save_shared_board(sanitized_payload, updated_by=updated_by)


@app.post("/auth/register", response_model=StudentAuthResponse)
def register_student(payload: StudentRegisterRequest) -> StudentAuthResponse:
    email_clean = ensure_utem_email(payload.email)
    try:
        user = student_auth.create_user(payload.name, email_clean, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token = student_auth.create_token(user["email"], user["name"])
    return StudentAuthResponse(
        token=token,
        email=user["email"],
        name=user["name"],
    )


@app.post("/auth/login", response_model=StudentAuthResponse)
def login_student(payload: StudentLoginRequest) -> StudentAuthResponse:
    email_clean = ensure_utem_email(payload.email)
    user = student_auth.verify_credentials(email_clean, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Correo o clave invalidos")

    token = student_auth.create_token(user["email"], user["name"])
    return StudentAuthResponse(
        token=token,
        email=user["email"],
        name=user["name"],
    )


@app.get("/auth/me")
def student_me(student: dict[str, Any] = Depends(require_student)) -> dict[str, str]:
    return {
        "email": str(student.get("sub", "")),
        "name": str(student.get("name", "")),
    }


@app.post("/admin/login", response_model=AdminLoginResponse)
def admin_login(payload: AdminLoginRequest) -> AdminLoginResponse:
    if not admin_auth.verify_credentials(payload.email, payload.password):
        raise HTTPException(status_code=401, detail="Credenciales invalidas")
    token = admin_auth.create_token(payload.email)
    return AdminLoginResponse(token=token, email=payload.email.strip().lower())


@app.get("/admin/me")
def admin_me(admin: dict[str, Any] = Depends(require_admin)) -> dict[str, str]:
    return {"email": str(admin.get("sub", ""))}


@app.patch("/admin/projects/{project_id}")
def update_project(
    project_id: str,
    payload: ProjectUpdateRequest,
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    metadata_path = get_submission_metadata_path(project_id)
    metadata = read_submission_metadata(metadata_path)
    if not metadata:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    if payload.title is not None:
        title_clean = payload.title.strip()
        if not title_clean:
            raise HTTPException(status_code=400, detail="Titulo es obligatorio")
        metadata["title"] = title_clean
    if payload.description is not None:
        metadata["description"] = payload.description.strip()
    if payload.author_name is not None:
        author_clean = payload.author_name.strip()
        if not author_clean:
            raise HTTPException(status_code=400, detail="Nombre del autor es obligatorio")
        metadata["author_name"] = author_clean
    if payload.utem_email is not None:
        metadata["utem_email"] = ensure_utem_email(payload.utem_email)
    if payload.repo_url is not None:
        metadata["repo_url"] = payload.repo_url.strip()

    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {"item": metadata_to_public_item(metadata, metadata_path.parent.name)}


@app.delete("/admin/projects/{project_id}")
def delete_project(
    project_id: str,
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, str]:
    metadata_path = get_submission_metadata_path(project_id)
    shutil.rmtree(metadata_path.parent)
    return {"ok": "true"}


@app.get("/admin/centers")
def admin_list_centers(admin: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    data = content_store.load_centers()
    return {"items": sort_centers(data.get("items", []))}


@app.post("/admin/centers")
def create_center(
    name: str = Form(...),
    period_label: str = Form(...),
    description: str = Form(""),
    is_active: str = Form("false"),
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    name_clean = name.strip()
    period_clean = period_label.strip()
    if not name_clean or not period_clean:
        raise HTTPException(status_code=400, detail="Nombre y periodo son obligatorios")

    data = content_store.load_centers()
    existing_ids = {item.get("id", "") for item in data.get("items", [])}
    center_id = content_store.unique_slug(f"{name_clean}-{period_clean}", existing_ids)

    center = {
        "id": center_id,
        "name": name_clean,
        "period_label": period_clean,
        "description": description.strip(),
        "is_active": parse_bool(is_active),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "members": [],
    }
    data.setdefault("items", []).append(center)

    if center["is_active"]:
        ensure_single_active_center(data, center_id)

    content_store.save_centers(data)
    return {"item": center}


@app.put("/admin/centers/{center_id}")
def update_center(
    center_id: str,
    name: str = Form(...),
    period_label: str = Form(...),
    description: str = Form(""),
    is_active: str = Form("false"),
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    data = content_store.load_centers()
    index, center = find_center(data, center_id)

    name_clean = name.strip()
    period_clean = period_label.strip()
    if not name_clean or not period_clean:
        raise HTTPException(status_code=400, detail="Nombre y periodo son obligatorios")

    center["name"] = name_clean
    center["period_label"] = period_clean
    center["description"] = description.strip()
    center["is_active"] = parse_bool(is_active)
    data["items"][index] = center

    if center["is_active"]:
        ensure_single_active_center(data, center_id)

    content_store.save_centers(data)
    return {"item": center}


@app.delete("/admin/centers/{center_id}")
def delete_center(
    center_id: str,
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, str]:
    data = content_store.load_centers()
    index, center = find_center(data, center_id)

    for member in center.get("members", []):
        delete_media_asset(member.get("image_url", ""))

    data["items"].pop(index)
    if data["items"] and not any(item.get("is_active") for item in data["items"]):
        data["items"][0]["is_active"] = True

    content_store.save_centers(data)
    return {"ok": "true"}


@app.post("/admin/centers/{center_id}/members")
async def create_member(
    center_id: str,
    name: str = Form(...),
    role: str = Form(...),
    bio: str = Form(""),
    linkedin_url: str = Form(""),
    image: UploadFile | None = File(default=None),
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    name_clean = name.strip()
    role_clean = role.strip()
    if not name_clean or not role_clean:
        raise HTTPException(status_code=400, detail="Nombre y cargo son obligatorios")

    data = content_store.load_centers()
    _, center = find_center(data, center_id)
    existing_ids = {member.get("id", "") for member in center.get("members", [])}
    member_id = content_store.unique_slug(name_clean, existing_ids)

    image_url = ""
    if image and image.filename:
        image_url = await store_media_upload(image, "centers", member_id)

    member = {
        "id": member_id,
        "name": name_clean,
        "role": role_clean,
        "bio": bio.strip(),
        "linkedin_url": linkedin_url.strip(),
        "image_url": image_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    center.setdefault("members", []).append(member)
    content_store.save_centers(data)
    return {"item": member}


@app.put("/admin/centers/{center_id}/members/{member_id}")
async def update_member(
    center_id: str,
    member_id: str,
    name: str = Form(...),
    role: str = Form(...),
    bio: str = Form(""),
    linkedin_url: str = Form(""),
    image: UploadFile | None = File(default=None),
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    name_clean = name.strip()
    role_clean = role.strip()
    if not name_clean or not role_clean:
        raise HTTPException(status_code=400, detail="Nombre y cargo son obligatorios")

    data = content_store.load_centers()
    _, center = find_center(data, center_id)
    member_index, member = find_member(center, member_id)

    if image and image.filename:
        delete_media_asset(member.get("image_url", ""))
        member["image_url"] = await store_media_upload(image, "centers", member_id)

    member["name"] = name_clean
    member["role"] = role_clean
    member["bio"] = bio.strip()
    member["linkedin_url"] = linkedin_url.strip()
    center["members"][member_index] = member

    content_store.save_centers(data)
    return {"item": member}


@app.delete("/admin/centers/{center_id}/members/{member_id}")
def delete_member(
    center_id: str,
    member_id: str,
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, str]:
    data = content_store.load_centers()
    _, center = find_center(data, center_id)
    member_index, member = find_member(center, member_id)
    delete_media_asset(member.get("image_url", ""))
    center["members"].pop(member_index)
    content_store.save_centers(data)
    return {"ok": "true"}


@app.get("/admin/presentations")
def admin_list_presentations(admin: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    data = content_store.load_presentations()
    return {"items": sort_presentations(data.get("items", []))}


@app.post("/admin/presentations")
async def create_presentation(
    title: str = Form(""),
    description: str = Form(""),
    pdf: UploadFile = File(...),
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    if not pdf.filename or Path(pdf.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Debes subir un archivo PDF")

    data = content_store.load_presentations()
    existing_ids = {item.get("id", "") for item in data.get("items", [])}
    base_title = title.strip() or content_store.normalize_presentation_name(pdf.filename)
    item_id = content_store.unique_slug(base_title, existing_ids)
    pdf_url = await store_media_upload(pdf, "presentations", item_id)

    item = {
        "id": item_id,
        "title": base_title,
        "description": description.strip() or "Documento PDF disponible para presentacion.",
        "pdf_url": pdf_url,
        "storage": "media",
        "file_name": Path(pdf_url).name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    data.setdefault("items", []).append(item)
    content_store.save_presentations(data)
    return {"item": item}


@app.delete("/admin/presentations/{presentation_id}")
def delete_presentation(
    presentation_id: str,
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, str]:
    data = content_store.load_presentations()
    for index, item in enumerate(data.get("items", [])):
        if item.get("id") == presentation_id:
            delete_media_asset(item.get("pdf_url", ""))
            data["items"].pop(index)
            content_store.save_presentations(data)
            return {"ok": "true"}
    raise HTTPException(status_code=404, detail="Presentacion no encontrada")


@app.get("/admin/alumni")
def admin_list_alumni(admin: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    data = content_store.load_alumni_wall()
    return {
        "intro": data.get("intro", ""),
        "items": sort_alumni(data.get("items", [])),
    }


@app.put("/admin/alumni/intro")
def update_alumni_intro(
    payload: AlumniIntroUpdateRequest,
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, str]:
    data = content_store.load_alumni_wall()
    data["intro"] = payload.intro.strip()
    content_store.save_alumni_wall(data)
    return {"intro": data["intro"]}


@app.post("/admin/alumni/preview-linkedin")
def preview_linkedin(
    payload: LinkedInPreviewRequest,
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    return {"item": fetch_linkedin_preview(payload.url)}


@app.post("/admin/alumni")
async def create_alumni(
    full_name: str = Form(""),
    summary: str = Form(""),
    graduation_year: int = Form(...),
    linkedin_url: str = Form(""),
    image_url: str = Form(""),
    image: UploadFile | None = File(default=None),
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    data = content_store.load_alumni_wall()
    preview: dict[str, str] = {}
    linkedin_url_clean = linkedin_url.strip()
    if linkedin_url_clean:
        try:
            preview = fetch_linkedin_preview(linkedin_url_clean)
        except HTTPException:
            preview = {}

    resolved_name = full_name.strip() or preview.get("full_name", "")
    if not resolved_name:
        raise HTTPException(status_code=400, detail="Nombre es obligatorio")

    existing_ids = {item.get("id", "") for item in data.get("items", [])}
    alumni_id = content_store.unique_slug(resolved_name, existing_ids)
    resolved_image_url = image_url.strip() or preview.get("image_url", "")
    if image and image.filename:
        resolved_image_url = await store_media_upload(image, "alumni", alumni_id)
    elif resolved_image_url.startswith(("http://", "https://")):
        resolved_image_url = store_remote_media(resolved_image_url, "alumni", alumni_id)

    item = {
        "id": alumni_id,
        "full_name": resolved_name,
        "summary": summary.strip() or preview.get("summary", ""),
        "graduation_year": parse_year(graduation_year),
        "linkedin_url": linkedin_url_clean,
        "image_url": resolved_image_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    data.setdefault("items", []).append(item)
    content_store.save_alumni_wall(data)
    return {"item": item}


@app.put("/admin/alumni/{alumni_id}")
async def update_alumni(
    alumni_id: str,
    full_name: str = Form(...),
    summary: str = Form(""),
    graduation_year: int = Form(...),
    linkedin_url: str = Form(""),
    image_url: str = Form(""),
    image: UploadFile | None = File(default=None),
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    full_name_clean = full_name.strip()
    if not full_name_clean:
        raise HTTPException(status_code=400, detail="Nombre es obligatorio")

    data = content_store.load_alumni_wall()
    item_index, item = find_alumni(data, alumni_id)
    linkedin_url_clean = linkedin_url.strip()
    preview: dict[str, str] = {}
    if linkedin_url_clean:
        try:
            preview = fetch_linkedin_preview(linkedin_url_clean)
        except HTTPException:
            preview = {}

    resolved_image_url = image_url.strip() or item.get("image_url", "") or preview.get("image_url", "")
    if image and image.filename:
        delete_media_asset(item.get("image_url", ""))
        resolved_image_url = await store_media_upload(image, "alumni", alumni_id)
    elif resolved_image_url.startswith(("http://", "https://")):
        if item.get("image_url", "").startswith("/media/") and item.get("image_url", "") != resolved_image_url:
            delete_media_asset(item.get("image_url", ""))
        resolved_image_url = store_remote_media(resolved_image_url, "alumni", alumni_id)
    elif not resolved_image_url:
        resolved_image_url = item.get("image_url", "")

    item.update(
        {
            "full_name": full_name_clean,
            "summary": summary.strip() or preview.get("summary", ""),
            "graduation_year": parse_year(graduation_year),
            "linkedin_url": linkedin_url_clean,
            "image_url": resolved_image_url,
        }
    )
    data["items"][item_index] = item
    content_store.save_alumni_wall(data)
    return {"item": item}


@app.delete("/admin/alumni/{alumni_id}")
def delete_alumni(
    alumni_id: str,
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, str]:
    data = content_store.load_alumni_wall()
    item_index, item = find_alumni(data, alumni_id)
    delete_media_asset(item.get("image_url", ""))
    data["items"].pop(item_index)
    content_store.save_alumni_wall(data)
    return {"ok": "true"}


@app.get("/media-db/alumni/{alumni_id}")
def get_alumni_image_from_db(alumni_id: str) -> Response:
    with db.SessionLocal() as session:
        item = session.get(models.AlumniProfile, alumni_id)
        if item is None or item.image_blob is None:
            raise HTTPException(status_code=404, detail="Imagen no encontrada")

        return Response(
            content=item.image_blob,
            media_type=item.image_content_type or "image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )


@app.get("/health")
def health() -> Dict[str, str]:
    return {
        "status": "ok",
        "chatbot": "ok" if chatbot is not None and index is not None else "unavailable",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, reload=True)
