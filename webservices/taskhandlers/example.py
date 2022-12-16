#an integration is a plugin that executes a binary on the operating system that this agent is running on and turns its output into Nodes that are ingested by Secquiry

import collablio.node as cnode
import collablio.client as cclient
import filereadutils
import json
import notifier

def fetch_body_required():
    return True

def do_task(tasknode, params, client):
    #n = cnode.Node(cnode.TYPE_TEXT)
    #params = json.loads(tasknode[cnode.PROP_TEXTDATA])
    params['run_by'] = 'example'
    runNode = cnode.Node(cnode.TYPE_JSON)
    runNode.Label = 'Task Result'
    runNode.Detail = 'Example Task Run Details'
    runNode.TextData = json.dumps(params)
    # just return list of new nodes to be added as children under the task node, these steps will be done by tasksched:
    #runNode.ParentUids.append(tasknode[cnode.PROP_UID])
    #client.upsertNodes([runNode])    
    notifier.queueNotification('example task completed')
    return {"nodes":[runNode], "status":"ok", "reason":""}
