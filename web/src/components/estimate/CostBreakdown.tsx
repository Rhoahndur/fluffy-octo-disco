'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { useState } from 'react';
import type { CostEstimate, DivisionBreakdown, ItemQuantity } from '@/types';
import { CSI_DIVISION_NAMES } from '@/lib/cost/data/csi-profiles';

interface CostBreakdownProps {
  estimate: CostEstimate;
  confidence?: number;
  conflicts?: string[];
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

export function CostBreakdown({ estimate, confidence = 0.8, conflicts = [] }: CostBreakdownProps) {
  const [divisionsOpen, setDivisionsOpen] = useState(false);
  const [quantitiesOpen, setQuantitiesOpen] = useState(false);

  // Calculate division percentages for bars
  const divisionEntries = Object.entries(estimate.division_breakdown) as [keyof DivisionBreakdown, number][];
  const maxDivisionCost = Math.max(...divisionEntries.map(([, cost]) => cost));

  // Get confidence color
  const confidenceColor = confidence >= 0.7 ? 'text-green-600' : confidence >= 0.5 ? 'text-yellow-600' : 'text-red-600';
  const confidenceLabel = confidence >= 0.7 ? 'High' : confidence >= 0.5 ? 'Medium' : 'Low';

  return (
    <div className="space-y-6">
      {/* Main cost display */}
      <Card className="bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-200">
        <CardContent className="pt-6">
          <div className="text-center space-y-2">
            <p className="text-sm text-gray-600">Estimated Total Cost</p>
            <p className="text-5xl font-bold text-blue-700">
              {formatCurrency(estimate.total_cost)}
            </p>
            <p className="text-lg text-gray-600">
              {formatCurrency(estimate.cost_per_sf)}/sq ft
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4 text-center">
            <p className="text-sm text-gray-500">Square Footage</p>
            <p className="text-2xl font-semibold">{formatNumber(estimate.area_sf)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 text-center">
            <p className="text-sm text-gray-500">Stories</p>
            <p className="text-2xl font-semibold">{estimate.stories}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 text-center">
            <p className="text-sm text-gray-500">Quality</p>
            <Badge variant={estimate.quality === 'high' ? 'default' : 'secondary'} className="mt-1">
              {estimate.quality.toUpperCase()}
            </Badge>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 text-center">
            <p className="text-sm text-gray-500">Location Factor</p>
            <p className="text-2xl font-semibold">{estimate.location_factor.toFixed(2)}x</p>
            <p className="text-xs text-gray-400">{estimate.location}</p>
          </CardContent>
        </Card>
      </div>

      {/* Confidence indicator */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Estimate Confidence</span>
            <span className={`font-semibold ${confidenceColor}`}>
              {confidenceLabel} ({Math.round(confidence * 100)}%)
            </span>
          </div>
          <Progress value={confidence * 100} className="h-2" />
          {conflicts.length > 0 && (
            <div className="mt-3 space-y-1">
              <p className="text-sm text-yellow-600 font-medium">Analysis Notes:</p>
              {conflicts.map((conflict, i) => (
                <p key={i} className="text-sm text-gray-600">• {conflict}</p>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* CSI Division breakdown */}
      <Collapsible open={divisionsOpen} onOpenChange={setDivisionsOpen}>
        <Card>
          <CollapsibleTrigger asChild>
            <CardHeader className="cursor-pointer hover:bg-gray-50 transition-colors">
              <CardTitle className="flex items-center justify-between text-lg">
                <span>Cost Breakdown by Division</span>
                <span className="text-gray-400">{divisionsOpen ? '▼' : '▶'}</span>
              </CardTitle>
            </CardHeader>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <CardContent className="space-y-3">
              {divisionEntries
                .sort(([, a], [, b]) => b - a)
                .map(([division, cost]) => {
                  const pct = (cost / estimate.total_cost) * 100;
                  const barWidth = (cost / maxDivisionCost) * 100;

                  return (
                    <div key={division} className="space-y-1">
                      <div className="flex justify-between text-sm">
                        <span>{CSI_DIVISION_NAMES[division] || division}</span>
                        <span className="font-medium">
                          {formatCurrency(cost)} ({pct.toFixed(1)}%)
                        </span>
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-500 rounded-full"
                          style={{ width: `${barWidth}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
            </CardContent>
          </CollapsibleContent>
        </Card>
      </Collapsible>

      {/* Item quantities */}
      {estimate.item_quantities && estimate.item_quantities.length > 0 && (
        <Collapsible open={quantitiesOpen} onOpenChange={setQuantitiesOpen}>
          <Card>
            <CollapsibleTrigger asChild>
              <CardHeader className="cursor-pointer hover:bg-gray-50 transition-colors">
                <CardTitle className="flex items-center justify-between text-lg">
                  <span>Material Quantities</span>
                  <span className="text-gray-400">{quantitiesOpen ? '▼' : '▶'}</span>
                </CardTitle>
              </CardHeader>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-2">Item</th>
                        <th className="text-right py-2">Quantity</th>
                        <th className="text-right py-2">Unit Cost</th>
                        <th className="text-right py-2">Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {estimate.item_quantities.map((item, i) => (
                        <tr key={i} className="border-b border-gray-100">
                          <td className="py-2">{item.item}</td>
                          <td className="text-right py-2">
                            {formatNumber(item.quantity)} {item.unit}
                          </td>
                          <td className="text-right py-2">
                            {formatCurrency(item.unit_cost)}
                          </td>
                          <td className="text-right py-2 font-medium">
                            {formatCurrency(item.total_cost)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </CollapsibleContent>
          </Card>
        </Collapsible>
      )}
    </div>
  );
}
