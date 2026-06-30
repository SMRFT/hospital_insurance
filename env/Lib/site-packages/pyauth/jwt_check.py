import jwt
import os
import base64
import time
import jwt
import re
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from .jwt_crypter import supported, decrypt


SECURITY_DISABLED_FLAG =  'SECURITY_DISABLED'
PUBLIC_KEY_NAME =  'GLOBAL_PUBLIC_KEY'
ISSUER_KEY =  'iss'
ISSUER_VALUE =  'https://lab.shinova.in/'
ISSUED_AT_KEY = "iat"
EXPIRES_AT_KEY = "exp"
ALLOWED_DATA_KEY = 'allowed-data'
ALLOWED_ACTIONS_KEY = 'allowed-actions'
ALLOWED_OUTLETS_KEY = 'allowed-outlets'
CRYPT_KEY = "crypt"
CRYPT_ALGORITHM_VALUE = "bit_map"

AUD_KEY = "aud"
NAME_KEY= "name"
EMAIL_KEY= "email"
PAGE_KEY= "page"
ACTION_KEY= "action"
PERMISSION_KEY= "permission"
#ROLE_KEY= "role_name"
HOSPITAL_CODE_KEY =  'hospital_code'

AUTHZ_MODEL = 'IMPLIED'
AUTHZ_MODEL_IMPLIED = 'IMPLIED'

__sec_dsiabled_flag = os.environ.get(SECURITY_DISABLED_FLAG, "false").lower()
SECURITY_DISABLED = (__sec_dsiabled_flag == 'true' or __sec_dsiabled_flag == 'yes' or __sec_dsiabled_flag == 'y')

if not SECURITY_DISABLED:
   _pubk_B64 = os.environ[PUBLIC_KEY_NAME]
   if not _pubk_B64:
      raise ValueError(f'Private key ({PUBLIC_KEY_NAME}) not set')

   _pubk = base64.b64decode(_pubk_B64) 

   PUBLIC_KEY = serialization.load_pem_public_key(
      _pubk, backend=default_backend())

def __load_module_from_file(file_path):
   module_namespace = {}
   with open(file_path, 'r') as file:
      exec(file.read(), module_namespace)
   return module_namespace

def __find_file_by_name(file_name, search_path):
    for root, dirs, files in os.walk(search_path):
        if file_name in files:
            return os.path.join(root, file_name)
    return None

file_path = __find_file_by_name("permissions_map.py", ".")
print(f"Loading permissions from: {file_path}")
__permissions = __load_module_from_file(file_path)

def isSecurityDisabled():
   return SECURITY_DISABLED


def checkAccess(accessToken:str, 
                data:str, #branch_code
                page:str, 
                action:str, 
                outlet:str = '') -> dict:

   vJson = __checkJwt(accessToken)
   
   __checkAccessForData(vJson, data)
   if outlet:
      __checkAccessForOutlet(vJson, outlet)

   __checkAccessForPageAction(vJson, page, action)
   return vJson

def checkAccessForData(accessToken:str, 
                data:str, outlet:str = '') -> dict:

   vJson = __checkJwt(accessToken)
   __checkAccessForData(vJson, data)
   if outlet:
      __checkAccessForOutlet(vJson, outlet)
   return vJson

def checkAccessForOutlet(accessToken:str, 
                outlet:str) -> dict:

   vJson = __checkJwt(accessToken)
   __checkAccessForOutlet(vJson, outlet)
   return vJson


def checkAccessForPageAction(accessToken:str, 
                page:str, 
                action:str) -> dict:

   vJson = __checkJwt(accessToken)
   __checkAccessForPageAction(vJson, page, action)
   return vJson

def __checkJwt(accessToken:str):

   ct = round(time.time())
   unverified = jwt.decode(accessToken, options={"verify_signature": False})

   if unverified[ISSUER_KEY] != ISSUER_VALUE :
      raise ValueError(f'Invalid access token [Token not from trusted source]')
   elif unverified[ISSUED_AT_KEY] > ct :
      raise ValueError(f'Invalid access token [Token is not yet valid]')
   elif unverified[EXPIRES_AT_KEY] < ct :
      raise ValueError(f'Invalid access token [Token expired]')

   tokenAud = unverified[AUD_KEY]

   hospitalCode = unverified.get(HOSPITAL_CODE_KEY, '')
   if not hospitalCode:
      raise ValueError(f'Invalid access token [Token does not have valid hospital code]')

   verified = jwt.decode(accessToken, key=_pubk, algorithms="RS256", audience=tokenAud)

   crypt = verified.get(CRYPT_KEY, "")
   if crypt:
      # split crypt value to get algorithm and value
      cryptParts = crypt.split(':')
      if len(cryptParts) == 4:
         env = cryptParts[0]
         cAlgo = cryptParts[1]
         permsVer  = cryptParts[2]
         permsHash = cryptParts[3]
         if cAlgo == CRYPT_ALGORITHM_VALUE:
            if supported(env, permsVer, permsHash): 
               verified[ALLOWED_ACTIONS_KEY] = decrypt(env, permsHash, verified[ALLOWED_ACTIONS_KEY])
   return verified

def __checkAccessForData(vJson:dict, 
                data:str) -> bool:

   # Data validation
   if data not in vJson[ALLOWED_DATA_KEY]:
      raise ValueError(f'Access denied [Not entitled to access requested data {data}]', data)
   return True

def __checkAccessForOutlet(vJson:dict, 
                outlet:str) -> bool:

   if not vJson[ALLOWED_OUTLETS_KEY]:
      raise ValueError(f'Access denied [Not entitled to access any outlet]', outlet)
   # Outlet validation
   if outlet not in vJson[ALLOWED_OUTLETS_KEY]:
      raise ValueError(f'Access denied [Not entitled to access requested outlet {outlet}]', outlet)
   return True


def __checkAccessForPageAction(vJson:dict, 
                page:str, 
                action:str) -> bool:

   pageId = __permissions.get("PAGE_MAPPING").get(page, "")
   if not pageId:
      for p in __permissions.get("PAGE_MAPPING"):
         if re.fullmatch(p, page):
            pageId = __permissions.get("PAGE_MAPPING").get(p, "")
            break
   if not pageId:
      raise ValueError(f'Access denied [Invalid page]: {pageId}')

   if pageId in __permissions.get("PAGE_ACTION_MAPPING") and action in __permissions.get("PAGE_ACTION_MAPPING").get(pageId):
      actionId = __permissions.get("PAGE_ACTION_MAPPING").get(pageId).get(action)
   else:
      actionId = __permissions.get("GEN_ACTION_MAPPING").get(action)

   if not actionId:
      raise ValueError(f'Access denied [Invalid action]: {actionId}')

   permissionId = pageId + '-' + actionId    

   if permissionId not in vJson[ALLOWED_ACTIONS_KEY]:
      if AUTHZ_MODEL == AUTHZ_MODEL_IMPLIED:
         for k in vJson[ALLOWED_ACTIONS_KEY]:
            if k.startswith(permissionId):
               break
         else:
               raise ValueError(f'Access denied [Not allowed to perform {action} on {page}]',action, page)
      else:      
         raise ValueError(f'Access denied [Not allowed to perform {action} on {page}]',action, page)
   # Allowed access
   vJson[PAGE_KEY] = pageId
   vJson[ACTION_KEY] = actionId
   vJson[PERMISSION_KEY] = permissionId
   return True

def validateRoleAccess(allowedActionCodes, pageId, actionId) -> bool:

   if not pageId:
      print(f'pageId is blank. Not allowed\n')
      return False

   if not actionId:
      print(f'actionId is blank. Not allowed\n')
      return False

   permissionId = pageId + '-' + actionId

   if permissionId not in allowedActionCodes:
      if AUTHZ_MODEL == AUTHZ_MODEL_IMPLIED:
         for k in allowedActionCodes:
            if k.startswith(permissionId):
               break
         else:
            print(f'Does not have implied access. Not allowed\n')
      else:
         print(f'Does not have access. Not allowed\n')

   return True

def validateDataAccess(allowedBranchCodes, branchCode) -> bool:

   if not branchCode:
      print(f'branchCode is blank. Not allowed\n')
      return False

   return branchCode in allowedBranchCodes
