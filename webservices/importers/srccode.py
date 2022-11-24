#an integration is a plugin that executes a binary on the operating system that this agent is running on and turns its output into Nodes that are ingested by Secquiry

import collablio.node as cnode
import collablio.client as cclient
import filereadutils

'''
curl -kv -X POST  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6ImFkbWluIiwiZXhwIjoxNjY5MTcwNjU1LCJpc3MiOiJjb2xsYWJsaW8iLCJhdWQiOiJjb2xsYWJsaW8ifQ.iRFAX4LEB9rzTxNP-kEjwbe77SXnEQ5nzIELQNd7nG4' -F 'file=@lab-nmapsvsc.xml' -F 'metadata={"under_label":"2211-TESTCO-INT","xml":true}' https://10.3.3.83/webservice/import/nmap
'''
async def do_import(fileToImport, metadata_json):

    client = cclient.Client(metadata_json['auth_token_hdr_val'])
    
    # TODO: allow import under any node type, not just TYPE_PROJECT
    nodeUIDToImportUnder = ''
    nodeLabelToImportUnder = fileToImport.filename
    
    if 'under_label' in metadata_json:
        nodeLabelToImportUnder = metadata_json['under_label']
        #jsonResponse = client.fetchNodes(field = cnode.PROP_LABEL, op = 'eq', val = nodeLabelToImportUnder, depth = 20, ntype = cnode.TYPE_PROJECT)
        jsonResponse = client.fetchNodes(field = cnode.PROP_LABEL, op = 'eq', val = nodeLabelToImportUnder, depth = 20)

        for nodeResult in jsonResponse['nodes']:
            if nodeResult[cnode.PROP_LABEL] == nodeLabelToImportUnder:
                nodeUIDToImportUnder = nodeResult[cnode.PROP_UID]
                break
    else:
        nodeUIDToImportUnder = metadata_json['under_uid']
    
    print('located node to import under: '+nodeUIDToImportUnder)

    filetext = await filereadutils.getTextFromFileUpload(fileToImport)
    
    nodesToUpsert = []
    
    codeNode = cnode.Node(cnode.TYPE_CODE)
    codeNode.Label = fileToImport.filename
    codeNode.TextData = '[]\n'+filetext
    codeNode.ParentUids.append(nodeUIDToImportUnder)
    nodesToUpsert.append(codeNode)
        
    client.upsertNodes(nodesToUpsert)    

    return {"status":"OK","detail":"Imported Successfully"}
  