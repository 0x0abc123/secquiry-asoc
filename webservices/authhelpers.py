import appconfig
import logger
import collablio.client as cclient
import secretstore
import jwt
import time
import urllib.request
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

pubkey_cache = {'oidc_aws':{}}
client = cclient.Client()
sstore = secretstore.GetStore()

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
    #{'name':jwtclaims['unique_name'],'tenant':jwtclaims['tid'],'exp':jwtclaims['exp']}
    issuer = appconfig.getValue("oidc_iss")
    if issuer != None and jwtclaims['iss'] == issuer:
        if int(jwtclaims['exp']) > int(time.time()):
            password = sstore.get('sso_auth_key')
            username = getUserFromJWTClaims(jwtclaims)
            authtoken = client.LoginAndGetToken(username, password)
            return authtoken
        else:
            logger.logEvent(f'authhelper: expired token')
    else:
        logger.logEvent(f'authhelper: fail to match issuer {issuer} to JWT claims issuer: {jwtclaims["iss"]}')

    return None