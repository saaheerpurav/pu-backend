create extension if not exists pgcrypto;

create table if not exists public.users (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    phone text,
    blood_group text,
    allergies text,
    emergency_contact text,
    role text not null default 'citizen',
    created_at timestamptz not null default now()
);

create table if not exists public.incidents (
    id uuid primary key default gen_random_uuid(),
    user_id uuid,
    type text not null,
    source text not null,
    status text not null default 'pending',
    priority text not null default 'medium',
    latitude double precision not null,
    longitude double precision not null,
    created_at timestamptz not null default now(),
    resolved_at timestamptz
);

alter table public.incidents
    add column if not exists context jsonb,
    add column if not exists dedupe_key text;

create table if not exists public.responders (
    id uuid primary key default gen_random_uuid(),
    name text not null default 'Responder',
    type text not null default 'ambulance',
    phone text,
    availability text not null default 'ready',
    latitude double precision not null,
    longitude double precision not null,
    current_status text not null default 'Idle',
    eta_minutes integer not null default 0,
    updated_at timestamptz not null default now()
);

create table if not exists public.responder_locations (
    id uuid primary key default gen_random_uuid(),
    responder_id uuid not null references public.responders(id) on delete cascade,
    latitude double precision not null,
    longitude double precision not null,
    speed_kmph double precision,
    captured_at timestamptz not null default now()
);

alter table public.responders
    add column if not exists availability text not null default 'ready';

create table if not exists public.assignments (
    id uuid primary key default gen_random_uuid(),
    incident_id uuid not null references public.incidents(id) on delete cascade,
    responder_id uuid not null references public.responders(id) on delete cascade,
    eta text not null,
    status text not null default 'assigned',
    created_at timestamptz not null default now()
);

create table if not exists public.chatbot_logs (
    id uuid primary key default gen_random_uuid(),
    message text not null,
    response text not null,
    created_at timestamptz not null default now()
);

create table if not exists public.incident_assignments (
    id uuid primary key default gen_random_uuid(),
    incident_id uuid not null references public.incidents(id) on delete cascade,
    responder_id uuid not null references public.responders(id) on delete cascade,
    assigned_by uuid,
    assigned_at timestamptz not null default now(),
    eta_minutes integer,
    note text
);

create table if not exists public.nfc_card_scans (
    id uuid primary key default gen_random_uuid(),
    card_user_id uuid not null,
    scanned_at timestamptz not null default now()
);

alter table public.nfc_card_scans
    add column if not exists tag_payload jsonb,
    add column if not exists reader_context jsonb,
    add column if not exists reader_context_error text,
    add column if not exists profile_snapshot jsonb,
    add column if not exists profile_fetch_error text,
    add column if not exists scanner_user_id uuid;

create table if not exists public.devices (
    id uuid primary key default gen_random_uuid(),
    user_id uuid,
    device_type text not null,
    device_id text not null,
    platform text,
    push_token text,
    last_seen_at timestamptz not null default now()
);

create table if not exists public.wearable_events (
    id uuid primary key default gen_random_uuid(),
    user_id uuid,
    device_id text,
    event_type text not null,
    payload_json jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.whatsapp_sessions (
    phone text primary key,
    last_intent text,
    last_severity text,
    last_interaction_at timestamptz not null default now()
);

create table if not exists public.ai_logs (
    id uuid primary key default gen_random_uuid(),
    feature text not null,
    model text not null,
    prompt_version text not null,
    latency_ms integer not null,
    confidence numeric(5,3) not null,
    escalation boolean not null,
    language_code text,
    message_hash text,
    created_at timestamptz not null default now()
);

create table if not exists public.audit_logs (
    id uuid primary key default gen_random_uuid(),
    actor_user_id uuid,
    action text not null,
    resource_type text,
    resource_id uuid,
    metadata jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_incidents_status_created_at on public.incidents(status, created_at desc);
create index if not exists idx_incidents_location on public.incidents (latitude, longitude);
do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'incidents' and column_name = 'dedupe_key'
  ) then
    create index if not exists idx_incidents_dedupe_key on public.incidents(dedupe_key);
  end if;
end;
$$;
create index if not exists idx_responders_availability_type on public.responders(availability, type);
create index if not exists idx_responders_location on public.responders (latitude, longitude);
create index if not exists idx_wearable_events_user_created on public.wearable_events(user_id, created_at desc);
