from fastapi import Request, Response
import cryptohelpers
import authhelpers

"""
Common
"""

PERM_READ = 'r'
PERM_WRITE = 'w'
PERM_ADD_OUT = 'o'
PERM_ADD_IN = 'i'
PERM_ADD_LNK = 'l'
PERM_ADD_INL = 'n'
PERM_DEL = 'd'

allowedPredicatesAndMappings = {
    "Client": {"l":"code", "d":"name"},
    "Project": {"l":"code", "d":"name","m":"last_modified"},
    "Folder": {"l":"code", "d":"name","m":"last_modified"},
}

permissionsForMethod = {
    "PUT": PERM_ADD_OUT,
    "PATCH": PERM_WRITE,
    "PATCHin": PERM_ADD_IN,
    "PATCHinl": PERM_ADD_INL,
    "DELETE": PERM_DEL
}

def CheckUserCanAccessNode(node: dict, userdata: dict, permissionsRequired: str):
    uid = userdata["uid"]
    if (node["e"] == userdata["uid"]) or userdata.get(authhelpers.ADMIN_FIELD):
        return True
    permissionsMet = True
    for perm in permissionsRequired:
        permissionsMet = permissionsMet and (perm in node["a"])
    return permissionsMet

"""---------------------
Client -> Server  checks
---------------------"""
def validateAccess(node: dict, userdata: dict, expectedType: str, permissionsRequired: str):
    if expectedType is not None and node["ty"] != expectedType:
        return False
    return CheckUserCanAccessNode(node, userdata, permissionsRequired)

def GetDecryptedState(encryptedState: str, userdata: dict):
    s = cryptohelpers.aesgcm_decrypt(encryptedState.strip('~'), userdata[authhelpers.AESGCMSECRETS_FIELD])
    s_parts = s.split('|')
    node_uid = s_parts[0]
    owner_uid = s_parts[1]
    permissions = '|'.join(s_parts[2])
    ntype = s_parts[3]
    return {
        "uid": node_uid,
        "e": owner_uid,
        "a": permissions,
        "ty": ntype
        }

def ValidateAndUnpack(encryptedState: str, userdata: dict, expectedType: str, permissionsRequired: str = PERM_READ):
    n = GetDecryptedState(encryptedState, userdata)
    if validateAccess(n, userdata, expectedType, permissionsRequired):
        return n
    else:
        return None

async def CheckAccessForRequest(request: Request, userdata: dict):
    uid = userdata["uid"]
    method = request.method
    path = request.url.path
    path_components = path.split('/')
    ntype = path_components[1] if len(path_components) > 1 else ""

    print(f"checkAccessForReq uid: {uid}, path: {path}, method: {method}")

    if ntype == "init":
        return True

    if ntype not in allowedPredicatesAndMappings:
        return False

    nodeData = []

    # retrieve
    if method == "GET":
        es = path_components[2]
        n = ValidateAndUnpack(es, userdata, ntype, PERM_READ)
        if n is None:
            return False
        nodeData.append(n)
        request.state.nodeData = nodeData
        return True

    requestJson = await request.json()

    # retrieve
    if method == "POST":
        for es in requestJson:
            n = ValidateAndUnpack(es, userdata, ntype, PERM_READ)
            if n is None:
                return False
            nodeData.append(n)
        request.state.nodeData = nodeData
        return True

    # create, update, delete
    if method in ["PUT","PATCH"]:
        if path_components[2].startswith('~'):
            edgeData = None
            if method == "PATCH":
                if len(path_components) > 3:
                    edgeType = path_components[3]
                    if edgeType in ['in','inl']:
                        method = method + edgeType
                        addIncomingNodes = []
                        delIncomingNodes = []
                        permission = PERM_ADD_OUT if edgeType == 'in' else PERM_ADD_LNK
                        for es in requestJson['add']:
                            n = ValidateAndUnpack(es, userdata, None, permission)
                            if n is None:
                                return False
                            addIncomingNodes.append(n)
                        for es in requestJson['del']:
                            n = ValidateAndUnpack(es, userdata, None, permission)
                            if n is None:
                                return False
                            delIncomingNodes.append(n)
                        edgeData = { "add": addIncomingNodes, "del": delIncomingNodes }

            es = path_components[2] 
            n = ValidateAndUnpack(es, userdata, ntype, permissionsForMethod[method])
            if n is None:
                return False
            n["data"] = requestJson if edgeData is None else edgeData
            nodeData.append(n)
            request.state.nodeData = nodeData
            return True


        for es in requestJson:
            n = ValidateAndUnpack(es, userdata, ntype, permissionsForMethod[method])
            if n is None:
                return False
            n["data"] = requestJson[es]
            nodeData.append(n)
        request.state.nodeData = nodeData
        return True

    return False

"""---------------------
Server -> Client  checks
---------------------"""

def GetEncryptedStateString(node: dict, userdata: dict):
    node_uid = node.get("uid")
    owner_uid = node["e"] if "e" in node else ""
    permissions = node["a"].replace('|','') if "a" in node else ""
    ntype = node.get("ty")
    return '~'+cryptohelpers.aesgcm_encrypt(
        f'{node_uid}|{owner_uid}|{permissions}|{ntype}',
        userdata[authhelpers.AESGCMSECRETS_FIELD]
        )

def FilterAllowedPredicates(nodes: list, userdata: dict):
    processedNodes = []
    for node in nodes:
        sanitisedNode = {}
        predicatesForType = allowedPredicatesAndMappings.get(node["ty"])
        if not predicatesForType:
            continue
        for predicateName in predicatesForType:
            if predicateName in node:
                mappedName = predicatesForType[predicateName]
                sanitisedNode[mappedName] = node[predicateName]
        sanitisedNode["es"] = GetEncryptedStateString(node, userdata)
        processedNodes.append(sanitisedNode)
    return processedNodes

def FilterNodesWithoutReadPermission(nodes: list, userdata: dict):
    FilteredNodes = []
    for node in nodes:
        if CheckUserCanAccessNode(node, userdata, PERM_READ):
            FilteredNodes.append(node)
    return FilteredNodes

def GenerateResponse(nodes: list, userdata: dict):
    nodesUserCanRead = FilterNodesWithoutReadPermission(nodes, userdata)
    nodesWithAllowedPredicates = FilterAllowedPredicates(nodesUserCanRead, userdata)
    responsedata = str(nodesWithAllowedPredicates)
    return Response(responsedata)

'''
retreival:
GET /ntype/<es>
POST /ntype
      [<es>,<es>,…]

create:
PUT /ntype/<es>
      {data}
  or for multiple subjects
PUT /ntype
      {<es>:{data}, <es>:{data}, …}

update:
PATCH /ntype/<es>
      {data}
  or for multiple subjects
PATCH /ntype
      {<es>:{data}, <es>:{data}, …}
*edge modification
PATCH /ntype/<es>/[in|inl]    <--- you wouldn't change the out or lnk, instead: use PUT/DELETE to add or remove child, or PATCH /childtype/<child_es>/[in/inl]
      {
          "add":[<es>,<es>,…],
          "del":[<es>,<es>,…],
      }

delete:
DELETE /ntype/<es>
  or for multiple subjects
DELETE /ntype
      {<es>:{data}, <es>:{data}, …}

'''