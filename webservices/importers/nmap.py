#an integration is a plugin that executes a binary on the operating system that this agent is running on and turns its output into Nodes that are ingested by Secquiry

import collablio.node as cnode
import collablio.client as cclient
import filereadutils
import json

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

    '''
    n = cnode.Node(cnode.TYPE_TEXT)

    contents = await filereadutils.getLinesOfTextFromFileUpload(fileToImport)
    for line in contents:
        print(line)
    n.CustomData = metadata_json['project_id']
    n.TextData = contents
    nl = []

    cnode.recursiveConvertNodesToAPIFormat(n,nl)
    print('do_import: '+json.dumps(nl))

    if 'xml' in metadata_json:
        xmlroot = await filereadutils.getXMLTreeFromFileUpload(fileToImport)
        print(xmlroot)
    '''

    allHosts = []

    root = await filereadutils.getXMLTreeFromFileUpload(fileToImport)

    for host in root.findall('host'):

        print("Host: {}".format(host.attrib))
        if not host.find('status').attrib['state'] == 'up':
            print('host is down')
            continue

        hostNode = cnode.Node(cnode.TYPE_HOST)
        allHosts.append(hostNode)
        
    #    for hostchild in host:
    #        print("    HostChild: <{}> {}".format(hostchild.tag,hostchild.attrib))

        for hostname in host.find('hostnames').findall('hostname'):
            print("    Hostname: <{}> {}".format(hostname.tag,hostname.attrib))
            annotationNode = cnode.Node(cnode.TYPE_ANNOTATION)
            hostNode.Children.append(annotationNode)
            annotationNode.Label = '[name] '+hostname.attrib['name'].lower()
            
        tmpIPv6Addr = ''
        tmpMACAddr = ''
        tmpLabel = ''
        
        for address in host.findall('address'):
            print("    Address: {}".format(address.attrib))
            annotationNode = cnode.Node(cnode.TYPE_ANNOTATION)
            hostNode.Children.append(annotationNode)
            annotationNode.Label = '[addr] '+address.attrib['addr']
            if 'vendor' in address.attrib:
                annotationNode.Detail = '[vendor] '+address.attrib['vendor']
            if address.attrib['addrtype'] == 'ipv4':
                tmpLabel = address.attrib['addr']
            elif address.attrib['addrtype'] == 'ipv6' and not tmpLabel:
                tmpIPv6Addr = address.attrib['addr']
            elif address.attrib['addrtype'] == 'mac' and not tmpLabel:
                tmpMACAddr = address.attrib['addr']
            if not tmpLabel:
                tmpLabel = tmpIPv6Addr if tmpIPv6Addr else (tmpMACAddr if tmpMACAddr else str(uuid.uuid4()))
            hostNode.Label = tmpLabel

        count = 0
        hostports = host.find('ports')
        if hostports:
            for port in hostports.findall('port'):

                print("    Port: {}".format(port.attrib))
                if port.find('state').attrib['state'] == 'open':

                    portNode = cnode.Node(cnode.TYPE_PORT)
                    hostNode.Children.append(portNode)

                    portNode.Label = port.attrib['portid'] + '/' + port.attrib['protocol']

                    service = port.find('service')
                    if not service:
                        continue

                    print("         Service: {}".format(service.attrib))

                    body = ''
                    body += service.attrib['product']+' ' if 'product' in service.attrib else ''
                    body += service.attrib['version']+' ' if 'version' in service.attrib else ''
                    body += service.attrib['extrainfo']+' ' if 'extrainfo' in service.attrib else ''
                    body += service.attrib['ostype']+' ' if 'ostype' in service.attrib else ''
                    body = body.strip()

                    UNKNOWN_SERVICE = 'Unknown Service'
                    if not body:
                        body = UNKNOWN_SERVICE
                    
                    for script in port.findall('script'):
                        print("         Script: {}".format(script.attrib))
                        scriptName = 'NSE Script: '+(script.attrib['id'] if script.attrib['id'] else '<?>')
                        body += '\n\n'+scriptName+'\n'+'-'*len(scriptName)+'\nOutput:\n'
                        for elem in script.findall('elem'):
                            print("           Elem: {}, text: {}".format(elem.attrib, elem.text))
                            if 'key' in elem.attrib and elem.text:
                                body += elem.attrib['key'] + ': ' + elem.text + '\n'
                        for table in script.findall('table'):
                            for telem in table.findall('elem'):
                                #print("           TElem: {}, text: {}".format(telem.attrib, telem.text))
                                te_key = telem.attrib['key'] if 'key' in telem.attrib else ''
                                te_text = telem.text if telem.text else ''
                                body += ' [*] '+ te_key + ': ' + te_text + '\n'
                        
                        
                    count += 1
                    if body != UNKNOWN_SERVICE:
                        textNode = cnode.Node(cnode.TYPE_TEXT)
                        portNode.Children.append(textNode)
                        textNode.TextData = body
                        textNode.Label = "NMAP scan "+portNode.Label
                        print('create node: '+str(count)+' '+textNode.Label)
                    else:
                        annotationNode = cnode.Node(cnode.TYPE_ANNOTATION)
                        portNode.Children.append(annotationNode)
                        annotationNode.Label = '(unknown service)'
                        print('create annotation: '+str(count)+' '+annotationNode.Label)

                    for c in portNode.Children:
                        c.Detail = '{}:{} nmap script'.format(hostNode.Label, portNode.Label)

        for c in hostNode.Children:
            c.Detail = '{} (nmap {})'.format(hostNode.Label, nodeLabelToImportUnder)




    #query recursively to find existing hosts under projectname

    jsonResponse =  client.fetchNodes(uid = nodeUIDToImportUnder, field = cnode.PROP_LASTMOD, op = 'gt', val = '0', ntype = cnode.TYPE_HOST)

    lookupExistingNodes = {}
    
    for nodeResult in jsonResponse['nodes']:
        lookupExistingNodes[nodeResult[cnode.PROP_LABEL]] = nodeResult
        print('located host '+nodeResult[cnode.PROP_LABEL])

    newFolder = cnode.Node(cnode.TYPE_FOLDER)
    newFolder.Label = 'Nmap Import '+fileToImport.filename.split('/')[-1]
    newFolder.UID = 'newfolder_for_scan'
    newFolder.ParentUids.append(nodeUIDToImportUnder)

    for nmapHost in allHosts:

        hostsAddedToNewFolder = False
        nodesToUpsert = []
        lookupExistingChildItems = {}

        if nmapHost.Label in lookupExistingNodes:
            nmapHost.UID = lookupExistingNodes[nmapHost.Label][cnode.PROP_UID]

            #fetch ports for existing host
            
            jsonResponse =  fetchNodes(uid = nmapHost.UID, field = cnode.PROP_LASTMOD, op = 'gt', val = '0')
            for nodeResult in jsonResponse['nodes']:
                if nodeResult[cnode.PROP_TYPE] in [cnode.TYPE_PORT, cnode.TYPE_ANNOTATION]:
                    lookupExistingChildItems[nodeResult[cnode.PROP_TYPE]+'_'+nodeResult[cnode.PROP_LABEL]] = nodeResult
                    print('found existing: '+nodeResult[cnode.PROP_LABEL]+' '+nodeResult[cnode.PROP_UID])
                                
        else:
            nmapHost.UID = nmapHost.Label
            nmapHost.ParentUids.append(newFolder.UID)
            hostsAddedToNewFolder = True
            print('host not found creating: '+nmapHost.UID)

        print('NmapHost children count = '+str(len(nmapHost.Children)))
        for childNode in nmapHost.Children:
            print('childNode type: '+childNode.Type+' childNode Label:'+childNode.Label)
            tmpkey = childNode.Type+'_'+childNode.Label
            if tmpkey in lookupExistingChildItems:
                childNode.UID = lookupExistingChildItems[tmpkey][cnode.PROP_UID]
            else:
                childNode.UID = nmapHost.UID+'_'+childNode.Label
                print('annotation/port not existing, creating new UID: '+childNode.UID)
                #nmapHost.Children.append
            
            ccount = 0
            for c in childNode.Children:
                ccount += 1
                print('text/annotations[] for port/annotation='+childNode.Label+' * port/annotaitonType='+childNode.Type+' '+str(ccount)+'/'+str(len(childNode.Children)))
            
            for grandChildNode in childNode.Children:
                grandChildNode.UID = childNode.UID+'_'+grandChildNode.Label
                print('text/annotation creating: Type='+grandChildNode.Type+' child UID='+childNode.UID+', grandchild Label='+grandChildNode.Label)
            
        '''    
        cnode.recursiveConvertNodesToAPIFormat(nmapHost, nodesToUpsert)
        if hostsAddedToNewFolder:
            nodesToUpsert.insert(0,newFolder.convert())
        '''
        nodesToUpsert.append(nmapHost)
        if hostsAddedToNewFolder:
            nodesToUpsert.insert(0, newFolder)
        
        listOfUidsUpserted = client.upsertNodes(nodesToUpsert)
        if hostsAddedToNewFolder and newFolder.UID == 'newfolder_for_scan':
           newFolder.UID = listOfUidsUpserted[0]
                

    return {"status":"OK","detail":"Imported Successfully"}
  