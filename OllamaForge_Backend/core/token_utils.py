def estimate_tokens(text: str) -> int:
    # Rough approximation: 1 token ≈ 4 characters
    if not text or not isinstance(text, str):
        return 0
    return max(1, len(text) // 4)
