from weather_cli.list import list_downloads


def test_list_downloads_outputs_and_returns(tmp_path, capsys):
    data_dir = tmp_path
    (data_dir / "city.zip").write_text("x")
    (data_dir / "town.zip").write_text("y")

    items = list_downloads(data_dir)
    captured = capsys.readouterr().out

    assert len(items) == 2
    assert "city.zip" in captured and "town.zip" in captured
    names = [name for name, _ in items]
    assert "city" in names and "town" in names
