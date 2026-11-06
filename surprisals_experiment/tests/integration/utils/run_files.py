def run_files(root):
    """Every file under a run folder, by relative path, with its bytes."""
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
