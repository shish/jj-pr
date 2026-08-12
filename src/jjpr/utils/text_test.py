from . import text


class TestRemoveAnsi:
    def test_strip(self) -> None:
        assert text.remove_ansi("\x1b[31mHello\x1b[0m") == "Hello"


class TestRichStrRoundTrip:
    def test_color(self) -> None:
        rendered = text.rich_str("[red]hello[/red]")
        assert "\x1b" in rendered
        assert text.remove_ansi(rendered) == "hello"

    def test_bold(self) -> None:
        rendered = text.rich_str("[bold]hello[/bold]")
        assert "\x1b" in rendered
        assert text.remove_ansi(rendered) == "hello"

    def test_link(self) -> None:
        rendered = text.rich_str("[link=http://example.com]click here[/link]")
        assert "\x1b" in rendered
        assert text.remove_ansi(rendered) == "click here"
