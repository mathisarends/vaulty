from io import StringIO

from rich.console import Console

from vaulty.cli.app import build_parser
from vaulty.cli.terminal import checklist_renderable, parse_checklist


def test_cli_accepts_workspace_and_display_overrides(tmp_path):
    args = build_parser().parse_args(["--root", str(tmp_path), "--no-color"])

    assert args.root == tmp_path
    assert args.no_color is True


def test_checklist_renderer_shows_pending_and_completed_items():
    items = parse_checklist("1. [x] Inspect files\n2. [ ] Run tests")

    assert items is not None
    output = StringIO()
    console = Console(file=output, no_color=True, width=80)
    console.print(checklist_renderable(items))

    rendered = output.getvalue()
    assert "Checklist" in rendered
    assert "[x]" in rendered and "Inspect files" in rendered
    assert "[ ]" in rendered and "Run tests" in rendered


def test_checklist_parser_rejects_regular_tool_output():
    assert parse_checklist("wrote notes.md (12 chars)") is None
