import os
import json
import base64
import traceback
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

'''
{"partialkey":"fh0uhsdhfago96uhaushfsbvxczbvzu", "salt":"hao34hawfhfhkl", "secrets":{"secret1":"f167rt9bgysgdy0vfqt", "secret2":"2f075tgbusd7fgt08t4"}}
'''

STORE_FILE = os.path.dirname(os.path.realpath(__file__)) + '/secretstore.json'
LINUX_MACHINE_ID_PATH = '/etc/machine-id'
WIN_MACHINE_ID_KEY = 'HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid'


# returns base64 urlsafe encoded (32)bytes, salt is 16 bytes (base64 encoded urlsafe)
def deriveKey(passwordString, saltB64String):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=base64.urlsafe_b64decode(saltB64String),
        iterations=390000,
    )
    derivedKey = base64.urlsafe_b64encode(kdf.derive(bytes(passwordString,'utf-8')))
    return derivedKey

def encrypt(plaintextToEncrypt, passwordString, saltB64String):
    key = deriveKey(passwordString, saltB64String)
    f = Fernet(key)
    return base64.urlsafe_b64encode(f.encrypt(bytes(plaintextToEncrypt,'utf-8'))).decode('utf-8')

def decrypt(ciphertextToDecrypt, passwordString, saltB64String):
    key = deriveKey(passwordString, saltB64String)
    f = Fernet(key)
    return f.decrypt(base64.urlsafe_b64decode(ciphertextToDecrypt)).decode('utf-8')


class LocalStore:
    def __init__(self):
        self.partialStr = ''
        self.saltB64Str = ''
        self.encryptedSecrets = {}
        self.passwordStr = ''
        self.decryptedSecrets = {}
        loadedStoreOK = False
        if os.path.isfile(STORE_FILE):
            try:
                store = {}
                with open(STORE_FILE,'r') as sf:
                    store = json.load(sf)
                self.partialStr = store['partial']
                self.derivePassword()
                self.saltB64Str = store['salt']
                self.encryptedSecrets = store['secrets']
                self.decryptSecrets()
                loadedStoreOK = True
            except Exception as e:
                print(e)
                traceback.print_exc()
        if not loadedStoreOK:
            # need to create and initialise store
            self.saltB64Str = base64.urlsafe_b64encode(os.urandom(16)).decode('utf-8')
            self.partialStr = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8')
            self.decryptedSecrets = {}
            self.encryptedSecrets = {}
            self.derivePassword()
            self.save()
            
    def derivePassword(self):
        self.passwordStr = self.partialStr
        if os.name == 'nt':
            self.passwordStr += 'implement_this_for_windows'
        else:
            with open(LINUX_MACHINE_ID_PATH,'r') as f:
                mID = f.read(1024)
                self.passwordStr += mID.strip()

    def encryptSecrets(self):
        for key in self.decryptedSecrets:
            self.encryptedSecrets[key] = encrypt(self.decryptedSecrets[key], self.passwordStr, self.saltB64Str)

    def decryptSecrets(self):
        for key in self.encryptedSecrets:
            self.decryptedSecrets[key] = decrypt(self.encryptedSecrets[key], self.passwordStr, self.saltB64Str)

            
    def store(self, nameString, valueString):
        self.decryptedSecrets[nameString] = valueString
        self.encryptSecrets()
        self.save()

    def get(self, nameString):
        if nameString in self.decryptedSecrets:
            return self.decryptedSecrets[nameString]
        else:
            return None

    def save(self):
        #try:
        tmpStore = {}
        tmpStore['partial'] = self.partialStr
        tmpStore['salt'] = self.saltB64Str
        tmpStore['secrets'] = self.encryptedSecrets
        with open(STORE_FILE,'w') as sf:
            json.dump(tmpStore,sf)
        #except Exception as e:
        #    print(e)
            
            
if __name__ == '__main__':
    ls = LocalStore()
    k = input('Enter key: ')
    v = input('Enter value: ')
    if k and v:
        ls.store(k.strip(),v.strip())
    else:
        print('invalid input')
        