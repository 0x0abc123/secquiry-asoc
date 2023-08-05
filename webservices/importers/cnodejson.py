import collablio.node as cnode
import collablio.client as cclient
import filereadutils
import json
import time
import uuid

'''
curl -kv -X POST  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6ImFkbWluIiwiZXhwIjoxNjY5MTcwNjU1LCJpc3MiOiJjb2xsYWJsaW8iLCJhdWQiOiJjb2xsYWJsaW8ifQ.iRFAX4LEB9rzTxNP-kEjwbe77SXnEQ5nzIELQNd7nG4' -F 'file=@lab-nmapsvsc.xml' -F 'metadata={"under_label":"2211-TESTCO-INT","xml":true}' https://10.3.3.83/webservice/import/nmap
'''
async def do_import(fileToImport, metadata_json):

    client = cclient.client #Client(metadata_json['auth_token_hdr_val'])
    
    nodeUIDToImportUnder = ''
    nodeLabelToImportUnder = fileToImport.filename
    
    if 'under_label' in metadata_json:
        nodeLabelToImportUnder = metadata_json['under_label']
        jsonResponse = client.fetchNodes(field = cnode.PROP_LABEL, op = 'eq', val = nodeLabelToImportUnder, depth = 20)

        for nodeResult in jsonResponse['nodes']:
            if nodeResult[cnode.PROP_LABEL] == nodeLabelToImportUnder:
                nodeUIDToImportUnder = nodeResult[cnode.PROP_UID]
                break
    else:
        nodeUIDToImportUnder = metadata_json['under_uid']
    
    jsonObjToImport = await filereadutils.getJsonObjFromFileUpload(fileToImport)
    
    nodesToUpsert = []
    
    for node in jsonObjToImport:
        if cnode.PROP_TYPE not in node or cnode.PROP_LABEL not in node:
            continue # skip any objects that don't appear to be collablio nodes        
        if cnode.PROP_PARENTLIST not in node or len(node[cnode.PROP_PARENTLIST]) < 1:
            node[cnode.PROP_PARENTLIST] = [{'uid':None}]
        if node[cnode.PROP_PARENTLIST][0][cnode.PROP_UID] is None:
            node[cnode.PROP_PARENTLIST][0][cnode.PROP_UID] = nodeUIDToImportUnder

        nodesToUpsert.append(node)
            
    client.upsertNodes(nodesToUpsert, convertToAPIFormat=False)    

    return {"status":"OK","detail":"Imported Successfully"}
  