#an integration is a plugin that executes a binary on the operating system that this agent is running on and turns its output into Nodes that are ingested by Secquiry

import collablio.node as cnode
import collablio.client as cclient
import filereadutils
import json
import notifier
import credentialmanager
import re
import os
import uuid
import traceback
import logger
import hashlib
import urllib.request
import urllib.parse


def initialise(secretstore):
    return

def fetch_body_required():
    return True

def do_task(tasknode, params, client):
    newrepofolder_id = params['newrepofolder_id']
    git_api_uri = params['git_api_uri']
    task_upload_uri = params['task_upload_uri']
    task_platform = params['task_platform']
    task_instance = params['task_instance'] if 'task_instance' in params else None
    task_cred_id = params['task_cred_id']
    git_org_name = params['git_org_name']
    cred_id = params['cred_id']  # encsecret node label or UID

    #print(params)
    m = re.search('^0x[a-f0-9]+$', cred_id.lower())
    is_uid = m is not None

    github_pat = credentialmanager.get_credentials(creds_uid = cred_id) if is_uid else credentialmanager.get_credentials(creds_label = cred_id) 

    if not git_api_uri.startswith('https://'):
        git_api_uri = f'https://{git_api_uri}'
    if not git_api_uri.endswith('/'):
        git_api_uri += '/'
    api_url = f'{git_api_uri}orgs/{git_org_name}/repos?per_page=100&page='

    repos_list = []
    page = 1
    while True:
        try:
            page_url = f'{api_url}{page}'
            request = urllib.request.Request(page_url)
            request.headers['Authorization'] = f'Bearer {github_pat}'
            request.headers['Accept'] = 'application/vnd.github+json'
            request.headers['X-GitHub-Api-Version'] = '2022-11-28'
            resp = urllib.request.urlopen(request)
            resp_str = resp.read().decode('utf8')
            repos_in_page = json.loads(resp_str)
            if type(repos_in_page) is list:
                if len(repos_in_page) < 1:
                    break
                repos_list.extend(repos_in_page)
                page += 1
            
        except Exception as e:
            logger.logEvent(traceback.format_exc())
            break

    print(json.dumps(repos_list))

    jsonRespWithTextbody = client.fetchNodes(field = cnode.PROP_LABEL, op = 'allofterms', val = 'repo_metadata', ntype = cnode.TYPE_JSON)
    existing_repo_metadata_list = jsonRespWithTextbody['nodes']
    existing_repo_metadata_nodes = {}
    for repo_node in existing_repo_metadata_list:
        rmRepoURL = repo_node[cnode.PROP_DETAIL]
        existing_repo_metadata_nodes[rmRepoURL] = repo_node
    
    list_of_nodes = []
    for repo in repos_list:

        saveFields = {
            "full_name": repo['full_name'],
            "description": repo['description'],
            "created_at": repo['created_at'],
            "updated_at": repo['updated_at'],
            "pushed_at": repo['pushed_at'],
            "visibility": repo['visibility'],
            "homepage": repo['homepage'],
            "size": repo['size'],
            "language": repo['language'],
            "has_issues": repo['has_issues'],
            "has_projects": repo['has_projects'],
            "has_downloads": repo['has_downloads'],
            "has_wiki": repo['has_wiki'],
            "has_pages": repo['has_pages'],
            "has_discussions": repo['has_discussions'],
            "forks_count": repo['forks_count'],
            "archived": repo['archived'],
            "open_issues_count": repo['open_issues_count'],
            "topics": repo['topics']
        }
        serializedSavedFields = json.dumps(saveFields)
        metadataHash = hashlib.sha256(serializedSavedFields.encode('utf-8')).hexdigest()
        
        # is there existing repo metadata?
        # is the hash of the metadata the same?
        # update the repo metadata node OR
        # create a new folder (under the specified UID) and a child node containing the repo metadata, plus schedtasks and empty findings nodes

        repoMetadataNode = cnode.Node(cnode.TYPE_JSON)
        repoMetadataNode.Label = 'repo_metadata'
        repoMetadataNode.Detail = 'https://github.com/'+repo['full_name']
        repoMetadataNode.CustomData = metadataHash
        repoMetadataNode.TextData = serializedSavedFields

        existing_metadata_node = None

        if repoMetadataNode.Detail in existing_repo_metadata_nodes:
            existing_metadata_node = existing_repo_metadata_nodes[repoMetadataNode.Detail]
            if existing_metadata_node[cnode.PROP_CUSTOM] == repoMetadataNode.CustomData:
                continue
            else:
                # update metadata node
                repoMetadataNode.UID = existing_metadata_node[cnode.PROP_UID]
                list_of_nodes.append(repoMetadataNode)
        else:
            # create new folder, child and empty findings
            repoFolderLabel = 'repo:github:'+repo['full_name']
            repoFolderNode = cnode.Node(cnode.TYPE_FOLDER)
            repoFolderNode.Label = repoFolderLabel
            repoFolderNode.ParentUids.append(newrepofolder_id)
            repoFolderNode.Children.append(repoMetadataNode)

            gitRepoURL = f"https://github.com/{repo['full_name']}.git"
            
            # empty findings
            repoDataFindingsNode = cnode.Node(cnode.TYPE_FINDINGS)
            repoDataFindingsNode.Label = "repodata-baseline"
            repoDataFindingsNode.Detail = gitRepoURL
            repoDataFindingsNode.CustomData = str(uuid.uuid4())
            osvscannerFindingsNode = cnode.Node(cnode.TYPE_FINDINGS)
            osvscannerFindingsNode.Label = "osvscanner-baseline"
            osvscannerFindingsNode.Detail = gitRepoURL
            osvscannerFindingsNode.CustomData = str(uuid.uuid4())

            # tasks
            taskdata = {"app_id":None,"repo_uri":gitRepoURL,"upload_uri":task_upload_uri,"platform":task_platform,"cred_id":task_cred_id,"tool":None}
            if task_instance:
                taskdata['task_instance'] = task_instance

            repoDataTaskNode = cnode.Node(cnode.TYPE_TASK)
            repoDataTaskNode.Label = "repodata-"+repo['full_name']
            repoDataTaskNode.CustomData = json.dumps({"handler": "staticscan", "nextrun": "0", "every": 0, "timeunit": "minutes"})
            taskdata['app_id'] = repoDataFindingsNode.CustomData
            taskdata['tool'] = "repodata"
            repoDataTaskNode.TextData = json.dumps(taskdata)

            osvscannerTaskNode = cnode.Node(cnode.TYPE_TASK)
            osvscannerTaskNode.Label = "osvscanner-"+repo['full_name']
            osvscannerTaskNode.CustomData = json.dumps({"handler": "staticscan", "nextrun": "0", "every": 0, "timeunit": "minutes"})
            taskdata['app_id'] = osvscannerFindingsNode.CustomData
            taskdata['tool'] = "osvscanner"
            osvscannerTaskNode.TextData = json.dumps(taskdata)

            repoFolderNode.Children.extend([repoDataFindingsNode, repoDataTaskNode, osvscannerFindingsNode, osvscannerTaskNode])
            list_of_nodes.append(repoFolderNode)
        
    return {"nodes":list_of_nodes, "status":"ok", "reason":""}


