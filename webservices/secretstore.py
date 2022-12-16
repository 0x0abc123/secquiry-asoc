import os
import json
import base64
import traceback
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

AWS_SUPPORTED = True
try:
    import boto3
except ImportError:
    AWS_SUPPORTED = False

'''
{"partialkey":"fh0uhsdhfago96uhaushfsbvxczbvzu", "salt":"hao34hawfhfhkl", "secrets":{"secret1":"f167rt9bgysgdy0vfqt", "secret2":"2f075tgbusd7fgt08t4"}}
'''

STORE_FILE_PATH = os.path.dirname(os.path.realpath(__file__)) + '/secretstore.json'
LINUX_MACHINE_ID_PATH = '/etc/machine-id'
WIN_MACHINE_ID_KEY = 'HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid'
CONFIG_FILE_PATH = os.path.dirname(os.path.realpath(__file__)) + '/secretstore.conf.json'

SSConfig = None

def GetConfig():
    global SSConfig

    if SSConfig is not None:
        return SSConfig

    loadedConfigOK = False
    if os.path.isfile(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH,'r') as cf:
                SSConfig = json.load(cf)
            loadedConfigOK = SSConfig['type'] != '' and SSConfig['location'] != ''
        except Exception as e:
            print(e)
            traceback.print_exc()
    if not loadedConfigOK:
        SSConfig = {'type':'local','location':None}
    return SSConfig
    
def GetStore():
    conf = GetConfig()
    if conf['type'].lower() == 'aws' and AWS_SUPPORTED:
        return AWSStore(conf['location'])
    else:
        return LocalStore(conf['location'])

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

def encrypt(plaintextToEncrypt, passwordString, saltB64String):
    key = deriveKey(passwordString, saltB64String)
    f = Fernet(key)
    return base64.urlsafe_b64encode(f.encrypt(bytes(plaintextToEncrypt,'utf-8'))).decode('utf-8')

def decrypt(ciphertextToDecrypt, passwordString, saltB64String):
    key = deriveKey(passwordString, saltB64String)
    f = Fernet(key)
    return f.decrypt(base64.urlsafe_b64decode(ciphertextToDecrypt)).decode('utf-8')

class AWSStore:
    def __init__(self, locationstring="ap-southeast-2/secquiry-asoc"):
        self.decryptedSecrets = {}
        # secretstore.conf.json : {"type":"aws","location":"us-east-2/secquiry-asoc"}
        # SecretId value is serialised JSON string: {"secquiry_user":"helloworld","secquiry_pass":"123a36excvb487628ga346"}
        location_parts = locationstring.split('/')
        region = location_parts[0]
        self.secret_id = location_parts[1] if len(location_parts) > 1 else "secquiry-asoc" 
        session = boto3.session.Session()
        self.client = session.client(
            service_name='secretsmanager',
            region_name=region
        )

        try:
            get_secret_value_response = self.client.get_secret_value(
                SecretId=self.secret_id
            )
            # Decrypts secret using the associated KMS key.
            secret = get_secret_value_response['SecretString']
            self.decryptedSecrets = json.loads(secret)
        except Exception as e:
            # For a list of exceptions thrown, see
            # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
            raise e

    def save(self):
        secretval = json.dumps(self.decryptedSecrets)
        try:
            put_secret_value_response = self.client.put_secret_value(
                SecretId=self.secret_id, SecretString=secretval
            )
        except Exception as e:
            # For a list of exceptions thrown, see
            # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
            raise e

    def store(self, nameString, valueString):
        self.decryptedSecrets[nameString] = valueString
        self.save()

    def get(self, nameString):
        if nameString in self.decryptedSecrets:
            return self.decryptedSecrets[nameString]
        else:
            return None


class LocalStore:
    def __init__(self, storeFilePath=None):
        self.secretStoreFilePath = storeFilePath if storeFilePath is not None else STORE_FILE_PATH
        self.partialStr = ''
        self.saltB64Str = ''
        self.encryptedSecrets = {}
        self.passwordStr = ''
        self.decryptedSecrets = {}
        loadedStoreOK = False
        if os.path.isfile(self.secretStoreFilePath):
            try:
                store = {}
                with open(self.secretStoreFilePath,'r') as sf:
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

    # TODO: read env var partial secret
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
        with open(self.secretStoreFilePath,'w') as sf:
            json.dump(tmpStore,sf)
        #except Exception as e:
        #    print(e)

    def debug(self):
        print(self.secretStoreFilePath)
        print(self.decryptedSecrets)
            
if __name__ == '__main__':
    ls = GetStore()
    k = input('Enter key: ')
    v = input('Enter value: ')
    if k and v:
        ls.store(k.strip(),v.strip())
    else:
        print('invalid input')
        