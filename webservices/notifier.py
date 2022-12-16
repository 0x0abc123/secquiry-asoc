# this is launched in a thread started by the main fastAPI app

import notifiers
import importlib
import json
import secretstore
import greenstalk

GREENSTALK_HOST = '127.0.0.1'
GREENSTALK_PORT = 11300

InstantNotifiers = []
MailNotifiers = []

for m in notifiers.__all__:
  try:
    notifier_module = importlib.import_module('notifiers.'+m)
    if notifier_module.notifier_type().lower() == "instant":
        InstantNotifiers.append(notifier_module)
    else:
        MailNotifiers.append(notifier_module)

    print(f'loaded module: {m}')
  except Exception as e:
    print(str(e))

print('InstantNotifiers loaded:')
print(InstantNotifiers)
print('MailNotifiers loaded:')
print(MailNotifiers)

def queueNotification(ndata, ntype = 'instant'):
    with greenstalk.Client((GREENSTALK_HOST, GREENSTALK_PORT)) as client:
        client.put(json.dumps({'type':ntype,'data':ndata}))
    return
        
def run():
    # todo: read config file and determine what secretstore to use (eg. local, AWS, hashicorpVault)
    sstore = secretstore.GetStore()

    allNotifiers = InstantNotifiers + MailNotifiers
    for notifier in allNotifiers:
        secretsDict = {}
        secrets_it_wants = notifier.secrets_required()
        for secret in secrets_it_wants:
            tmpval = sstore.get(secret)
            if not tmpval:
                tmpval = ''
            secretsDict[secret] = tmpval
        notifier.init(secretsDict)
    
    with greenstalk.Client((GREENSTALK_HOST, GREENSTALK_PORT)) as client:
        while True:
            try:
                job = client.reserve()
                payload = json.loads(job.body)
                p_type = payload["type"]
                p_data = payload["data"]
                if p_type == 'instant':
                    for inotifier in InstantNotifiers:
                        inotifier.send_notification(p_data)
                else:
                    for mnotifier in MailNotifiers:
                        mnotifier.send_notification(p_data)

                client.delete(job)
            except Exception as e:
                print(str(e))
