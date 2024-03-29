import appconfig
import logger
import collablio.client as cclient
import collablio.node as cnode
import cryptohelpers
import base64
import jwt
import json
import os
import time
import urllib.request
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI, Header, Depends, HTTPException, UploadFile, Form, Request, Response, status

PASSWD_FIELD = 'pass'
SSO_FIELD = 'sso'
AESGCMSECRETS_FIELD = 'aessecrets'
ADMIN_FIELD = 'isadmin'

JWT_ALG = "HS256"

pubkey_cache = {'oidc_aws':{}}
client = cclient.client 
loggedin_users = {}

def random_secret():
    randompassvals = os.urandom(32)
    passcharset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890!@#$%^&*()-=_+:;{}[]|,./?><~"
    passchars = len(passcharset)
    randompass = ''
    for i in randompassvals:
        randompass += passcharset[i % passchars]
    return randompass

JWT_SECRET_KEY = random_secret()

def get_pubkey(ssotype, kid):
    global pubkey_cache
    cache = pubkey_cache[ssotype]
    if kid in cache:
        return cache[kid]
    pubkeyserverURL = "http://127.0.0.1"
    urlFromConfig = appconfig.getValue("sso_pubkey_url")
    if urlFromConfig:
        pubkeyserverURL = urlFromConfig

    # if the EC2 that is running webservices is in a private subnet without an IGW or NAT, then we will need a proxy located in a public subnet
    proxyserverURL = appconfig.getValue("proxy")
    if proxyserverURL:
        proxyserverURL = proxyserverURL.replace('http://','')

    if ssotype == 'oidc_aws':
        req = urllib.request.Request(f'{pubkeyserverURL}/{kid}')
        if proxyserverURL:
            req.set_proxy(proxyserverURL,'http')
        res_bytes = urllib.request.urlopen(req).read()
        pk = serialization.load_pem_public_key(res_bytes, backend=default_backend())
        logger.logEvent(f'Authhelpers get_pubkey loaded PK: {pubkeyserverURL}/{kid}')
    else:
        logger.logEvent(f'unknown SSO type: {ssotype}')
        return None

    cache[kid] = pk
    return pk

def getUserFromJWTClaims(claims):
    if 'unique_name' in claims:
        return claims['unique_name']
    if 'upn' in claims:
        return claims['upn']
    if 'email' in claims:
        return claims['email']
    return None

def login_oidc_aws(reqdata):
    oidc_jwt = reqdata.headers.get('x-amzn-oidc-data')
    jwthdr = jwt.get_unverified_header(oidc_jwt)
    kid = jwthdr['kid']
    public_key = get_pubkey('oidc_aws',kid)
    jwtclaims = jwt.decode(oidc_jwt, public_key, algorithms=jwthdr["alg"])
    issuer = appconfig.getValue("oidc_iss")
    if issuer != None and jwtclaims['iss'] == issuer:
        if int(jwtclaims['exp']) > int(time.time()):
            authtoken = login_default({"username":getUserFromJWTClaims(jwtclaims)},True)
            return authtoken
        else:
            logger.logEvent(f'authhelper: expired token')
    else:
        logger.logEvent(f'authhelper: fail to match issuer {issuer} to JWT claims issuer: {jwtclaims["iss"]}')

    return None

def hash_password(password_str):
    salt = os.urandom(16)
    saltstr = base64.urlsafe_b64encode(salt).decode('utf-8')
    return f'{saltstr}${cryptohelpers.deriveKey(password_str,saltstr).decode("utf-8")}'

def verify_password(plaintxtpswd, salt_and_derivedpasswd):
    tmps = salt_and_derivedpasswd.split('$')
    ssalt = tmps[0]
    spass = tmps[1]
    expectedkey = cryptohelpers.deriveKey(plaintxtpswd,ssalt).decode("utf-8")
    return expectedkey == spass

#TODO: check expiry time on JWT
def verify_jwt_get_uid(jwtbearertoken):
    payload = jwt.decode(jwtbearertoken, JWT_SECRET_KEY, algorithms=[JWT_ALG])
    return payload.get(cnode.PROP_UID)

def get_usrdata_if_loggedin(jwtbearertoken):
    uid = verify_jwt_get_uid(jwtbearertoken)
    if uid:
        usrdata = loggedin_users.get(uid)
        if usrdata is not None:
            return usrdata
        else:
            raise Exception("User is not logged in")        
    raise Exception("JWT Payload missing UID")

#TODO: set expiry time on JWT
def login_default(logindata, ssologin=False):
    global loggedin_users
    jsonResponse = client.fetchNodes(field = cnode.PROP_LABEL, op = 'eq', val = logindata['username'], ntype = cnode.TYPE_USER)
    if 'nodes' in jsonResponse and len(jsonResponse['nodes']) == 1:
        usernodeReturned = jsonResponse['nodes'][0]
        usrdata_json = usernodeReturned[cnode.PROP_CUSTOM]
        usrdata = json.loads(usrdata_json)
        if (ssologin and usrdata.get(SSO_FIELD)) or verify_password(logindata['password'], usrdata[PASSWD_FIELD]):            
            if PASSWD_FIELD in usrdata:
                del usrdata[PASSWD_FIELD]
            user_uid = usernodeReturned[cnode.PROP_UID]
            usrdata['uid'] = user_uid
            usrdata[AESGCMSECRETS_FIELD] = cryptohelpers.generateAESGCMSecrets()
            loggedin_users[user_uid] = usrdata
            return create_jwt(logindata['username'], user_uid)

    return None

def create_jwt(sub, for_uid):
    payload_data = {
        "sub": sub,
        cnode.PROP_UID: for_uid
    }
    token = jwt.encode(
        payload=payload_data,
        key=JWT_SECRET_KEY,
        algorithm=JWT_ALG
    )
    if type(token) is bytes:
        return token.decode('utf-8')
    return token


def test_create_user(userdata):
    newusrname = userdata.get("username")
    newusrpswd = userdata.get("password")
    newusrsso = userdata.get("sso")
    if not newusrpswd and not newusrname:
        return None
    newusernode = cnode.Node(cnode.TYPE_USER)
    newusernode.Label = newusrname
    newusernode.CustomData = json.dumps({PASSWD_FIELD:hash_password(newusrpswd), SSO_FIELD:newusrsso})
    nodesToUpsert = [newusernode]
    return client.upsertNodes(nodesToUpsert)

def returnStatus(statuscode):
    lookup = {
        "400": status.HTTP_400_BAD_REQUEST,
        "401": status.HTTP_401_UNAUTHORIZED,
        "403": status.HTTP_403_FORBIDDEN,
        "404": status.HTTP_404_NOT_FOUND
    }
    response = Response()
    response.status_code = lookup[statuscode]
    return response

class AuthMiddleware:

    def __init__(self, anonymousRoutePrefixes = [], otherConditions = None):
        self.anonymous_routes = anonymousRoutePrefixes
        self.other_conditions = otherConditions

    """
    you can use request.state.your_custom_param  to pass data on to the route handlers from the middleware
    https://stackoverflow.com/questions/64602770/how-can-i-set-attribute-to-request-object-in-fastapi-from-middleware

    - this is a middleware function that is called for every request
    - it checks if the request is for an anonymous route
    - if it is not anonymous, it checks if the user is logged in and populates the user data in the request state
    - if validation fails, it will return an appropriate response object with the status code set
    - otherwise it will return None
    """
    async def getAuthorisation(self, request):
        p = request.url.path
        prefix = p.split("/")[1]
        if prefix not in self.anonymous_routes:
            auth_hdr = request.headers.get('Authorization')
            '''remove the leading "Bearer" string'''
            if auth_hdr:
                parts = auth_hdr.split(' ')
                auth_hdr = parts[1] if len(parts) > 1 else None
            else:
                auth_hdr = request.cookies.get('Authorization')
            if not auth_hdr:
                return returnStatus("400")

            try:
                usrdata = get_usrdata_if_loggedin(auth_hdr)
                if self.other_conditions:
                    conditionsMet = await self.other_conditions(request, usrdata)
                    if not conditionsMet:
                        return returnStatus("403")
                request.state.usrdata = usrdata
            except Exception as e:
                return returnStatus("401")
        return None