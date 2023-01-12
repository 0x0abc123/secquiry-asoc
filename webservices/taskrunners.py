#
import json
import notifier
import traceback
import logger

AWS_SUPPORTED = True
try:
    import boto3
except ImportError:
    AWS_SUPPORTED = False

class AWSFargateRunner:
    def __init__(self):
        self.taskDefinitionCache = {}
        self.ecs_client = boto3.client('ecs')
        return

    # cluster, vpcsubnet, secgrp, publicIP, taskdef, image, taskname, envvars [], cpu, mem
    def run(self, runparams):
        try:
            print('fargate runner')
            print(runparams)
            taskdef = runparams['taskdef']
            vpc_subnet = runparams['vpc_subnet'] #conf['fargate']['vpc_subnet_id']
            sec_grp = runparams['sec_grp'] #conf['fargate']['security_group_id']
            cluster_name = runparams['cluster_name'] #conf['fargate']['cluster']

            if 'cpu' not in runparams:
                runparams['cpu'] = "512"
            if 'mem' not in runparams:
                runparams['mem'] = "1024"

            if self.checkOrCreateTaskDefinition(runparams):
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
                        'cpu': str(runparams['cpu']),
                        'memory': str(runparams['mem']),
                        'containerOverrides': [
                            {
                                'name': taskdef,
                                'environment': runparams['envvars'],
                            },
                        ],
                    },
                    tags=[
                        {
                            'key': 'secquiry',
                            'value': 'taskrunner'
                        },
                    ],
                    taskDefinition=taskdef
                )

                if not response:
                    logger.logEvent('ECS run task API call failed')
                elif len(response['tasks']) < 1 or 'taskArn' not in response['tasks'][0]:
                    failurestr = json.dumps(response['failures'])
                    logger.logEvent(failurestr)
            else:
                logger.logEvent(f'no task definition found: {taskdef}')

        except Exception as e:
            print(e)
            logger.logEvent(traceback.format_exc())


    def checkOrCreateTaskDefinition(self, params):
        try:
            task_definition = params['taskdef']
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
            logger.logEvent(traceback.format_exc())
            return False

    def registerTaskDefinitionForTool(self, params):
        try:
            task_definition = params['taskdef']
            #conf = GetConfig()
            #image_conf = conf['images'][tool_id]
            envplaceholders = []
            for var in params['envvars']:
                envplaceholders.append({"name":var['name'],"value":"placeholder"})
                
            response = self.ecs_client.register_task_definition(
                family=task_definition,
                networkMode='awsvpc',
                cpu=str(params['cpu']),
                memory=str(params['mem']),
                containerDefinitions=[
                    {
                        'name': task_definition,
                        'image': params['image'],
                        'environment': envplaceholders,
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
            logger.logEvent(traceback.format_exc())

            '''
            # response:
            {
            'taskDefinition': {
                'taskDefinitionArn': 'string',
                'containerDefinitions': [
            '''
        return