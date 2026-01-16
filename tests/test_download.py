import weather_cli.download as download


def test_slugify_basic():
    assert download.slugify("Hello World") == "hello-world"
    assert download.slugify("   ") == "dataset"
