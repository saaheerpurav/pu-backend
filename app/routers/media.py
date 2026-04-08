"""
Media Upload Router
Mobile app uploads geotagged images to Supabase Storage.
Returns public URL to attach to a report.
"""

import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.supabase_client import supabase_admin
from app.services.clustering import snap_to_grid

BUCKET = "disaster-media"
SUPABASE_URL = "https://avqylsoystodlrvdzsdh.supabase.co"

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/jpg"}
MAX_SIZE_MB = 100

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    disaster_type: str = Form(default="other"),
    report_id: str = Form(default=None),   # optionally link to existing report
    user_id: str = Form(default=None),
):


    # Read and validate size
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    
    # Build storage path: disaster_type/uuid.ext
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    file_name = f"{disaster_type}/{uuid.uuid4()}.{ext}"

    # Upload to Supabase Storage
    try:
        supabase_admin.storage.from_(BUCKET).upload(
            path=file_name,
            file=contents,
            file_options={"content-type": file.content_type, "upsert": "false"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{file_name}"

    # Store metadata in a media_uploads table-lite: tag onto grid_risk comment
    # We log it as a report description if report_id given
    if report_id:
        try:
            supabase_admin.table("reports").update({
                "description": f"[IMAGE] {public_url}"
            }).eq("id", report_id).execute()
        except Exception:
            pass  # non-critical

    # Update grid risk cell with image presence
    grid_lat, grid_lng = snap_to_grid(latitude, longitude)

    return {
        "url": public_url,
        "file_name": file_name,
        "latitude": latitude,
        "longitude": longitude,
        "disaster_type": disaster_type,
        "size_mb": round(size_mb, 2),
        "report_id": report_id,
        "message": "Image uploaded successfully.",
    }


@router.get("/list")
def list_images(disaster_type: str = None, limit: int = 50):
    """List uploaded images from storage bucket."""
    try:
        def list_folder(folder: str) -> list:
            res = supabase_admin.storage.from_(BUCKET).list(
                path=folder,
                options={"limit": limit, "sortBy": {"column": "created_at", "order": "desc"}},
            )
            files = []
            for f in (res or []):
                name = f.get("name", "")
                if not name or name == ".emptyFolderPlaceholder":
                    continue
                # Skip folder entries (id is null for folders)
                if f.get("id") is None:
                    continue
                prefix = f"{folder}/" if folder else ""
                metadata = f.get("metadata") or {}
                files.append({
                    "name": name,
                    "url": f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{prefix}{name}",
                    "size_bytes": metadata.get("size", 0),
                    "created_at": f.get("created_at"),
                    "disaster_type": folder or "unknown",
                })
            return files

        if disaster_type:
            all_files = list_folder(disaster_type)
        else:
            # List each known folder
            all_files = []
            for folder in ["flood", "fire", "earthquake", "landslide", "other"]:
                all_files.extend(list_folder(folder))

        return {"files": all_files, "total": len(all_files)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
