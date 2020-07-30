import requests
import json
import sys
import yaml

with open('config.yaml') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)


IP_API = 'https://api.ipify.org?format=json'
API_KEY = config['api']
EMAIL = config['email']
ZONE_ID = config['zoneID']
RECORD_ID = config['recordID']


if not RECORD_ID:  # if there is no record id entered then get it from api response
    resp = requests.get(
        'https://api.cloudflare.com/client/v4/zones/{}/dns_records'.format(
            ZONE_ID),
        headers={
            'X-Auth-Key': API_KEY,
            'X-Auth-Email': EMAIL
        })
    print(json.dumps(resp.json(), indent=4, sort_keys=True))
    print('Please find the DNS record ID you would like to update and entry the value into the script')
    sys.exit(0)

resp = requests.get(IP_API)
ip = resp.json()['ip']


resp = requests.put(
    'https://api.cloudflare.com/client/v4/zones/{}/dns_records/{}'.format(
        ZONE_ID, RECORD_ID),
    json={
        'type': config['type'],  # record type
        # enter subdomain/main domain address you want to edit
        'name': config['name'],
        'content': ip,  # your public IP
        'proxied': config['proxied']
    },
    headers={
        'X-Auth-Key': API_KEY,
        'X-Auth-Email': EMAIL
    })
assert resp.status_code == 200

print('Updated DNS record of ===> {} to ===> {}'.format(config['name'], ip))
