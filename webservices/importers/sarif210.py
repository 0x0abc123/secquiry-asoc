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

    def titleGeneratorGitleaks(rule_obj):
        return rule_obj['id']

    def titleGeneratorSemgrep(rule_obj):
        return rule_obj['id'].split('.')[-1]

    def titleGeneratorDefault(rule_obj):
        title = ''
        if 'shortDescription' in rule_obj:
            title = rule_obj['shortDescription']['text']
        elif 'messageStrings' in rule_obj and 'default' in rule_obj['messageStrings']:
            title = rule_obj['messageStrings']['default']['text']
        return title
        
    titleGenerators = {
        'gitleaks':titleGeneratorGitleaks,
        'semgrep':titleGeneratorSemgrep,
        'default':titleGeneratorDefault,
    }
    
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
    
    sarifObj = await filereadutils.getJsonObjFromFileUpload(fileToImport)
    
    runs = []

    baselineFindings = {}
    isDiffScan = 'diffscan' in metadata_json and metadata_json['diffscan']
    if isDiffScan:
        jsonResponse = client.fetchNodes(uid = nodeUIDToImportUnder, field = cnode.PROP_LASTMOD, op = 'gt', val = '0', depth = 1, ntype = cnode.TYPE_JSON)
        for nodeResult in jsonResponse['nodes']:
            bfKey = nodeResult[cnode.PROP_LABEL] + nodeResult[cnode.PROP_DETAIL] + nodeResult[cnode.PROP_CUSTOM]
            baselineFindings[bfKey] = nodeResult

    
    for run in sarifObj['runs']:
        
        rulesLookupTitle = {}
        rulesLookupSeverity = {}
        resultsNodesToAdd = []

        toolName = run['tool']['driver']['name']
        
        rulesPresent = 'rules' in run['tool']['driver']
        
        if rulesPresent:
            for rule in run['tool']['driver']['rules']:
                rulesLookupTitle[rule['id']] = titleGenerators[toolName](rule) if toolName in titleGenerators else titleGenerators['default'](rule)
                    
                # levels: error, warning, note, none
                if 'defaultConfiguration' in rule and 'level' in rule['defaultConfiguration']:
                    rulesLookupSeverity[rule['id']] = rule['defaultConfiguration']['level']
                

        findingsNode = cnode.Node(cnode.TYPE_FINDINGS)
        timestamp = str(int(time.time()))
        findingsNode.Label = f'{toolName}-{timestamp}'
        findingsNode.Detail = ''

        if 'results' in run:
            for result in run['results']:
                #result['ruleId'] = titleGenerators[toolName](rule) if toolName in titleGenerators else titleGenerators['default'](rule)
                title = ''
                severity = ''
                location = ''
                
                #title
                ruleID = result['ruleId']
                if ruleID in rulesLookupTitle:
                    title = rulesLookupTitle[ruleID]
                else:
                    title = result['message']['text']
                #severity
                if 'level' in result:
                    severity = result['level']
                elif ruleID in rulesLookupSeverity:
                    severity = rulesLookupSeverity[ruleID]
                else:
                    severity = 'note'
                #location
                if 'locations' in result:
                    loc_file = ''
                    loc_line = ''
                    if len(result['locations']) > 0:
                        if 'physicalLocation' in result['locations'][0]:
                            if 'artifactLocation' in result['locations'][0]['physicalLocation']:
                                if 'uri' in result['locations'][0]['physicalLocation']['artifactLocation']:
                                    loc_file = result['locations'][0]['physicalLocation']['artifactLocation']['uri']
                            if 'region' in result['locations'][0]['physicalLocation']:
                                if 'startLine' in result['locations'][0]['physicalLocation']['region']:
                                    loc_line = result['locations'][0]['physicalLocation']['region']['startLine']
                        location = f'{loc_file}:{loc_line}'
                
                resultNode = cnode.Node(cnode.TYPE_JSON)
                resultNode.Label = title
                resultNode.Detail = location
                resultNode.CustomData = severity
                resultNode.TextData = json.dumps(result)
                
                if isDiffScan:
                    bfKey = resultNode.Label + resultNode.Detail + resultNode.CustomData
                    if bfKey in baselineFindings:
                        continue
                findingsNode.Children.append(resultNode)

        runNode = cnode.Node(cnode.TYPE_JSON)
        runNode.Label = 'Run Details'
        runNode.Detail = ''
        runNode.CustomData = 'none'
        '''
        we don't need to include results because the finding nodes already capture this data
        we don't include rules, because they bloat the size of the json data with irrelevant info
        we don't include toolExecutionNotification, because it can sometimes bloat the size of the json data with irrelevant info
        '''
        del run['results']
        if rulesPresent:
            del run['tool']['driver']['rules']
        if 'invocations' in run and 'toolExecutionNotifications' in run['invocations'][0]:
            del run['invocations'][0]['toolExecutionNotifications']
        runNode.TextData = json.dumps(run)
        findingsNode.Children.append(runNode)
        
        findingsNode.ParentUids.append(nodeUIDToImportUnder)

        if not isDiffScan:
            findingsNode.CustomData = str(uuid.uuid4())

        runs.append(findingsNode)

    client.upsertNodes(runs)    

    return {"status":"OK","detail":"Imported Successfully"}
  