import json
import re
from typing import Any, Optional, List, Dict

def extract_json_from_response(response: str) -> Optional[Any]:
    """
    Robust JSON extraction from LLM responses that may contain extra text.
    Handles common issues like text before/after JSON, markdown code blocks, etc.
    """
    if not response or not response.strip():
        return None
    
    # Clean the response
    cleaned = response.strip()
    
    # Try direct JSON parsing first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # Look for JSON in markdown code blocks
    code_block_patterns = [
        r'```json\s*\n?(.*?)\n?```',
        r'```\s*\n?(.*?)\n?```',
        r'`([^`]+)`'
    ]
    
    for pattern in code_block_patterns:
        matches = re.findall(pattern, cleaned, re.DOTALL | re.IGNORECASE)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
    
    # Look for JSON array patterns
    array_pattern = r'\[.*\]'
    array_matches = re.findall(array_pattern, cleaned, re.DOTALL)
    for match in array_matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue
    
    # Look for JSON object patterns
    object_pattern = r'\{.*\}'
    object_matches = re.findall(object_pattern, cleaned, re.DOTALL)
    for match in object_matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue
    
    # Try to extract JSON from the middle of text
    # Find the first { or [ and last } or ]
    start_chars = ['{', '[']
    end_chars = ['}', ']']
    
    for start_char, end_char in zip(start_chars, end_chars):
        start_idx = cleaned.find(start_char)
        end_idx = cleaned.rfind(end_char)
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            potential_json = cleaned[start_idx:end_idx + 1]
            try:
                return json.loads(potential_json)
            except json.JSONDecodeError:
                continue
    
    return None

def parse_llm_json_response(response: str, expected_type: type = list) -> Any:
    """
    Parse LLM JSON response with robust error handling.
    
    Args:
        response: The raw LLM response
        expected_type: Expected type (list or dict)
    
    Returns:
        Parsed JSON data or empty list/dict if parsing fails
    """
    if not response:
        return [] if expected_type == list else {}
    
    # Try robust extraction
    result = extract_json_from_response(response)
    
    if result is None:
        print(f"Could not extract JSON from response: {response[:200]}...")
        return [] if expected_type == list else {}
    
    # Validate type
    if not isinstance(result, expected_type):
        print(f"Expected {expected_type.__name__}, got {type(result).__name__}")
        return [] if expected_type == list else {}
    
    return result