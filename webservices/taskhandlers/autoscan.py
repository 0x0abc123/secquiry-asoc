#an integration is a plugin that executes a binary on the operating system that this agent is running on and turns its output into Nodes that are ingested by Secquiry

import collablio.node as cnode
import collablio.client as cclient
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

CONFIG_FILE_PATH = os.path.dirname(os.path.realpath(__file__)) + '/autoscan.conf.json'
ASConfig = None

# aws vpc_id
# aws security_groups
# aws ECS cluster
# general:  images: tool -> { containerImage, CPU/RAM }

#runners = {'fargate':AWSFargateRunner()}


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
            traceback.print_exc()
    if not loadedConfigOK:
        #ASConfig = {'type':'local','location':None}
        ASConfig = {}
    return ASConfig

class AWSFargateRunner:
    def __init__(self):
        self.taskDefinitionCache = {}
        self.ecs_client = boto3.client('ecs')
        pass

    def run(self, params):
        try:
            print('fargate runner')
            print(params)
            app_id = params['app_id']
            tool_id = params['tool']
            conf = GetConfig()
            vpc_subnet = conf['fargate']['vpc_subnet_id']
            sec_grp = conf['fargate']['security_group_id']
            cluster_name = conf['fargate']['cluster']
            image_conf = conf['images'][params['tool']]

            if 'cpu' not in params:
                params['cpu'] = image_conf['cpu']
            if 'mem' not in params:
                params['mem'] = image_conf['mem']

            if self.checkOrCreateTaskDefinition(params):
                response = self.ecs_client.run_task(
                    count=1,
                    cluster=cluster_name,
                    launchType='FARGATE',
                    networkConfiguration={
                        'awsvpcConfiguration': {
                            'subnets': [
                                vpc_subnet,
                            ],
                            'securityGroups': [
                                sec_grp,
                            ],
                            'assignPublicIp': 'ENABLED'
                        }
                    },
                    overrides={
                        'cpu': str(image_conf['cpu']),
                        'memory': str(image_conf['mem']),
                        'containerOverrides': [
                            {
                                'name': tool_id,
                                'environment': [
                                    {
                                        'name': 'APP_ID',
                                        'value': app_id
                                    },
                                    {
                                        'name': 'UPLOAD_URL',
                                        'value': params['upload_uri']
                                    },
                                    {
                                        'name': 'GIT_REPO',
                                        'value': params['repo_uri']
                                    },
                                    {
                                        'name': 'SECRET_STORE',
                                        'value': 'env'
                                    },
                                    {
                                        'name': 'SECRET_LOCATION',
                                        'value': params['creds']
                                    },
                                ],
                                #'cpu': 123,
                                #'memory': 123,
                                #'memoryReservation': 123,
                                #'resourceRequirements': [
                                #    {
                                #        'value': 'string',
                                #        'type': 'GPU'|'InferenceAccelerator'
                                #    },
                                #]
                            },
                        ],
                    },
                    tags=[
                        {
                            'key': 'secquiry',
                            'value': 'autoscan'
                        },
                    ],
                    taskDefinition=tool_id
                )

                if not response:
                    print('ECS run task API call failed')
                elif len(response['tasks']) < 1 or 'taskArn' not in response['tasks'][0]:
                    failurestr = json.dumps(response['failures'])
                    print(failurestr)
            else:
                print(f'no task definition found: {tool_id}')

        except Exception as e:
            print(e)
            traceback.print_exc()


    def checkOrCreateTaskDefinition(self, params):
        try:
            task_definition = params['tool']
            if task_definition in self.taskDefinitionCache:
                return True
            
            response = self.ecs_client.list_task_definitions(familyPrefix=task_definition)
            if len(response['taskDefinitionArns']) < 1:
                self.registerTaskDefinitionForTool(params)
                self.taskDefinitionCache[task_definition] = None
                return True
            else:
                return True
        except Exception as e:
            print(e)
            traceback.print_exc()
            return False

    def registerTaskDefinitionForTool(self, params):
        try:
            tool_id = params['tool']
            conf = GetConfig()
            image_conf = conf['images'][tool_id]
            
            response = self.ecs_client.register_task_definition(
                family=tool_id,
                networkMode='awsvpc',
                cpu=str(image_conf['cpu']),
                memory=str(image_conf['mem']),
                containerDefinitions=[
                    {
                        'name': tool_id,
                        'image': image_conf['image'],
                        'environment': [
                            {
                                'name': 'APP_ID',
                                'value': 'placeholder'
                            },
                            {
                                'name': 'UPLOAD_URL',
                                'value': 'placeholder'
                            },
                            {
                                'name': 'GIT_REPO',
                                'value': 'placeholder'
                            },
                            {
                                'name': 'SECRET_STORE',
                                'value': 'env'
                            },
                            {
                                'name': 'SECRET_LOCATION',
                                'value': 'placeholder'
                            },
                        ],
                    },
                ],
                requiresCompatibilities=[
                    'FARGATE',
                ],
                tags=[
                    {
                        'key': 'secquiry',
                        'value': 'autoscan'
                    },
                ],
                runtimePlatform={
                    'cpuArchitecture': 'X86_64',
                    'operatingSystemFamily': 'LINUX'
                }
            )
        except Exception as e:
            print(e)
            traceback.print_exc()

            '''
            # response:
            {
            'taskDefinition': {
                'taskDefinitionArn': 'string',
                'containerDefinitions': [
            '''
        return

def initialise(secretstore):
    return

def fetch_body_required():
    return True

def do_task(tasknode, params, client):
    app_id = params['app_id']
    # we need the asocscan container tag to use too
    git_repo_uri = params['repo_uri']
    upload_uri = params['upload_uri']
    platform = params['platform']
    cred_id = params['cred_id']  # encsecret node label or UID

    #print(params)
    m = re.search('^0x[a-f0-9]+$', cred_id.lower())
    is_uid = m is not None

    ssh_key = credentialmanager.get_credentials(creds_uid = cred_id) if is_uid else credentialmanager.get_credentials(creds_label = cred_id) 
    print(ssh_key)
    params['creds'] = ssh_key

    runner = runners[platform]
    runner.run(params)
    '''
    params['run_by'] = 'example'
    runNode = cnode.Node(cnode.TYPE_JSON)
    runNode.Label = 'Task Result'
    runNode.Detail = 'Example Task Run Details'
    runNode.TextData = json.dumps(params)
    # just return list of new nodes to be added as children under the task node, these steps will be done by tasksched:
    #runNode.ParentUids.append(tasknode[cnode.PROP_UID])
    #client.upsertNodes([runNode])    
    notifier.queueNotification('example task completed')
    '''
    return {"nodes":[], "status":"ok", "reason":""}


runners = {'fargate':AWSFargateRunner()}
