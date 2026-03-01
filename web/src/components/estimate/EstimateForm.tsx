'use client';

import { useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ImageUpload } from './ImageUpload';
import { DescriptionInput } from './DescriptionInput';
import type { ImageFile } from '@/lib/utils/image';
import type { EstimateResponse } from '@/types';

interface EstimateFormProps {
  onEstimateComplete: (estimate: EstimateResponse) => void;
}

export function EstimateForm({ onEstimateComplete }: EstimateFormProps) {
  const [images, setImages] = useState<ImageFile[]>([]);
  const [description, setDescription] = useState('');
  const [location, setLocation] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = images.length > 0 || description.trim().length > 0;

  const handleSubmit = useCallback(async () => {
    if (!canSubmit) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/estimate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          images: images.map(img => img.base64),
          description: description.trim(),
          location: location.trim() || undefined,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to generate estimate');
      }

      const result: EstimateResponse = await response.json();
      onEstimateComplete(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'An error occurred';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [images, description, location, canSubmit, onEstimateComplete]);

  return (
    <Card className="max-w-4xl mx-auto">
      <CardHeader>
        <CardTitle className="text-2xl">Get a Cost Estimate</CardTitle>
        <p className="text-gray-500">
          Upload images of your project and/or describe what you want to build.
          Our AI will analyze your project and provide a detailed cost estimate.
        </p>
      </CardHeader>
      <CardContent className="space-y-8">
        {/* Image upload section */}
        <div>
          <h3 className="text-lg font-medium mb-4">Project Images</h3>
          <ImageUpload
            images={images}
            onChange={setImages}
            disabled={loading}
          />
        </div>

        {/* Description section */}
        <div>
          <h3 className="text-lg font-medium mb-4">Project Details</h3>
          <DescriptionInput
            description={description}
            location={location}
            onDescriptionChange={setDescription}
            onLocationChange={setLocation}
            disabled={loading}
          />
        </div>

        {/* Error display */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {/* Submit button */}
        <div className="flex justify-center">
          <Button
            size="lg"
            onClick={handleSubmit}
            disabled={!canSubmit || loading}
            className="px-8"
          >
            {loading ? (
              <>
                <span className="animate-spin mr-2">⏳</span>
                Analyzing...
              </>
            ) : (
              'Generate Estimate'
            )}
          </Button>
        </div>

        {!canSubmit && (
          <p className="text-center text-sm text-gray-500">
            Please upload at least one image or provide a project description.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
