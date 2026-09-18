import builtins

import pytest

from news_reposter import cli


def test_create_admin_command_uses_hidden_confirmation_and_reports_id(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    answers = iter(["admin", "Александр"])
    password_prompts: list[str] = []

    async def fake_create_admin(
        username: str,
        display_name: str,
        password: str,
    ) -> int:
        assert username == "admin"
        assert display_name == "Александр"
        assert password == "a sufficiently long password"
        return 42

    monkeypatch.setattr(builtins, "input", lambda _prompt: next(answers))

    def fake_getpass(prompt: str) -> str:
        password_prompts.append(prompt)
        return "a sufficiently long password"

    monkeypatch.setattr(cli.getpass, "getpass", fake_getpass)
    monkeypatch.setattr(cli, "create_admin", fake_create_admin)

    exit_code = cli.main(["create-admin"])

    assert exit_code == 0
    assert len(password_prompts) == 2
    assert capsys.readouterr().out == "Администратор создан, ID: 42\n"


def test_create_admin_command_rejects_different_passwords(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    answers = iter(["admin", "Administrator"])
    passwords = iter(["first long password", "second long password"])

    async def unexpected_create_admin(*_args: str) -> int:
        raise AssertionError("create_admin must not be called")

    monkeypatch.setattr(builtins, "input", lambda _prompt: next(answers))
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: next(passwords))
    monkeypatch.setattr(cli, "create_admin", unexpected_create_admin)

    exit_code = cli.main(["create-admin"])

    assert exit_code == 1
    assert "Введённые пароли не совпадают" in capsys.readouterr().out
