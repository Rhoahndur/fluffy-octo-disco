'use client';

import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';

interface DescriptionInputProps {
  description: string;
  location: string;
  onDescriptionChange: (value: string) => void;
  onLocationChange: (value: string) => void;
  disabled?: boolean;
}

export function DescriptionInput({
  description,
  location,
  onDescriptionChange,
  onLocationChange,
  disabled = false,
}: DescriptionInputProps) {
  const maxLength = 5000;

  return (
    <div className="space-y-4">
      {/* Description textarea */}
      <div className="space-y-2">
        <label htmlFor="description" className="block text-sm font-medium">
          Project Description
        </label>
        <Textarea
          id="description"
          placeholder={`Describe your construction project...

Examples:
• "2-story single family home, 2500 sqft, 4 bedrooms, modern finishes, wood frame construction"
• "Small retail space renovation, 1200 sqft, new storefront, basic finishes"
• "Industrial warehouse, 10,000 sqft, concrete slab, metal building"
• "Medical office buildout, 3000 sqft, high-end finishes, specialized HVAC"

Include details like:
- Building type and use
- Square footage
- Number of stories
- Quality level (basic, standard, premium)
- Construction type (wood frame, steel, concrete)
- Special features or requirements`}
          value={description}
          onChange={(e) => onDescriptionChange(e.target.value)}
          className="min-h-[200px] resize-y"
          maxLength={maxLength}
          disabled={disabled}
        />
        <div className="flex justify-between text-sm text-gray-500">
          <span>Be as detailed as possible for better estimates</span>
          <span>{description.length}/{maxLength}</span>
        </div>
      </div>

      {/* Location input */}
      <div className="space-y-2">
        <label htmlFor="location" className="block text-sm font-medium">
          Location (optional)
        </label>
        <Input
          id="location"
          placeholder="e.g., Chicago, IL or San Francisco, CA"
          value={location}
          onChange={(e) => onLocationChange(e.target.value)}
          disabled={disabled}
        />
        <p className="text-sm text-gray-500">
          Location affects labor and material costs. Leave blank for national average.
        </p>
      </div>
    </div>
  );
}
