# uvicorn main:app --port 8800

from fastapi import FastAPI, Header, Depends, HTTPException, UploadFile, Form, Request, Response, status
from fastapi.responses import StreamingResponse
import importlib
import json
import logger
import appconfig
import authhelpers
import accesscontrol as AC
import collablio.client as cclient
import collablio.node as cnode

app = FastAPI()

client = cclient.client


ANONYMOUS_ROUTE_PREFIXES = [
   "ssoconfig",
   "login",
   "debug"
]


authMiddleware = authhelpers.AuthMiddleware(
    anonymousRoutePrefixes=ANONYMOUS_ROUTE_PREFIXES, 
    otherConditions=AC.CheckAccessForRequest
    )

def getUserData(request: Request):
    return request.state.usrdata

def getNodeData(request: Request):
    return request.state.nodeData


@app.middleware("http")
async def check_auth(request: Request, call_next):
    response = await authMiddleware.getAuthorisation(request)
    if response:
        return response
    response = await call_next(request)
    return response

@app.get("/tmpauthcookie")
def get_tmpauth(request: Request):
    user_uid = request.state.usrdata.get('uid')
    response = Response()
    response.set_cookie(
        "Authorization", 
        authhelpers.create_jwt("tmpauth", user_uid), 
        max_age=60, 
        path="/", 
        secure=True, 
        httponly=True, 
        samesite="strict")
    return response


@app.get("/ssoconfig")
async def get_ssoconfig():
    return {"sso": appconfig.getValue('sso')}

@app.post("/login/sso/{sso_type}")
async def post_loginsso(sso_type: str, request: Request):
    auth_token = None
    if sso_type == 'oidc_aws':
        auth_token = authhelpers.login_oidc_aws(request)
    return {"token": auth_token}

@app.post("/login/default")
async def post_logindefault(request: Request):
    logindata = await request.json()
    auth_token = authhelpers.login_default(logindata)
    return {"token": auth_token}

@app.get("/init")
async def api_init(request: Request):
    userData = getUserData(request)
    user_uid = userData.get('uid')
    querydata = {
        "rootIds": [user_uid],
        "rootQuery": None,
        "recurse": "lnk",
        "depth": 1,
        "filters": {
            "or": [
                {"field": "ty","op": "eq","val": "Client"},
                {"field": "ty","op": "eq","val": "Project"}
            ]
        },
        "select":["uid","ty","l","d","c","a","e","m"]
    }
    nodesReturned = client.ExecQuery(querydata)
    return AC.GenerateResponse(nodesReturned, userData)


@app.get("/Project/{es}")
async def api_get_project(request: Request, es: str):
    userData = getUserData(request)
    nodeData = getNodeData(request)
    user_uid = userData.get('uid')
    querydata = {
        "rootIds": [nodeData[0].get('uid')],
        "rootQuery": None,
        "recurse": "out",
        "depth": 1,
        "filters": {
            "or": [
                {"field": "ty","op": "eq","val": "Folder"},
                {"field": "ty","op": "eq","val": "Note"},
            ]
        },
        "select":["uid","ty","l","d","c","a","e","m"]
    }
    nodesReturned = client.ExecQuery(querydata)
    return AC.GenerateResponse(nodesReturned, userData)


@app.get("/debug/req_headers")
async def do_debug(request: Request):
    if not appconfig.getValue('debug'):
        return {}
    return {"requestdata":request.headers}

@app.get("/debug/test")
def get_debug_test(request: Request):
    response = Response(json.dumps({"result": "hello"}))
    return response

@app.post("/debug/test")
async def post_debug_test(request: Request):
    reqdata = await request.json()
    response = Response(json.dumps({"result": reqdata['input']}))
    return response

@app.post("/query")
async def api_querypost(request: Request):
    querydata = await request.json()
    return client.queryPostObj(querydata)

@app.post("/move")
async def api_movepost(request: Request):
    nodesdata = await request.json()
    return client.moveNodesPostObj(nodesdata)

@app.post("/link")
async def api_linkpost(request: Request):
    nodesdata = await request.json()
    return client.linkNodesPostObj(nodesdata)

@app.post("/unlink")
async def api_unlinkpost(request: Request):
    nodesdata = await request.json()
    return client.unlinkNodesPostObj(nodesdata)

@app.post("/upsert")
async def api_upsertpost(request: Request):
    nodesdata = await request.json()
    return client.upsertNodesPostObj(nodesdata)

@app.post("/upload")
def api_uploadfile(filedata: UploadFile, p: str = Form()):
    form = cclient.MultiPartForm()
    form.add_field('type', 'file_upload')
    form.add_field('_p', p)
    form.add_file('filedata', filedata.filename, fileHandle=filedata.file)
    return client.createFileNode(form)


@app.get("/download/{node_uid}")
def download_file(node_uid: str, request: Request):
    def iterfile(f):
        with open(f, mode="rb") as file_like:
            yield from file_like

    tmpfile,contenttype,disposition = client.downloadFile(node_uid)
    resp = StreamingResponse(iterfile(tmpfile), media_type=contenttype)
    resp.headers['Content-Disposition'] = disposition
    return resp


@app.get("/attachment/{attachment_uid}/{timestamp}")
async def get_attachment(attachment_uid: str, timestamp: str, request: Request):
    return client.fetchNodes(
        uid = attachment_uid, 
        field = cnode.PROP_LASTMOD, 
        op = 'gt', 
        val = timestamp, 
        depth = 0, 
        body = True)


@app.get("/test/checklogin")
async def do_testchecklogin():

    return {"check":"ok"}


"""
public class QueryOptionsClause
{
    public List<QueryOptionsClause>? and { get; set; } = null;
    public List<QueryOptionsClause>? or { get; set; } = null;
    public string? field { get; set; } = null;
    public string? op { get; set; } = null;
    public string? val { get; set; } = null;
}

public class QueryOptions
{
    public List<string>? rootIds { get; set; }
    public QueryOptionsClause? rootQuery { get; set; } //if present, then ignore rootIds, recurse and depth
    public string recurse { get; set; } = "out";
    public uint depth { get; set; } = 0;
    public QueryOptionsClause? filters { get; set; }
    public List<string>? select { get; set; }
}

# query (recurse outward from rootIds)
{
  "rootIds": ["0x2"], //can set this to [] and collablio will replace it with the root node ID
  "rootQuery": null,
  "recurse": "out",
  "depth": 20,
  "filters": {
    "field": "m",
    "op": "gt",
    "val": "0"
  },
  "select":["uid","ty","l","d","c"]
}

# query (dgraph rootQuery)
{
  "rootIds": null,
  "rootQuery": {
    "field": "m",
    "op": "gt",
    "val": "0"
  },
  "recurse": null,
  "filters": {
    "field": "m",
    "op": "gt",
    "val": "0"
  },
  "select":["uid","ty","l","d","c"]
}

# upsert
[
    {
        "uid": "",
        "ty": "Annotation",
        "l": "unique-label",
        "d": "Human Readable Label",
        "c": "{customdata:123}",
        "in": [
            {
                "uid": "0x2"
            }
        ],
        "out": [],
        "lnk": []
    }
]

# move
{
  "nodes": [
    "0x13890"
  ],
  "parents": [
    "0x6"
  ],
  "children": [],
  "newparent": "0x2fb9"
}
"""