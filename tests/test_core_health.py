from patchwork_assurance.core.health import core_status


def test_core_status_shape():
    status = core_status()
    assert status["status"] == "ok"
    assert status["layer"] == "core"
    assert status["corpus_size"] == 0
