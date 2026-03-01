'use client';

import { useCallback, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import type { ImageFile } from '@/lib/utils/image';
import { validateImageFile, compressImage, fileToBase64 } from '@/lib/utils/image';

interface ImageUploadProps {
  images: ImageFile[];
  onChange: (images: ImageFile[]) => void;
  maxImages?: number;
  disabled?: boolean;
}

export function ImageUpload({
  images,
  onChange,
  maxImages = 10,
  disabled = false,
}: ImageUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);

  const processFiles = useCallback(async (files: FileList | File[]) => {
    setError(null);
    setProcessing(true);

    const newImages: ImageFile[] = [];
    const fileArray = Array.from(files);

    // Check max images limit
    const remaining = maxImages - images.length;
    if (fileArray.length > remaining) {
      setError(`Can only add ${remaining} more image(s). Max ${maxImages} total.`);
      fileArray.splice(remaining);
    }

    for (const file of fileArray) {
      // Validate
      const validation = validateImageFile(file);
      if (!validation.valid) {
        setError(validation.error || 'Invalid file');
        continue;
      }

      try {
        // Compress
        const compressed = await compressImage(file, 1);

        // Create preview and base64
        const preview = URL.createObjectURL(compressed);
        const base64 = await fileToBase64(compressed);

        newImages.push({
          file: compressed,
          preview,
          base64,
        });
      } catch (err) {
        console.error('Failed to process image:', err);
        setError('Failed to process image');
      }
    }

    setProcessing(false);
    onChange([...images, ...newImages]);
  }, [images, maxImages, onChange]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    if (disabled) return;

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      processFiles(files);
    }
  }, [disabled, processFiles]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) {
      setIsDragging(true);
    }
  }, [disabled]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      processFiles(files);
    }
    // Reset input
    e.target.value = '';
  }, [processFiles]);

  const removeImage = useCallback((index: number) => {
    const newImages = [...images];
    // Cleanup preview URL
    URL.revokeObjectURL(newImages[index].preview);
    newImages.splice(index, 1);
    onChange(newImages);
  }, [images, onChange]);

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <Card
        className={`
          relative border-2 border-dashed p-8 text-center cursor-pointer
          transition-colors duration-200
          ${isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        `}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => !disabled && document.getElementById('file-input')?.click()}
      >
        <input
          id="file-input"
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          multiple
          className="hidden"
          onChange={handleFileSelect}
          disabled={disabled}
        />

        <div className="space-y-2">
          <div className="text-4xl">📷</div>
          <p className="text-lg font-medium">
            {processing ? 'Processing...' : 'Drop images here or click to upload'}
          </p>
          <p className="text-sm text-gray-500">
            Supports JPEG, PNG, WebP, GIF. Max 10MB per file.
          </p>
          <p className="text-sm text-gray-400">
            {images.length}/{maxImages} images
          </p>
        </div>
      </Card>

      {/* Error message */}
      {error && (
        <p className="text-red-500 text-sm">{error}</p>
      )}

      {/* Image previews */}
      {images.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {images.map((img, index) => (
            <div key={index} className="relative group">
              <img
                src={img.preview}
                alt={`Upload ${index + 1}`}
                className="w-full h-32 object-cover rounded-lg border"
              />
              <Button
                variant="destructive"
                size="sm"
                className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity h-6 w-6 p-0"
                onClick={(e) => {
                  e.stopPropagation();
                  removeImage(index);
                }}
                disabled={disabled}
              >
                ✕
              </Button>
              <div className="absolute bottom-1 left-1 bg-black/50 text-white text-xs px-1 rounded">
                {(img.file.size / 1024).toFixed(0)}KB
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
