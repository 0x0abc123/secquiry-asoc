import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def generateAESGCMSecrets():
    return {
        "key" :  AESGCM.generate_key(bit_length=128),
        "aad" :  base64.urlsafe_b64encode(os.urandom(12))
    }

# returns base64 urlsafe encoded (32)bytes, salt is 16 bytes (base64 encoded urlsafe)
def deriveKey(passwordString, saltB64String):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=base64.urlsafe_b64decode(saltB64String),
        iterations=390000,
        backend=default_backend()
    )
    derivedKey = base64.urlsafe_b64encode(kdf.derive(bytes(passwordString,'utf-8')))
    return derivedKey

def fernet_encrypt(plaintextToEncrypt, passwordString, saltB64String):
    key = deriveKey(passwordString, saltB64String)
    f = Fernet(key)
    return base64.urlsafe_b64encode(f.encrypt(bytes(plaintextToEncrypt,'utf-8'))).decode('utf-8')

def fernet_decrypt(ciphertextToDecrypt, passwordString, saltB64String):
    key = deriveKey(passwordString, saltB64String)
    f = Fernet(key)
    return f.decrypt(base64.urlsafe_b64decode(ciphertextToDecrypt)).decode('utf-8')

def aesgcm_encrypt(plaintextToEncrypt,secrets):
    key = secrets['key']
    aad = secrets['aad']
    nonce = os.urandom(12)
    b64str_nonce = base64.urlsafe_b64encode(nonce).decode('utf-8')
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, bytes(plaintextToEncrypt,'utf-8'), aad)
    b64str_ct = base64.urlsafe_b64encode(ct).decode('utf-8')
    return f"{b64str_ct}.{b64str_nonce}"

def aesgcm_decrypt(ciphertextDotNonce,secrets):
    key = secrets['key']
    aad = secrets['aad']
    parts = ciphertextDotNonce.split(".")
    b64str_nonce = parts[1]
    b64str_ct = parts[0]
    nonce = base64.urlsafe_b64decode(bytes(b64str_nonce,'utf-8'))
    ct = base64.urlsafe_b64decode(bytes(b64str_ct,'utf-8'))
    aesgcm = AESGCM(key)
    pt = aesgcm.decrypt(nonce, ct, aad)
    return pt.decode('utf-8')
