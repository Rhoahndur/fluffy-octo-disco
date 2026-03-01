import { NextRequest, NextResponse } from 'next/server';
import { findSimilarProjects } from '@/lib/similar/matcher';
import type { BuildingCategory, Quality } from '@/types';

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;

    const buildingType = searchParams.get('type') as BuildingCategory | null;
    const subType = searchParams.get('sub_type') || undefined;
    const quality = searchParams.get('quality') as Quality | null;
    const sqftParam = searchParams.get('sqft');
    const limitParam = searchParams.get('limit');

    if (!buildingType) {
      return NextResponse.json(
        { error: 'type parameter is required' },
        { status: 400 }
      );
    }

    const sqft = sqftParam ? parseInt(sqftParam, 10) : undefined;
    const limit = limitParam ? parseInt(limitParam, 10) : 3;

    const projects = await findSimilarProjects(
      {
        building_type: buildingType,
        sub_type: subType,
        quality: quality || undefined,
        area_sf: sqft,
      },
      limit
    );

    return NextResponse.json({ projects });
  } catch (error) {
    console.error('Similar projects error:', error);
    return NextResponse.json(
      { error: 'Failed to find similar projects' },
      { status: 500 }
    );
  }
}
