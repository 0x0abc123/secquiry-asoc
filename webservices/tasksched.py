# this is launched in a thread started by the main fastAPI app

import taskhandlers
import importlib
import json
import time
import datetime
import collablio.node as cnode
import collablio.client as cclient
import secretstore

# collablio auth
class AuthHandler:
    def __init__(self, username, password):
        self.auth_token_hdr_val = None #_auth_token_hdr_val
        self.user = username
        self.passwd = password
        self.lastAuthTime = datetime.datetime(1970,1,1)

    def getAuthToken(self):
        mins90 = datetime.timedelta(minutes=90)
        now = datetime.datetime.now()
        if not self.auth_token_hdr_val or self.lastAuthTime + mins90 < now:
            self.auth_token_hdr_val = cclient.LoginAndGetToken(self.user, self.passwd)
            self.lastAuthTime = now
        print(self.auth_token_hdr_val)
        return self.auth_token_hdr_val

# load plugins
# taskhandlers
TaskHandlers = {}

for m in taskhandlers.__all__:
  try:
    taskhandler_module = importlib.import_module('taskhandlers.'+m)
    TaskHandlers[m] = taskhandler_module
    print(f'loaded module: {m}')
  except Exception as e:
    print(str(e))

print(TaskHandlers)

def run_task(taskhandler_name, params):
    if taskhandler_name not in TaskHandlers:
        pass
    taskhandler = TaskHandlers[taskhandler_name]
    return


def run():
    # todo: read config file and determine what secretstore to use (eg. local, AWS, hashicorpVault)
    sstore = secretstore.LocalStore()
    authHandler = AuthHandler(sstore.get('secquiry_user'),sstore.get('secquiry_pass'))

    while True:
        time.sleep(10)
        print('tasksched sleep 10')
        # manage creds (do we need to refresh auth token? or still time before expiry?)
        auth_token_hdr_val = authHandler.getAuthToken()
        # query collablio for task nodes
        client = cclient.Client(f'Bearer {auth_token_hdr_val}')
        jsonResponse = client.fetchNodes(field = cnode.PROP_LASTMOD, op = 'gt', val = 0, ntype = cnode.TYPE_TASK)
        print(json.dumps(jsonResponse))
        # for each task, extract parameters
        # run task in new thread/process
        # taskhandler responsible for updating collablio with task results
        
        
        
'''
task nodes:

l: whatever label
d: whatever description
c: taskhandler_name
x: [["key","val"],["key","val"],["key","val"]]

in the HTML UI,
copy the functions and UI elements from the "table" node type
in populate jexcel, hardcode the column data (two cols of type text)

'''