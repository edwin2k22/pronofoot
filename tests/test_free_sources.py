from collector.sources import free_sources


def test_free_source_manifest_is_explicit():
    manifest = free_sources.manifest()
    labels = {source["label"] for source in manifest["sources"]}
    assert manifest["mode"] == "free-only"
    assert "ESPN public" in labels
    assert "openfootball" in labels
    assert len(labels) >= 5


def test_no_paid_api_dependency_in_active_code():
    assert free_sources.scan_for_paid_dependencies() == []
