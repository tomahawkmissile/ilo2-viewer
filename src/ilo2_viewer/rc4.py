"""RC4 stream cipher with MD5-based key derivation for iLO2 session encryption."""

import hashlib


class RC4:
    def __init__(self, key: bytes):
        self._pre = bytearray(key[:16])
        self._key = bytearray(16)
        self._s_box = bytearray(256)
        self._i = 0
        self._j = 0
        self.update_key()

    def update_key(self):
        md5 = hashlib.md5()
        md5.update(self._pre)
        md5.update(self._key)
        digest = md5.digest()
        self._key[:] = digest[:16]

        for k in range(256):
            self._s_box[k] = k
        key_box = bytearray(self._key[k % 16] for k in range(256))

        self._j = 0
        for self._i in range(256):
            self._j = (self._j + self._s_box[self._i] + key_box[self._i]) & 0xFF
            self._s_box[self._i], self._s_box[self._j] = self._s_box[self._j], self._s_box[self._i]

        self._i = 0
        self._j = 0

    def random_value(self) -> int:
        self._i = (self._i + 1) & 0xFF
        self._j = (self._j + self._s_box[self._i]) & 0xFF
        self._s_box[self._i], self._s_box[self._j] = self._s_box[self._j], self._s_box[self._i]
        m = (self._s_box[self._i] + self._s_box[self._j]) & 0xFF
        return self._s_box[m]
