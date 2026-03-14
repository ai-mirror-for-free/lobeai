# Plan: Implement OpenRouter Model Pricing Lookup

## Context
The user wants a Python function to retrieve the input and output pricing for a given model from OpenRouter. This integration will be built from scratch since there is no existing LLM infrastructure in the codebase.

## Approach
1. Create a new utility module for OpenRouter API interactions.
2. Implement a function that fetches model pricing from the OpenRouter `/api/v1/models` endpoint.
3. Add a caching/mapping mechanism to avoid repeated API calls for the same model data.
4. Structure the output of the function to return `{ prompt_price: float, completion_price: float }` for the requested model ID.

## Critical Files
- `/Users/yangfan/project/lobeai/utils/pricing.py` (New file)
- `/Users/yangfan/project/lobeai/.env` (To store the OPENROUTER_API_KEY)

## Testing
- Create a test script to query the price of a known model (e.g., `openai/gpt-4o`) and print the result.
