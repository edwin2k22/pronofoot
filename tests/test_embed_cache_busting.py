from collector import embed


def test_stamp_assets_adds_and_replaces_cache_buster(tmp_path):
    html = tmp_path / "index.html"
    html.write_text(
        '<link rel="stylesheet" href="assets/theme.css?v=old">\n'
        '<script src="assets/shell.js"></script>\n'
        '<script type="module" src="assets/main.js?v=old"></script>',
        encoding="utf-8",
    )

    embed._stamp_assets(str(html), "20260706123456")
    out = html.read_text(encoding="utf-8")

    assert 'href="assets/theme.css?v=20260706123456"' in out
    assert 'src="assets/shell.js?v=20260706123456"' in out
    assert 'src="assets/main.js?v=20260706123456"' in out


def test_stamp_build_writes_data_version(tmp_path):
    html = tmp_path / "index.html"
    html.write_text('<body data-build="old"></body>', encoding="utf-8")

    embed._stamp_build(str(html), "06/07 13:31", "20260706133146")
    out = html.read_text(encoding="utf-8")

    assert 'data-build="06/07 13:31"' in out
    assert 'data-version="20260706133146"' in out
