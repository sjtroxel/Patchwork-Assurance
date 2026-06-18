from patchwork_assurance import __version__


def core_status() -> dict:
    """Proof-of-life for the core package, with no web layer involved.

    corpus_size is 0 now and becomes a real count in Phase 1, when the loader
    indexes the statutes — at which point /health turns into a real readiness check.
    """
    return {"status": "ok", "layer": "core", "version": __version__, "corpus_size": 0}
