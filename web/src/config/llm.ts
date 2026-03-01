// LLM Provider Configuration

export type LLMProvider = 'gemini' | 'claude' | 'both';

// Get the configured LLM provider from environment variable
// Default to 'gemini' if not specified
export const LLM_PROVIDER: LLMProvider =
  (process.env.LLM_PROVIDER as LLMProvider) || 'gemini';

export const config = {
  provider: LLM_PROVIDER,

  // Check if a specific provider should be used
  useClaude: LLM_PROVIDER === 'claude' || LLM_PROVIDER === 'both',
  useGemini: LLM_PROVIDER === 'gemini' || LLM_PROVIDER === 'both',
};
