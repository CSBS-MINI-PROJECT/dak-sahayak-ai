  import { createClient as createSupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://yqxmrebtldrhfxvaqvjg.supabase.co';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlxeG1yZWJ0bGRyaGZ4dmFxdmpnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODcxMzMyNDYsImV4cCI6MjEwMjcwOTI0Nn0.gQcqgNL5PrAuWvjATo9fvQQfTKDWwm0TGYAzJ1T9MtA';

export function createClient() {
  return createSupabaseClient(supabaseUrl, supabaseAnonKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true
    }
  });
}

export const supabase = createClient();

