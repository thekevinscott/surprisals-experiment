def well_formed(text: str) -> str:
    """Rejoin surrogate pairs split across stream chunks; replace any left alone."""
    return text.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
