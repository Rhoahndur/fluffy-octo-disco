// Image utilities for client-side processing

import imageCompression from 'browser-image-compression';

export interface ImageFile {
  file: File;
  preview: string;
  base64?: string;
}

// Compress image to target size
export async function compressImage(
  file: File,
  maxSizeMB: number = 1,
  maxWidthOrHeight: number = 2048
): Promise<File> {
  const options = {
    maxSizeMB,
    maxWidthOrHeight,
    useWebWorker: true,
    fileType: file.type as 'image/jpeg' | 'image/png' | 'image/webp',
  };

  try {
    const compressedFile = await imageCompression(file, options);
    return compressedFile;
  } catch (error) {
    console.error('Image compression failed:', error);
    return file; // Return original if compression fails
  }
}

// Convert file to base64
export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = error => reject(error);
  });
}

// Process multiple images for upload
export async function processImages(
  files: File[],
  maxSizeMB: number = 1
): Promise<ImageFile[]> {
  const processed: ImageFile[] = [];

  for (const file of files) {
    // Compress if needed
    const compressed = await compressImage(file, maxSizeMB);

    // Generate preview
    const preview = URL.createObjectURL(compressed);

    // Convert to base64
    const base64 = await fileToBase64(compressed);

    processed.push({
      file: compressed,
      preview,
      base64,
    });
  }

  return processed;
}

// Validate image file
export function validateImageFile(file: File): { valid: boolean; error?: string } {
  const validTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];

  if (!validTypes.includes(file.type)) {
    return {
      valid: false,
      error: `Invalid file type: ${file.type}. Allowed: JPEG, PNG, WebP, GIF`,
    };
  }

  // Max 10MB before compression
  const maxSize = 10 * 1024 * 1024;
  if (file.size > maxSize) {
    return {
      valid: false,
      error: `File too large: ${(file.size / 1024 / 1024).toFixed(1)}MB. Max: 10MB`,
    };
  }

  return { valid: true };
}

// Get image dimensions
export function getImageDimensions(
  file: File
): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      resolve({ width: img.width, height: img.height });
      URL.revokeObjectURL(img.src);
    };
    img.onerror = () => {
      reject(new Error('Failed to load image'));
      URL.revokeObjectURL(img.src);
    };
    img.src = URL.createObjectURL(file);
  });
}

// Cleanup preview URLs
export function cleanupPreviews(images: ImageFile[]): void {
  images.forEach(img => {
    if (img.preview) {
      URL.revokeObjectURL(img.preview);
    }
  });
}
