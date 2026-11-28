"""cli.py encrypt: which RSA key a bundle is sealed to."""
from types import SimpleNamespace

import pytest

import cli
from sentinelspread.crypto.key_mgmt import export_key, generate_rsa_keypair


def _args(tmp_path, **kw):
    base = dict(input="hello", type="text", out=str(tmp_path / "bundle.bin"), key=None, save_keys=False)
    base.update(kw)
    return SimpleNamespace(**base)


def test_missing_key_file_is_an_error_not_a_new_keypair(tmp_path, capsys, monkeypatch):
    made = []
    monkeypatch.setattr(cli, "generate_rsa_keypair", lambda **kw: made.append(kw))
    with pytest.raises(SystemExit) as exit_info:
        cli.handle_encrypt(_args(tmp_path, key=str(tmp_path / "pubkey.pem")))
    assert exit_info.value.code == 1
    assert "not found" in capsys.readouterr().out
    assert made == [] and not (tmp_path / "bundle.bin").exists()


def test_given_key_file_is_used(tmp_path, capsys):
    _, pub = generate_rsa_keypair(2048)
    export_key(pub, tmp_path / "pub.pem")
    cli.handle_encrypt(_args(tmp_path, key=str(tmp_path / "pub.pem")))
    out = capsys.readouterr().out
    assert "Loaded public key" in out and "Warning" not in out
    assert (tmp_path / "bundle.bin").stat().st_size > 0


def test_unsaved_transient_key_is_warned_about(tmp_path, capsys):
    cli.handle_encrypt(_args(tmp_path))
    assert "cannot be decrypted later" in capsys.readouterr().out
