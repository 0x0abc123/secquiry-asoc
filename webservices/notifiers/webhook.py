#an integration is a plugin that executes a binary on the operating system that this agent is running on and turns its output into Nodes that are ingested by Secquiry

import urllib.request
import urllib.parse
import filereadutils
import appconfig
import json
import os

CONFIG_FILE = os.path.dirname(os.path.realpath(__file__)) + '/webhook.conf.json'
WEBHOOK_URL = ''

PROXY_URL = appconfig.getValue("proxy")
if PROXY_URL:
    PROXY_URL = PROXY_URL.replace('http://','')

# "instant", "mail"
def notifier_type():
    return "instant"

# ['example_api_key']
def secrets_required():
    return []

def init(secretsRequired = {}):
    global WEBHOOK_URL
    # save secrets required
    # plus load and process any config here
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE,'r') as cf:
                store = json.load(cf)
            WEBHOOK_URL = store['url']
        except Exception as e:
            logger.logEvent(f'webhook error loading config: {e}')
            traceback.print_exc()
    

def send_notification(message_body, content_type = 'text/plain'):
    if not WEBHOOK_URL:
        return
        
    req = urllib.request.Request(WEBHOOK_URL, data=message_body.encode('utf8'), headers={'content-type': content_type})
    if PROXY_URL:
        req.set_proxy(PROXY_URL,'http')
    response = urllib.request.urlopen(req)
