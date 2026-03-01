'use client';

import { useState } from 'react';
import { EstimateForm } from '@/components/estimate/EstimateForm';
import { CostBreakdown } from '@/components/estimate/CostBreakdown';
import { SimilarProjects } from '@/components/estimate/SimilarProjects';
import { Button } from '@/components/ui/button';
import type { EstimateResponse } from '@/types';

export default function Home() {
  const [estimate, setEstimate] = useState<EstimateResponse | null>(null);

  const handleEstimateComplete = (result: EstimateResponse) => {
    setEstimate(result);
    // Scroll to results
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleNewEstimate = () => {
    setEstimate(null);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-2xl">🏗️</span>
              <h1 className="text-xl font-bold text-gray-900">
                Construction Cost Estimator
              </h1>
            </div>
            {estimate && (
              <Button variant="outline" onClick={handleNewEstimate}>
                New Estimate
              </Button>
            )}
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        {!estimate ? (
          <div className="space-y-8">
            {/* Hero section */}
            <div className="text-center max-w-3xl mx-auto">
              <h2 className="text-4xl font-bold text-gray-900 mb-4">
                Get Instant Construction Cost Estimates
              </h2>
              <p className="text-xl text-gray-600">
                Upload project images and descriptions. Our AI analyzes your plans
                using Claude and Gemini vision models, then provides detailed
                RSMeans-based cost breakdowns.
              </p>
            </div>

            {/* Features */}
            <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
              <div className="bg-white p-6 rounded-lg shadow-sm border text-center">
                <div className="text-3xl mb-2">🤖</div>
                <h3 className="font-semibold mb-1">Multi-AI Analysis</h3>
                <p className="text-sm text-gray-600">
                  Claude and Gemini analyze your project for accurate classification
                </p>
              </div>
              <div className="bg-white p-6 rounded-lg shadow-sm border text-center">
                <div className="text-3xl mb-2">📊</div>
                <h3 className="font-semibold mb-1">RSMeans Pricing</h3>
                <p className="text-sm text-gray-600">
                  Industry-standard cost data with regional adjustments
                </p>
              </div>
              <div className="bg-white p-6 rounded-lg shadow-sm border text-center">
                <div className="text-3xl mb-2">📋</div>
                <h3 className="font-semibold mb-1">Detailed Breakdown</h3>
                <p className="text-sm text-gray-600">
                  18 CSI divisions with material quantities
                </p>
              </div>
            </div>

            {/* Form */}
            <EstimateForm onEstimateComplete={handleEstimateComplete} />
          </div>
        ) : (
          <div className="space-y-8">
            {/* Results header */}
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">
                  Your Cost Estimate
                </h2>
                <p className="text-gray-500">
                  Generated on {new Date(estimate.created_at).toLocaleString()}
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    navigator.clipboard.writeText(window.location.href);
                  }}
                >
                  Copy Link
                </Button>
                <Button variant="outline" onClick={handleNewEstimate}>
                  New Estimate
                </Button>
              </div>
            </div>

            {/* Cost breakdown */}
            {estimate.estimate && (
              <CostBreakdown
                estimate={estimate.estimate}
                confidence={estimate.analysis?.confidence}
                conflicts={estimate.analysis?.conflicts}
              />
            )}

            {/* Similar projects */}
            {estimate.similar_projects && estimate.similar_projects.length > 0 && (
              <SimilarProjects projects={estimate.similar_projects} />
            )}

            {/* Analysis details */}
            {estimate.analysis && (
              <div className="bg-white rounded-lg border p-6">
                <h3 className="font-semibold mb-4">Analysis Details</h3>
                <div className="grid md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500">Building Type:</span>{' '}
                    <span className="font-medium">
                      {estimate.analysis.merged.building_type}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Sub-type:</span>{' '}
                    <span className="font-medium">
                      {estimate.analysis.merged.sub_type.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Construction Type:</span>{' '}
                    <span className="font-medium">
                      {estimate.analysis.merged.construction_type.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Materials Detected:</span>{' '}
                    <span className="font-medium">
                      {estimate.analysis.merged.materials_detected.join(', ') || 'N/A'}
                    </span>
                  </div>
                </div>
                {estimate.analysis.merged.notes && (
                  <div className="mt-4 p-3 bg-gray-50 rounded text-sm">
                    <span className="text-gray-500">Notes:</span>{' '}
                    {estimate.analysis.merged.notes}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t mt-16">
        <div className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
          <p className="text-center text-gray-500 text-sm">
            Construction Cost Estimator - Powered by Claude, Gemini, and RSMeans data
          </p>
        </div>
      </footer>
    </div>
  );
}
