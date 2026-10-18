"""
Session key rotation by HKDF ratchet.

Both ends start from the same root key and advance a one-way chain: key for epoch n is
HKDF(root, info="sentinelspread-session" + n). Each epoch therefore has an independent AES key
and, because the DSSS PN seed is derived from the AES key, an independent spreading sequence too.
The chain is one-way, so a compromised epoch key does not reveal the root or earlier epochs.
"""

from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import HKDF


class KeyRatchet:
    def __init__(self, root_key: bytes, epoch: int = 0, key_len: int = 32):
        if len(root_key) < 16:
            raise ValueError("root_key must be at least 16 bytes")
        self.root_key = bytes(root_key)
        self.key_len = key_len
        self.epoch = epoch

    def key_for(self, epoch: int) -> bytes:
        """Deterministic AES session key for a specific epoch (either end can jump to any epoch)."""
        return HKDF(
            master=self.root_key,
            key_len=self.key_len,
            salt=b"",
            hashmod=SHA256,
            context=b"sentinelspread-session-" + str(int(epoch)).encode(),
        )

    def current_key(self) -> bytes:
        return self.key_for(self.epoch)

    def advance(self) -> bytes:
        """Step to the next epoch and return its key."""
        self.epoch += 1
        return self.current_key()
