// Supabase client configuration

import { createClient, SupabaseClient } from '@supabase/supabase-js';
import type { EstimateRecord } from '@/types';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

// Lazy-loaded clients
let _supabase: SupabaseClient | null = null;
let _serviceClient: SupabaseClient | null = null;

// Check if Supabase is configured
export function isSupabaseConfigured(): boolean {
  return Boolean(supabaseUrl && supabaseAnonKey);
}

// Get the anon client (for browser-side operations)
function getSupabase(): SupabaseClient | null {
  if (!isSupabaseConfigured()) {
    return null;
  }
  if (!_supabase) {
    _supabase = createClient(supabaseUrl, supabaseAnonKey);
  }
  return _supabase;
}

// Server-side client with service role key (for API routes)
export function getServiceClient(): SupabaseClient | null {
  if (!isSupabaseConfigured()) {
    return null;
  }

  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (serviceRoleKey) {
    if (!_serviceClient) {
      _serviceClient = createClient(supabaseUrl, serviceRoleKey);
    }
    return _serviceClient;
  }

  // Fall back to anon client
  return getSupabase();
}

// Database operations

export async function saveEstimate(
  estimate: Omit<EstimateRecord, 'id' | 'created_at'>
): Promise<EstimateRecord | null> {
  const client = getServiceClient();
  if (!client) {
    console.warn('Supabase not configured, skipping save');
    return null;
  }

  const { data, error } = await client
    .from('estimates')
    .insert(estimate)
    .select()
    .single();

  if (error) {
    console.error('Failed to save estimate:', error);
    return null;
  }

  return data as EstimateRecord;
}

export async function getEstimate(id: string): Promise<EstimateRecord | null> {
  const client = getSupabase();
  if (!client) {
    console.warn('Supabase not configured');
    return null;
  }

  const { data, error } = await client
    .from('estimates')
    .select('*')
    .eq('id', id)
    .single();

  if (error) {
    console.error('Failed to get estimate:', error);
    return null;
  }

  return data as EstimateRecord;
}

export async function getEstimatesBySession(
  sessionId: string
): Promise<EstimateRecord[]> {
  const client = getSupabase();
  if (!client) {
    console.warn('Supabase not configured');
    return [];
  }

  const { data, error } = await client
    .from('estimates')
    .select('*')
    .eq('session_id', sessionId)
    .order('created_at', { ascending: false });

  if (error) {
    console.error('Failed to get estimates:', error);
    return [];
  }

  return data as EstimateRecord[];
}

// Image storage operations

export async function uploadImage(
  file: File,
  path: string
): Promise<string | null> {
  const client = getServiceClient();
  if (!client) {
    console.warn('Supabase not configured, skipping upload');
    return null;
  }

  const { data, error } = await client.storage
    .from('estimate-images')
    .upload(path, file, {
      cacheControl: '3600',
      upsert: false,
    });

  if (error) {
    console.error('Failed to upload image:', error);
    return null;
  }

  // Get public URL
  const { data: urlData } = client.storage
    .from('estimate-images')
    .getPublicUrl(data.path);

  return urlData.publicUrl;
}

export async function uploadImageBase64(
  base64: string,
  filename: string
): Promise<string | null> {
  const client = getServiceClient();
  if (!client) {
    console.warn('Supabase not configured, skipping upload');
    return null;
  }

  // Extract the actual base64 data
  let data = base64;
  let contentType = 'image/png';

  if (base64.startsWith('data:')) {
    const match = base64.match(/^data:([^;]+);base64,(.+)$/);
    if (match) {
      contentType = match[1];
      data = match[2];
    }
  }

  // Convert base64 to Uint8Array
  const bytes = Uint8Array.from(atob(data), c => c.charCodeAt(0));

  const { data: uploadData, error } = await client.storage
    .from('estimate-images')
    .upload(filename, bytes, {
      contentType,
      cacheControl: '3600',
      upsert: false,
    });

  if (error) {
    console.error('Failed to upload image:', error);
    return null;
  }

  // Get public URL
  const { data: urlData } = client.storage
    .from('estimate-images')
    .getPublicUrl(uploadData.path);

  return urlData.publicUrl;
}
