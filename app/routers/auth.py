from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from app.supabase_client import supabase_anon, supabase_admin

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "citizen"   # citizen | authority
    phone: str = None
    blood_group: str | None = None
    allergies: str | None = None
    emergency_contact: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/signup")
def signup(body: SignupRequest):
    # 1. Create user in Supabase Auth
    try:
        res = supabase_anon.auth.sign_up({
            "email": body.email,
            "password": body.password,
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not res.user:
        raise HTTPException(status_code=400, detail="Signup failed")

    user_id = res.user.id

    # 2. Insert profile row
    supabase_admin.table("profiles").insert({
        "id": user_id,
        "name": body.name,
        "role": body.role,
        "phone": body.phone,
    }).execute()

    supabase_admin.table("users").insert({
        "id": user_id,
        "name": body.name,
        "phone": body.phone,
        "blood_group": body.blood_group,
        "allergies": body.allergies,
        "emergency_contact": body.emergency_contact,
        "role": body.role,
    }).execute()

    return {
        "message": "Signup successful",
        "user_id": user_id,
        "role": body.role,
        "access_token": res.session.access_token if res.session else None,
    }


@router.post("/login")
def login(body: LoginRequest):
    try:
        res = supabase_anon.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password,
        })
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

    if not res.user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Fetch app profile for role and metadata
    profile = supabase_admin.table("users").select("*").eq("id", res.user.id).single().execute()

    return {
        "access_token": res.session.access_token,
        "user_id": res.user.id,
        "email": res.user.email,
        "role": profile.data.get("role") if profile.data else "citizen",
        "profile": profile.data,
    }


@router.post("/logout")
def logout():
    supabase_anon.auth.sign_out()
    return {"message": "Logged out"}


# ─────────────────────────────────────────
# Phone OTP (for mobile app)
# ─────────────────────────────────────────

class PhoneSendRequest(BaseModel):
    phone: str   # E.164 format e.g. +919876543210


class PhoneVerifyRequest(BaseModel):
    phone: str
    otp: str
    name: str = None   # only needed on first login (auto-registers citizen)


@router.post("/phone/send-otp")
def phone_send_otp(body: PhoneSendRequest):
    try:
        supabase_anon.auth.sign_in_with_otp({"phone": body.phone})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": f"OTP sent to {body.phone}"}


@router.post("/phone/verify-otp")
def phone_verify_otp(body: PhoneVerifyRequest):
    try:
        res = supabase_anon.auth.verify_otp({
            "phone": body.phone,
            "token": body.otp,
            "type": "sms",
        })
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

    if not res.user:
        raise HTTPException(status_code=401, detail="Invalid OTP")

    user_id = res.user.id

    # Upsert profile — creates on first login, no-op on subsequent
    existing = supabase_admin.table("profiles").select("id, role").eq("id", user_id).execute()
    if not existing.data:
        supabase_admin.table("profiles").insert({
            "id": user_id,
            "name": body.name or body.phone,
            "role": "citizen",
            "phone": body.phone,
        }).execute()
        role = "citizen"
    else:
        role = existing.data[0].get("role", "citizen")

    supabase_admin.table("users").upsert({
        "id": user_id,
        "name": body.name or body.phone,
        "phone": body.phone,
        "role": role,
    }, on_conflict="id").execute()

    return {
        "access_token": res.session.access_token,
        "user_id": user_id,
        "phone": body.phone,
        "role": role,
    }
