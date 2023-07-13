#an integration is a plugin that executes a binary on the operating system that this agent is running on and turns its output into Nodes that are ingested by Secquiry

import collablio.node as cnode
import collablio.client as cclient
import filereadutils
import json
import logger
import html

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
    
    logger.logEvent('located node to import under: '+nodeUIDToImportUnder)


    allHosts = []

    root = await filereadutils.getXMLTreeFromFileUpload(fileToImport)

    IgnoredPluginIDs = ['10180','10287','10919','11219','12053','19506','22964','25220','31422','39470','45590','50350','54615','110723','132634']
    allHosts = []

    reportElement = root.find('Report')
    if not reportElement:
        logger.logEvent('The file does not appear to contain any report information')
        return

    for host in reportElement.findall('ReportHost'):

        hname = host.attrib['name'].lower()
        hostNode = cnode.Node(cnode.TYPE_HOST)
        allHosts.append(hostNode)

        annotationNodeHname = cnode.Node(cnode.TYPE_ANNOTATION)
        hostNode.Children.append(annotationNodeHname)
        annotationNodeHname.Label = '[name] '+hname
        
            
        tmpLabel = ''
        
        for tag in host.find('HostProperties').findall('tag'):
            annotationNode = cnode.Node(cnode.TYPE_ANNOTATION)
            if tag.attrib['name'] == 'host-rdns':
                annotationNode.Label = '[name] '+tag.text
            elif tag.attrib['name'] == 'host-ip':
                annotationNode.Label = '[addr] '+tag.text
                tmpLabel = tag.text
            if annotationNode.Label:
                hostNode.Children.append(annotationNode)

        if not tmpLabel:
            tmpLabel = str(uuid.uuid4())
        hostNode.Label = tmpLabel

        portsDict = {}
        
        count = 0
        for reportitem in host.findall('ReportItem'):
            if reportitem.attrib['pluginID'] not in IgnoredPluginIDs:

                portLabel = reportitem.attrib['port'] + '/' + reportitem.attrib['protocol'].lower()
                if portLabel != '0/tcp':
                    portNode = portsDict[portLabel] if (portLabel in portsDict) else cnode.Node(cnode.TYPE_PORT)
                    if not portNode.Label:
                        portNode.Label = portLabel
                        hostNode.Children.append(portNode)
                        portsDict[portLabel] = portNode
                
                itemLabel = str(4 - int(reportitem.attrib['severity']))+' '+reportitem.attrib['pluginName']
                body = ''

                synopsisElement = reportitem.find('synopsis')
                body += '[Synopsis]:\n'+synopsisElement.text+'\n\n' if not (synopsisElement is None) else ''
                
                cvssElement = reportitem.find('cvss3_base_score')
                body += '[CVSS Base Score]:\n'+cvssElement.text+'\n\n' if not (cvssElement is None) else ''

                descriptionElement = reportitem.find('description')
                body += '[Description]:\n'+descriptionElement.text+'\n\n' if not (descriptionElement is None) else ''

                outputElement = reportitem.find('plugin_output')
                body += '[Plugin Output]:\n'+html.unescape(outputElement.text)+'\n\n' if not (outputElement is None) else ''

                solutionElement = reportitem.find('solution')
                body += '[Solution]:\n'+solutionElement.text+'\n\n' if not (solutionElement is None) else ''

                body = body.strip()

                textNode = cnode.Node(cnode.TYPE_TEXT)
                if portLabel != '0/tcp':
                    portNode.Children.append(textNode)
                else:
                    hostNode.Children.append(textNode)

                textNode.TextData = body
                textNode.Label = itemLabel
                textNode.Detail = '{}:{} nessus plugin'.format(hostNode.Label, portLabel)

        for c in hostNode.Children:
            c.Detail = '{} (nessus)'.format(hostNode.Label)



    #query recursively to find existing hosts under projectname

    jsonResponse =  client.fetchNodes(uid = nodeUIDToImportUnder, field = cnode.PROP_LASTMOD, op = 'gt', val = '0', ntype = cnode.TYPE_HOST)

    lookupExistingNodes = {}
    
    for nodeResult in jsonResponse['nodes']:
        lookupExistingNodes[nodeResult[cnode.PROP_LABEL]] = nodeResult


    newFolder = cnode.Node(cnode.TYPE_FOLDER)
    newFolder.Label = 'Nessus Import '+fileToImport.filename.split('/')[-1]
    newFolder.UID = 'newfolder_for_scan'
    newFolder.ParentUids.append(nodeUIDToImportUnder)

    for nessusHost in allHosts:

        hostsAddedToNewFolder = False
        nodesToUpsert = []
        lookupExistingChildItems = {}

        if nessusHost.Label in lookupExistingNodes:
            nessusHost.UID = lookupExistingNodes[nessusHost.Label][cnode.PROP_UID]

            #fetch ports for existing host
            
            jsonResponse =  client.fetchNodes(uid = nessusHost.UID, field = cnode.PROP_LASTMOD, op = 'gt', val = '0')
            for nodeResult in jsonResponse['nodes']:
                if nodeResult[cnode.PROP_TYPE] in [cnode.TYPE_PORT, cnode.TYPE_ANNOTATION]:
                    lookupExistingChildItems[nodeResult[cnode.PROP_TYPE]+'_'+nodeResult[cnode.PROP_LABEL]] = nodeResult

                                
        else:
            nessusHost.UID = nessusHost.Label
            nessusHost.ParentUids.append(newFolder.UID)
            hostsAddedToNewFolder = True



        for childNode in nessusHost.Children:

            tmpkey = childNode.Type+'_'+childNode.Label
            if tmpkey in lookupExistingChildItems:
                childNode.UID = lookupExistingChildItems[tmpkey][cnode.PROP_UID]
            else:
                childNode.UID = nessusHost.UID+'_'+childNode.Label

            
            ccount = 0
            for c in childNode.Children:
                ccount += 1
            
            for grandChildNode in childNode.Children:
                grandChildNode.UID = childNode.UID+'_'+grandChildNode.Label
            

        nodesToUpsert.append(nessusHost)
        if hostsAddedToNewFolder:
            nodesToUpsert.insert(0, newFolder)
        
        listOfUidsUpserted = client.upsertNodes(nodesToUpsert)
        if hostsAddedToNewFolder and newFolder.UID == 'newfolder_for_scan':
           newFolder.UID = listOfUidsUpserted[0]
                

    return {"status":"OK","detail":"Imported Successfully"}
  