from patchwork_assurance.core.contracts import CorpusVocab
from patchwork_assurance.core.corpus.metadata import LawMetadata


def corpus_vocab(laws: list[LawMetadata]) -> CorpusVocab:
    """Aggregate the form's controlled vocabulary from the loaded corpus — generic over N statutes.
    Adding a jurisdiction (drop a file pair, re-run the loader) auto-populates the UI form with zero
    code change (Phase 4.6, Fork K1; invariant 2). Returns sorted, de-duplicated values."""
    return CorpusVocab(
        jurisdictions=sorted({law.jurisdiction for law in laws}),
        decision_domains=sorted({d for law in laws for d in law.scope_domains}),
        roles=sorted({r for law in laws for r in law.regulated_roles}),
    )
