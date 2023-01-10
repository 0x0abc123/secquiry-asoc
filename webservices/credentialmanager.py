# credentials
import collablio.node as cnode
import collablio.client as cclient
import filereadutils
import secretstore
import logger
import json

import random
import sys
import re
import os
import time

import copy
import datetime
import uuid
import traceback

import base64
import io

def save_credentials(metadata_dict):
    auth_token = metadata_dict['auth_token_hdr_val']
    client = cclient.Client(auth_token)

    plaintext_creds = metadata_dict['creds']
    sstore = secretstore.GetStore()
    enc_key_pass = sstore.get('credential_enc_pass')
    saltB64 = base64.urlsafe_b64encode(os.urandom(16)).decode('utf-8')
    ciphertext = secretstore.encrypt(plaintext_creds, enc_key_pass, saltB64)

    # collablio node textdata containing encrypted creds will be of the form: dWa1M3NlUta0JnS0N6eV9IZUhxNTgwZnE3N1lwdHc9PQ==$CpmVKeLQT1ptHj4V94A2ZQ==
    # split using "$"
    # first part is ciphertext, second is the salt
    textdata = f'{ciphertext}${saltB64}'
    
    credsNode = cnode.Node(cnode.TYPE_CREDENTIALS)
    credsNode.Label = metadata_dict['label']
    credsNode.Detail = metadata_dict['description']
    credsNode.TextData = textdata
    credsNode.ParentUids.append(metadata_dict['under_uid'])
    client.upsertNodes([credsNode])  
    
    return {"status":"OK","detail":"Generated Successfully"}

def get_credentials(creds_uid=None, creds_label=None):
    if creds_uid == None and creds_label == None:
        raise Exception('Get Credentials must be supplied with either a UID or Label')
    sstore = secretstore.GetStore()
    enc_key_pass = sstore.get('credential_enc_pass')
    client = cclient.Client()
    client.setCreds(sstore.get('secquiry_user'),sstore.get('secquiry_pass'))

    # client fetch node using uid or label
    # get textdata from node
    #parts = credsNode.TextData.split('$')
    jsonResponse = {}
    if creds_uid != None:
        jsonResponse = client.fetchNodes(uid = creds_uid, field = cnode.PROP_LASTMOD, op = 'gt', val = 0, depth = 0, ntype = cnode.TYPE_CREDENTIALS, body = True)
    else:
        jsonResponse = client.fetchNodes(field = cnode.PROP_LABEL, op = 'eq', val = creds_label, ntype = cnode.TYPE_CREDENTIALS, body = True)
        
    logger.logEvent(f'creds_uid: {creds_uid}, creds_label: {creds_label}')
    logger.logEvent(json.dumps(jsonResponse))
    textdata = None
    if 'nodes' in jsonResponse:
        for nodeReturned in jsonResponse['nodes']:
            textdata = nodeReturned[cnode.PROP_TEXTDATA]
            break

    if not textdata:
        raise Exception('Credentials node text data is empty')
    # collablio node textdata containing encrypted creds will be of the form: dWa1M3NlUta0JnS0N6eV9IZUhxNTgwZnE3N1lwdHc9PQ==$CpmVKeLQT1ptHj4V94A2ZQ==
    # split using "$"
    # first part is ciphertext, second is the salt
    parts = textdata.split('$')
    ciphertext_creds = parts[0]
    saltB64 = parts[1]
    plaintext = secretstore.decrypt(ciphertext_creds, enc_key_pass, saltB64)

    
    return plaintext

