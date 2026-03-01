import { NextRequest, NextResponse } from 'next/server';
import { getEstimate, isSupabaseConfigured } from '@/lib/db/supabase';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;

    if (!isSupabaseConfigured()) {
      return NextResponse.json(
        { error: 'Database not configured' },
        { status: 503 }
      );
    }

    const estimate = await getEstimate(id);

    if (!estimate) {
      return NextResponse.json(
        { error: 'Estimate not found' },
        { status: 404 }
      );
    }

    return NextResponse.json(estimate);
  } catch (error) {
    console.error('Get estimate error:', error);
    return NextResponse.json(
      { error: 'Failed to retrieve estimate' },
      { status: 500 }
    );
  }
}
