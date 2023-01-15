#an integration is a plugin that executes a binary on the operating system that this agent is running on and turns its output into Nodes that are ingested by Secquiry

import collablio.node as cnode
import collablio.client as cclient
import taskrunners 
import filereadutils
import json
import notifier
import credentialmanager
import re
import os
import traceback
import logger

AWS_SUPPORTED = True
try:
    import boto3
except ImportError:
    AWS_SUPPORTED = False

CONFIG_FILE_PATH = os.path.dirname(os.path.realpath(__file__)) + '/dynamicscan.conf.json'
ASConfig = None


def GetConfig():
    global ASConfig

    if ASConfig is not None:
        return ASConfig

    loadedConfigOK = False
    if os.path.isfile(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH,'r') as cf:
                ASConfig = json.load(cf)
            #loadedConfigOK = ASConfig['type'] != '' and ASConfig['location'] != ''
            loadedConfigOK = True
        except Exception as e:
            print(e)
            logger.logEvent(traceback.format_exc())
    if not loadedConfigOK:
        #ASConfig = {'type':'local','location':None}
        ASConfig = {}
    return ASConfig


def getParamsFargate(conf, instance=None):
    params = {}
    params['vpc_subnet'] = conf['fargate'][instance]['vpc_subnet_id'] if instance else conf['fargate']['vpc_subnet_id']
    params['sec_grp'] = conf['fargate'][instance]['security_group_id'] if instance else conf['fargate']['security_group_id']
    params['cluster_name'] = conf['fargate'][instance]['cluster'] if instance else conf['fargate']['cluster']
    return params

def getParamsWebhook(conf, instance=None):
    params = {}
    params['url'] = conf['webhook'][instance]['url'] if instance else conf['webhook']['url']
    params['method'] = conf['webhook'][instance]['method'] if instance else conf['webhook']['method']
    return params

paramsLoaders = {
    "fargate" : getParamsFargate,
    "webhook" : getParamsWebhook,
}

def initialise(secretstore):
    return

def fetch_body_required():
    return True

def do_task(tasknode, params, client):
    tool = params['tool']
    var_dict = params['vars']
    # we need the asocscan container tag to use too
    #upload_uri = params['upload_uri']
    platform = params['platform']
    cred_id = params['cred_id'] if 'cred_id' in params else None # encsecret node label or UID

    plaintextcreds = ''
    if cred_id:
        m = re.search('^0x[a-f0-9]+$', cred_id.lower())
        is_uid = m is not None
        plaintextcreds = credentialmanager.get_credentials(creds_uid = cred_id) if is_uid else credentialmanager.get_credentials(creds_label = cred_id) 
        var_dict['SECRET'] = plaintextcreds

    env = [{'name':x,'value':var_dict[x]} for x in var_dict]

            
    conf = GetConfig()
    image_conf = conf['images'][tool]
    instance = params['instance'] if 'instance' in params else None
    
    runparams = paramsLoaders[platform](conf, instance)
    runparams['image'] = image_conf['image']
    runparams['cpu'] = params['cpu'] if 'cpu' in params else image_conf['cpu']
    runparams['mem'] = params['mem'] if 'mem' in params else image_conf['mem']
    runparams['envvars'] = env
    runparams['taskdef'] = tool

    runner = runners[platform]
    runner.run(runparams)
    #print(runparams)
    return {"nodes":[], "status":"ok", "reason":""}


runners = {
    'fargate': taskrunners.AWSFargateRunner(),
    'webhook': taskrunners.WebhookRunner(),
}
