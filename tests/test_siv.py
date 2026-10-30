"""Cross-check actual Lua 5.1 implementation against independent AES-SIV."""
from pathlib import Path
import secrets
import unittest
from Crypto.Cipher import AES
from lupa.lua51 import LuaRuntime

class SIVTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lua=LuaRuntime(encoding=None,unpack_returned_tuples=True)
        # Exercise the same restricted library surface as the game.
        cls.lua.execute(b'package=nil;require=nil;io=nil;os=nil;bit=nil;bit32=nil')
        cls.lua.execute((Path(__file__).resolve().parents[1]/'DLC/InGameTranslateMod/UI/IGT_Crypto.lua').read_bytes())
        cls.siv=cls.lua.globals().IGT_Crypto
    def compare(self,key,ad,plain):
        obj=AES.new(key,AES.MODE_SIV)
        for a in ad:obj.update(a)
        cipher,tag=obj.encrypt_and_digest(plain)
        expected=tag+cipher
        actual=self.siv.seal(key,self.lua.table_from(ad),plain)
        self.assertEqual(actual,expected)
        self.assertEqual(self.siv.open(key,self.lua.table_from(ad),expected),plain)
        return actual
    def test_rfc5297_a1(self):
        key=bytes.fromhex('fffefdfcfbfaf9f8f7f6f5f4f3f2f1f0f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff')
        ad=[bytes.fromhex('101112131415161718191a1b1c1d1e1f2021222324252627')]
        actual=self.compare(key,ad,bytes.fromhex('112233445566778899aabbccddee'))
        self.assertEqual(actual.hex(),'85632d07c6e8f37f950acd320a2ecc9340c02b9690c4dc04daef7f6afe5c')
    def test_boundaries_and_unicode(self):
        for n in [0,1,15,16,17,31,32,33,127,500,4096]:
            with self.subTest(n=n):self.compare(secrets.token_bytes(32),[b'IGT/request/v1',b'test-id',b'7'],secrets.token_bytes(n))
        self.compare(secrets.token_bytes(32),[], 'Hello! ÐŸÑ€Ð¸Ð²ÐµÑ‚! ì•ˆë…•í•˜ì„¸ìš”!'.encode())
    def test_every_tampered_byte_rejected(self):
        key=secrets.token_bytes(32);ad=[b'request',b'id',b'1']
        sealed=self.compare(key,ad,b'No plaintext before authentication')
        for i in range(len(sealed)):
            bad=sealed[:i]+bytes([sealed[i]^1])+sealed[i+1:]
            self.assertEqual(self.siv.open(key,self.lua.table_from(ad),bad),(None,b'Authentication failed'))
        for badad in [[b'response',b'id',b'1'],[b'request',b'other',b'1'],[b'request',b'id',b'2']]:
            self.assertEqual(self.siv.open(key,self.lua.table_from(badad),sealed),(None,b'Authentication failed'))
    def test_repeated_metadata_does_not_reuse_ctr_stream(self):
        key=secrets.token_bytes(32);ad=[b'request',b'id',b'1']
        a=self.compare(key,ad,b'first');b=self.compare(key,ad,b'other')
        self.assertNotEqual(a[:16],b[:16])

if __name__=='__main__':unittest.main()
