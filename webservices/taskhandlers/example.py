#an integration is a plugin that executes a binary on the operating system that this agent is running on and turns its output into Nodes that are ingested by Secquiry

import collablio.node as cnode
import filereadutils
import json


async def do_import(fileToImport, metadata_json):
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
  contents = await filereadutils.getLinesOfTextFromFileUpload(fileToImport)
  for line in contents:
    print(line)
  n.CustomData = metadata_json['under_uid']
  n.TextData = contents
  nl = []

  cnode.recursiveConvertNodesToAPIFormat(n,nl)
  print('do_import: '+json.dumps(nl))

  if 'xml' in metadata_json:
    xmlroot = await filereadutils.getXMLTreeFromFileUpload(fileToImport)
    print(xmlroot)

  return {"status":"OK","detail":"Imported Successfully"}
  #return nl

