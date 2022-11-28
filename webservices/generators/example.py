#an integration is a plugin that executes a binary on the operating system that this agent is running on and turns its output into Nodes that are ingested by Secquiry

import collablio.node as cnode
import filereadutils
import json


async def generate(metadata_dict):
  n = cnode.Node(cnode.TYPE_TEXT)
  '''
  contents = ''
  await fileToImport.seek(0)
  while True:
    line = await fileToImport.read(1024)
    if not line:
        break
    contents += line.decode('utf-8')
  '''
  n.CustomData = metadata_dict['under_uid']
  n.TextData = 'blah'
  nl = []

  cnode.recursiveConvertNodesToAPIFormat(n,nl)
  print('generate(): '+json.dumps(nl))

  return {"status":"OK","detail":"Generated Successfully"}
  #return nl

