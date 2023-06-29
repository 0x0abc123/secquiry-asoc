import os
import json
import traceback
import logger

'''
{"collablio_url":"http://127.0.0.1:5000","sso":"oidc_aws","oidc_iss":"https://login.microsoftonline.com/5f135576-8928-f43c-4cab-dfcdddf844b4/v2.0","sso_pubkey_url":"https://public-keys.auth.elb.ap-southeast-2.amazonaws.com","proxy":"172.31.25.64:8888"}
'''

CONFIG_FILE_PATH = os.path.dirname(os.path.realpath(__file__)) + '/app.conf.json'

AppConfig = None

def GetConfig():
    global AppConfig

    if AppConfig is not None:
        return AppConfig

    loadedConfigOK = False
    if os.path.isfile(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH,'r') as cf:
                AppConfig = json.load(cf)
            loadedConfigOK = 'collablio_url' in AppConfig
        except Exception as e:
            logger.logEvent(e)
            logger.logEvent(traceback.format_exc())
    if not loadedConfigOK:
        AppConfig = {'collablio_url':'http://127.0.0.1:5000'}
    return AppConfig
    


def getValue(nameString):
    conf = GetConfig()
    if nameString in conf:
        return conf[nameString]
    else:
        return None



        