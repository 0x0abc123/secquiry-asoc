# this is launched in a thread started by the main fastAPI app

#import notifiers
#import importlib
import json
import datetime
import os
#import secretstore
#import greenstalk

# TODO: use beanstalkd instead of directly invoking the logging functions
GREENSTALK_HOST = '127.0.0.1'
GREENSTALK_PORT = 11301

CONFIG_FILE_PATH = os.path.dirname(os.path.realpath(__file__)) + '/logger.conf.json'
DEFAULT_LOG_PATH = '/tmp/secquiry-asoc.log'
LoggerConfig = None

# aws vpc_id
# aws security_groups
# aws ECS cluster
# general:  images: tool -> { containerImage, CPU/RAM }

#runners = {'fargate':AWSFargateRunner()}


def GetConfig():
    global LoggerConfig

    if LoggerConfig is not None:
        return LoggerConfig

    loadedConfigOK = False
    if os.path.isfile(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH,'r') as cf:
                LoggerConfig = json.load(cf)
            #loadedConfigOK = ASConfig['type'] != '' and ASConfig['location'] != ''
            loadedConfigOK = True
        except Exception as e:
            print(e)
            traceback.print_exc()
    if not loadedConfigOK:
        #ASConfig = {'type':'local','location':None}
        LoggerConfig = {'path':DEFAULT_LOG_PATH}
    return LoggerConfig



def logEvent(eventdata, eventtype = 'debug'):
    '''
    with greenstalk.Client((GREENSTALK_HOST, GREENSTALK_PORT)) as client:
        client.put(json.dumps({'type':ntype,'data':ndata}))
    '''
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(GetConfig()['path'],'a') as lf:
        lf.write(f'[{eventtype}] [{timestamp}] {str(eventdata)}\n')
    return

'''        
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
'''        
