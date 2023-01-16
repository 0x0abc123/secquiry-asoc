#an integration is a plugin that executes a binary on the operating system that this agent is running on and turns its output into Nodes that are ingested by Secquiry

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

    baselineFindings = {}
    lookupByUID = {}
    
    def getBaselineScanNodeKey(node, nodeParent = None, nodeGrandParent = None):
        if not type(node) is cnode.Node:
            raise Exception("Type Error - must be a dict or collablio node")
        
        key = None
        if node.Type == cnode.TYPE_HOST:
            key = f'{node.Label}'
        else:
            if not nodeParent:
                nodeParentUIDs = node.ParentUids
                if len(nodeParentUIDs) > 0 and nodeParentUIDs[0] in lookupByUID:
                    nodeParent = lookupByUID[nodeParentUIDs[0]]
            parentlabel = nodeParent.Label if nodeParent else ''

            if node.Type == cnode.TYPE_PORT:
                key = f'{parentlabel}:{node.Label}'
            else:                
                if not nodeGrandParent:
                    nodeGrandParentUIDs = nodeParent.ParentUids if nodeParent else []
                    if len(nodeGrandParentUIDs) > 0 and nodeGrandParentUIDs[0] in lookupByUID:
                        nodeGrandParent = lookupByUID[nodeGrandParentUIDs[0]]
                grandparentlabel = nodeGrandParent.Label if nodeGrandParent else ''

                if node.Type == cnode.TYPE_JSON:
                    n_d = node.Detail
                    n_c = node.CustomData            
                    key = f'{grandparentlabel}:{parentlabel}:{node.Label}:{n_d}:{n_c}'

        if not key:
            key = str(uuid.uuid4())
        return key
        
    client = cclient.Client(metadata_json['auth_token_hdr_val'])
    
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
    
    dynscanObj = await filereadutils.getJsonObjFromFileUpload(fileToImport)
    
    nodesToUpsert = []

    isDiffScan = 'diffscan' in metadata_json and metadata_json['diffscan']
    if isDiffScan:
        jsonResponse = client.fetchNodes(uid = nodeUIDToImportUnder, field = cnode.PROP_LASTMOD, op = 'gt', val = '0', depth = 20)
        for nodeResult in jsonResponse['nodes']:
            cn = cnode.Node(None)
            cn.populateFromDict(nodeResult)
            lookupByUID[cn.UID] = cn
        for cnr in lookupByUID.values():
            bfKey = getBaselineScanNodeKey(cnr)
            baselineFindings[bfKey] = cnr

    
    for host in dynscanObj['hosts']:
        
        existingHostUID = None

        hostNode = cnode.Node(cnode.TYPE_HOST)
        timestamp = str(int(time.time()))
        hostNode.Label = host['label']
        hostNode.CustomData = json.dumps({'hostname':host['hostname'],'ip':host['ip'],'mac':host['mac']}) #''

        if isDiffScan:
            bfKey = getBaselineScanNodeKey(hostNode)
            if bfKey in baselineFindings:
                existingHostUID = baselineFindings[bfKey].UID
            else:
                nodesToUpsert.append(hostNode)
        else:
            nodesToUpsert.append(hostNode)
                
        if 'ports' in host:
            for port in host['ports']:

                existingPortUID = None
                
                portNode = cnode.Node(cnode.TYPE_PORT)
                portNode.Label = port['port']
                
                if isDiffScan:
                    bfKey = getBaselineScanNodeKey(portNode, hostNode)
                    if bfKey in baselineFindings:
                        existingPortUID = baselineFindings[bfKey].UID
                    else:
                        if existingHostUID:
                            portNode.ParentUids.append(existingHostUID)
                            nodesToUpsert.append(portNode)
                        else:
                            hostNode.Children.append(portNode)
                else:
                    hostNode.Children.append(portNode)

                if 'findings' in port:
                    for finding in port['findings']:
                        findingNode = cnode.Node(cnode.TYPE_JSON)
                        findingNode.Label = finding['title']
                        findingNode.Detail = finding['location']
                        findingNode.CustomData = finding['severity']
                        findingNode.TextData = json.dumps(finding)

                        if isDiffScan:
                            bfKey = getBaselineScanNodeKey(findingNode, portNode, hostNode)
                            if bfKey in baselineFindings:
                                continue
                            else:
                                if existingPortUID:
                                    findingNode.ParentUids.append(existingPortUID)
                                    nodesToUpsert.append(findingNode)
                                else:
                                    portNode.Children.append(findingNode)
                        else:
                            portNode.Children.append(findingNode)
        
        if not existingHostUID:
            hostNode.ParentUids.append(nodeUIDToImportUnder)
        

    client.upsertNodes(nodesToUpsert)    

    return {"status":"OK","detail":"Imported Successfully"}
  