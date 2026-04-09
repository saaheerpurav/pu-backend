from app.supabase_client import supabase_admin
print(supabase_admin.storage.list_buckets())
