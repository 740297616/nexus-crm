from app.modules.auth.model import User
from app.modules.roles.model import Role
from sqlalchemy import select


def test_bootstrap_admin_requires_secret_environment_and_is_idempotent(
    monkeypatch, capsys, test_session_factory
) -> None:
    from app.scripts import bootstrap_admin

    monkeypatch.setattr(bootstrap_admin, "SessionLocal", test_session_factory)
    monkeypatch.setenv("INITIAL_ADMIN_USERNAME", "initial-admin")
    monkeypatch.setenv("INITIAL_ADMIN_DISPLAY_NAME", "Initial Admin")
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "initial-admin@example.com")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "HighEntropyInitialPassword123!")

    bootstrap_admin.bootstrap_admin()
    first_output = capsys.readouterr().out
    assert "Initial system administrator created." in first_output
    assert "HighEntropyInitialPassword123!" not in first_output

    with test_session_factory() as db:
        user = db.scalar(select(User).where(User.username == "initial-admin"))
        assert user is not None
        assert user.password_hash.startswith("$argon2id$")
        assert [role.code for role in user.roles] == ["system_admin"]
        assert db.scalar(select(Role.id).where(Role.code == "system_admin")) is not None

    bootstrap_admin.bootstrap_admin()
    assert "already exists" in capsys.readouterr().out
