// Similar project matching using the eval dataset

import type { SimilarProject, Quality, BuildingCategory, EvalProject } from '@/types';

// We'll load these at runtime from the data directory
let evalDataset: EvalProject[] = [];
let richDataset: EvalProject[] = [];
let datasetsLoaded = false;

// Load datasets (called once on first use)
export async function loadDatasets(): Promise<void> {
  if (datasetsLoaded) return;

  try {
    // In production, these would be loaded from a database or API
    // For now, we'll use dynamic imports
    const evalData = await import('@/data/eval_dataset.json');
    const richData = await import('@/data/rich_eval_dataset.json');

    evalDataset = evalData.default as unknown as EvalProject[];
    richDataset = richData.default as unknown as EvalProject[];
    datasetsLoaded = true;
  } catch (error) {
    console.error('Failed to load datasets:', error);
    // Use empty arrays if datasets not available
    evalDataset = [];
    richDataset = [];
    datasetsLoaded = true;
  }
}

interface MatchCriteria {
  building_type: BuildingCategory;
  sub_type?: string;
  quality?: Quality;
  area_sf?: number;
}

export async function findSimilarProjects(
  criteria: MatchCriteria,
  limit: number = 3
): Promise<SimilarProject[]> {
  await loadDatasets();

  const allProjects = [...evalDataset, ...richDataset];

  if (allProjects.length === 0) {
    return [];
  }

  // Score each project by similarity
  const scored = allProjects.map(project => ({
    project,
    score: calculateSimilarity(criteria, project),
  }));

  // Sort by score descending and take top N
  const topProjects = scored
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);

  return topProjects.map(({ project, score }) => ({
    project_id: project.project_id,
    name: project.name,
    building_type: project.building_type,
    sub_type: project.sub_type,
    quality: project.quality,
    area_sf: project.area_sf,
    total_cost: project.ground_truth.total_cost,
    cost_per_sf: project.ground_truth.cost_per_sf,
    similarity_score: Math.round(score * 100) / 100,
  }));
}

function calculateSimilarity(query: MatchCriteria, project: EvalProject): number {
  let score = 0;

  // Exact building type match: +40 points
  if (query.building_type === project.building_type) {
    score += 40;
  } else {
    // Partial credit for related types
    const relatedTypes: Record<string, string[]> = {
      residential: ['commercial'], // mixed-use overlap
      commercial: ['residential', 'institutional'],
      industrial: ['infrastructure'],
      institutional: ['commercial'],
      infrastructure: ['industrial'],
    };
    const projectType = project.building_type as string;
    if (relatedTypes[query.building_type]?.includes(projectType)) {
      score += 15;
    }
  }

  // Sub-type match: +30 points
  if (query.sub_type && query.sub_type === project.sub_type) {
    score += 30;
  } else if (query.sub_type) {
    // Partial credit for similar sub-types
    const querySub = query.sub_type.toLowerCase();
    const projSub = project.sub_type.toLowerCase();

    // Check for word overlap
    const queryWords = new Set(querySub.split('_'));
    const projWords = new Set(projSub.split('_'));
    const overlap = [...queryWords].filter(w => projWords.has(w)).length;
    score += overlap * 8;
  }

  // Quality match: +15 points
  if (query.quality && query.quality === project.quality) {
    score += 15;
  } else if (query.quality && project.quality) {
    // Partial credit for adjacent quality
    const qualities = ['low', 'mid', 'high'];
    const qIdx = qualities.indexOf(query.quality);
    const pIdx = qualities.indexOf(project.quality as string);
    if (qIdx >= 0 && pIdx >= 0 && Math.abs(qIdx - pIdx) === 1) {
      score += 8;
    }
  }

  // Area similarity: +15 points (scaled by closeness)
  if (query.area_sf && project.area_sf) {
    const areaRatio = Math.min(query.area_sf, project.area_sf) /
                      Math.max(query.area_sf, project.area_sf);
    score += areaRatio * 15;
  }

  return score;
}

// Get projects by type for browsing
export async function getProjectsByType(
  buildingType: BuildingCategory
): Promise<SimilarProject[]> {
  await loadDatasets();

  const allProjects = [...evalDataset, ...richDataset];

  return allProjects
    .filter(p => p.building_type === buildingType)
    .map(project => ({
      project_id: project.project_id,
      name: project.name,
      building_type: project.building_type,
      sub_type: project.sub_type,
      quality: project.quality,
      area_sf: project.area_sf,
      total_cost: project.ground_truth.total_cost,
      cost_per_sf: project.ground_truth.cost_per_sf,
      similarity_score: 1,
    }));
}

// Get a single project by ID
export async function getProjectById(
  projectId: string
): Promise<EvalProject | null> {
  await loadDatasets();

  const allProjects = [...evalDataset, ...richDataset];
  return allProjects.find(p => p.project_id === projectId) || null;
}
