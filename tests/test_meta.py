"""core.meta.corpus_vocab — pure aggregation over loaded law metadata, no network."""

from patchwork_assurance.core.corpus.metadata import LawMetadata
from patchwork_assurance.core.meta import corpus_vocab


def _law(jurisdiction, roles, domains):
    return LawMetadata.model_construct(
        jurisdiction=jurisdiction, regulated_roles=roles, scope_domains=domains
    )


def test_corpus_vocab_aggregates_sorted_unique():
    laws = [
        _law("Colorado", ["deployer", "developer"], ["employment", "financial_lending"]),
        _law("Connecticut", ["deployer", "developer"], ["employment", "ai_companion"]),
    ]
    v = corpus_vocab(laws)
    assert v.jurisdictions == ["Colorado", "Connecticut"]
    assert v.decision_domains == ["ai_companion", "employment", "financial_lending"]
    assert v.roles == ["deployer", "developer"]  # de-duplicated across laws


def test_corpus_vocab_empty():
    v = corpus_vocab([])
    assert v.jurisdictions == []
    assert v.decision_domains == []
    assert v.roles == []
