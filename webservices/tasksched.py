# this is launched in a thread started by the main fastAPI app

import taskhandlers
import importlib
import json
import time
import datetime
import collablio.node as cnode
import collablio.client as cclient
import secretstore
import logger

# load plugins
# taskhandlers
TaskHandlers = {}

for m in taskhandlers.__all__:
  try:
    taskhandler_module = importlib.import_module('taskhandlers.'+m)
    TaskHandlers[m] = taskhandler_module
    logger.logEvent(f'loaded module: {m}')
  except Exception as e:
    logger.logEvent(str(e))

print(TaskHandlers)


lastFetchTime = 0

def getLastFetchTime():
    global lastFetchTime
    returnTime = lastFetchTime
    lastFetchTime = int(time.time())
    return returnTime

# '2022-11-28 10:30:00'
def textToTime(timestamp_text):
    datetimeobj = datetime.datetime.strptime(timestamp_text, '%Y-%m-%d %H:%M')
    return datetimeobj

def timeToText(timeobj):
    return timeobj.strftime('%Y-%m-%d %H:%M')
    
def isTaskScheduledToRunNow(taskmetadata):
    if 'nextrun' not in taskmetadata:
        return True
    next_run_timestamp = taskmetadata['nextrun']
    if next_run_timestamp in ['','0','disabled']:
        return False
    try:
        return textToTime(next_run_timestamp) < datetime.datetime.now()
    except Exception as e:
        logger.logEvent(f'failed to parse time {next_run_timestamp}')
        return False

def scheduleNextTaskRun(istatus, taskmetadata):
    status = istatus.lower()
    # OK -> successful
    # failed -> task failed but keep rescheduling
    if status in ["ok","failed"]:
        #if still repeats, set nextrun
        if 'every' in taskmetadata and taskmetadata['every'] > 0:
        #TODO: be forgiving if every is a string and not an int
            # handle "until"
            if 'until' in taskmetadata and textToTime(taskmetadata['until']) < datetime.datetime.now():
                taskmetadata['nextrun'] = '0'
                return

            dt_delta = datetime.timedelta(days=taskmetadata['every'])
            # default time unit is 'days', handle other timeunits
            if 'timeunit' in taskmetadata:
                if taskmetadata['timeunit'] == 'minutes':
                    dt_delta = datetime.timedelta(minutes=taskmetadata['every'])
                elif taskmetadata['timeunit'] == 'hours':
                    dt_delta = datetime.timedelta(hours=taskmetadata['every'])
                elif taskmetadata['timeunit'] == 'weeks':
                    dt_delta = datetime.timedelta(weeks=taskmetadata['every'])

            nextrunObj = textToTime(taskmetadata['nextrun']) + dt_delta
            taskmetadata['nextrun'] = timeToText(nextrunObj)
        else:
            taskmetadata['nextrun'] = '0'

    # suspend -> task failed, stop further scheduling
    elif status == "suspend":
        taskmetadata['nextrun'] = '0'
    return
    

def run():
    # todo: read config file and determine what secretstore to use (eg. local, AWS, hashicorpVault)
    sstore = secretstore.GetStore()
    #sstore.debug()
    client = cclient.Client()
    client.setCreds(sstore.get('secquiry_user'),sstore.get('secquiry_pass'))
    #authHandler = cclient.AuthHandler(sstore.get('secquiry_user'),sstore.get('secquiry_pass'))

    for th in TaskHandlers:
        TaskHandlers[th].initialise(sstore)
        
    # dict key is tasknode.uid, value is {schedtime: <timeobj>, node: tasknode}
    pendingTasks = {}
    
    unknownHandlers = set()
    
    while True:
        time.sleep(10)
        # manage creds (do we need to refresh auth token? or do we still have time before expiry?)
        #auth_token_hdr_val = authHandler.getAuthToken()
        # query collablio for task nodes
        #client = cclient.Client(f'Bearer {auth_token_hdr_val}')
        jsonResponse = client.fetchNodes(field = cnode.PROP_LASTMOD, op = 'gt', val = getLastFetchTime(), ntype = cnode.TYPE_TASK)
        
        if 'nodes' in jsonResponse:
            for nodeReturned in jsonResponse['nodes']:
                pendingTasks[nodeReturned[cnode.PROP_UID]] = nodeReturned


        # for each task, extract parameters
        # run task in new thread/process
        # taskhandler responsible for updating collablio with task results
        for pendingTaskUID in pendingTasks:
            task_node = pendingTasks[pendingTaskUID]
            params = {}
            serialized_metadata = task_node[cnode.PROP_CUSTOM]
            task_metadata = {}
            if serialized_metadata:
                task_metadata = json.loads(serialized_metadata)
            else:
                continue

            taskhandler_name = task_metadata['handler']

            if taskhandler_name not in TaskHandlers:
                if taskhandler_name not in unknownHandlers:
                    logger.logEvent(f'taskhandler {taskhandler_name} unknown')
                    unknownHandlers.add(taskhandler_name)
                continue

            if not isTaskScheduledToRunNow(task_metadata):
                continue

            taskhandler = TaskHandlers[taskhandler_name]

            if taskhandler.fetch_body_required():
                jsonRespWithTextbody = client.fetchNodes(uid = task_node[cnode.PROP_UID], field = cnode.PROP_LASTMOD, op = 'gt', val = 0, body = True)
                task_node = jsonRespWithTextbody['nodes'][0]
                params = json.loads(task_node[cnode.PROP_TEXTDATA])
            
            # do_task() should return a list of any new nodes to upsert, tasksched assumes that the task node itself will be updated and upserted
            # { "nodes" : [],  "status" : "<status>", "reason" : "whatever message" }
            # status:   OK|failed|suspend
            # OK -> successful
            # failed -> task failed but keep rescheduling
            # suspend -> task failed, stop further scheduling
            taskResultData = taskhandler.do_task(task_node, params, client)
            resultNodes = taskResultData['nodes']
            for n in resultNodes:
                if len(n.ParentUids) < 1:
                    n.ParentUids.append(task_node[cnode.PROP_UID])
            
            #update next run times
            scheduleNextTaskRun(taskResultData['status'], task_metadata)
            
            task_node[cnode.PROP_CUSTOM] = json.dumps(task_metadata)
            cTaskNode = cnode.Node(cnode.TYPE_TASK)
            cTaskNode.populateFromDict(task_node)
            resultNodes.append(cTaskNode)
            
            client.upsertNodes(resultNodes)    

'''
task nodes:

l: whatever label
d: whatever description
c: taskhandler_name
x: {"key":"val","key":"val","key":"val"}


common key/vals:
**timestamps format:   2022-12-08 12:35:00

_metadata.nextrun: <timestamp>   0 means it's marked as done, anything > 0 is a timestamp to start
_metadata.every:  <int>,  0 means no repeat
_metadata.timeunit:  minutes|hours|days|weeks
_metadata.until:  <timestamp>   only read if repeat is > 0, if empty, then repeat forever

start_datetime = datetime.datetime.strptime('2022-11-28 10:30:00', '%Y-%m-%d %H:%M:%S')


in the HTML UI,
copy the functions and UI elements from the "table" node type
in populate jexcel, hardcode the column data (two cols of type text)

'''