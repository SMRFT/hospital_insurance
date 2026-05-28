import base64
import os
import requests
import hashlib

PERMS_BASE_URL = "https://raw.githubusercontent.com/SMRFT/Permissions_master/refs/heads/"
PERMS_BASE_PATH = "/auth/permissions_master"
PERMS_EXT = ".lst"

osEnv = os.getenv('ENV_CLASSIFICATION')
if osEnv != 'prod':
    osEnv = 'test'

# initialize map
master_permissions = {}
master_versions = set()

def __load_permissions(env: str, permVer=""):
    global master_permissions
    master_versions.add(permVer)

    fullUrl = f"{PERMS_BASE_URL}{env}{PERMS_BASE_PATH}_{permVer}{PERMS_EXT}" if permVer else f"{PERMS_BASE_URL}{env}{PERMS_BASE_PATH}{PERMS_EXT}"

    response = requests.get(fullUrl)
    if response.status_code != 200:
        raise ValueError(f'Failed to retrieve permissions file: {fullUrl}')

    perms = [line.strip() for line in response.text.splitlines()]
    perms_hash = hashlib.sha256(''.join(perms).encode()).hexdigest()

    perms_key = f"{env}_{perms_hash}"
    master_permissions[perms_key] = perms

def decrypt(env: str, permsHash: str, base64BitMap: str) -> list[str]:
    global master_permissions
    # decode base64 to bytes
    bitMap = base64.b64decode(base64BitMap.encode('utf-8'))
    actions = []

    perms_key = f"{env}_{permsHash}"
    permissions = master_permissions.get(perms_key)
    
    # reverse the bitmap to get actions
    for i in range(len(bitMap)*8):
        bytePosition = i // 8
        bitPosition = i % 8
        if bitMap[bytePosition] & (1 << (7 - bitPosition)):
            actions.append(permissions[i])

    return actions

def supported(env: str, permsVer: str, permsHash: str) -> bool:
    global master_permissions
    global master_versions
    global osEnv

    if osEnv != env:
        return False

    perms_key = f"{env}_{permsHash}"
    if perms_key in master_permissions:
        return True
    elif permsVer in master_versions:
        raise ValueError(f'Permissions file not found: {permsVer}')
    else:
        __load_permissions(env, permsVer)
        return perms_key in master_permissions
