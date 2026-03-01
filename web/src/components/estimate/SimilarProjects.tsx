'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { SimilarProject } from '@/types';

interface SimilarProjectsProps {
  projects: SimilarProject[];
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatNumber(num: number): string {
  return new Intl.NumberFormat('en-US').format(num);
}

export function SimilarProjects({ projects }: SimilarProjectsProps) {
  if (projects.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Similar Projects for Reference</CardTitle>
        <p className="text-sm text-gray-500">
          These comparable projects from our database can help validate your estimate.
        </p>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 md:grid-cols-3">
          {projects.map((project) => (
            <Card key={project.project_id} className="bg-gray-50">
              <CardContent className="pt-4 space-y-3">
                <div>
                  <p className="font-medium text-sm line-clamp-2">{project.name}</p>
                  <div className="flex gap-2 mt-1">
                    <Badge variant="outline" className="text-xs">
                      {project.building_type}
                    </Badge>
                    <Badge variant="secondary" className="text-xs">
                      {project.quality}
                    </Badge>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <p className="text-gray-500">Total Cost</p>
                    <p className="font-semibold">{formatCurrency(project.total_cost)}</p>
                  </div>
                  <div>
                    <p className="text-gray-500">$/sq ft</p>
                    <p className="font-semibold">{formatCurrency(project.cost_per_sf)}</p>
                  </div>
                  <div>
                    <p className="text-gray-500">Size</p>
                    <p className="font-medium">{formatNumber(project.area_sf)} sq ft</p>
                  </div>
                  <div>
                    <p className="text-gray-500">Match</p>
                    <p className="font-medium text-green-600">
                      {Math.round(project.similarity_score)}%
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
