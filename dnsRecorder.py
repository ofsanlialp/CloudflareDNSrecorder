import requests
import json
import sys
import yaml
import traceback

# Cloudflare API base URL
CLOUDFLARE_API_BASE_URL = "https://api.cloudflare.com/client/v4"

def call_cloudflare_api(method: str, endpoint: str, api_key: str, email: str, json_data: dict = None) -> dict:
    """
    Makes a call to the Cloudflare API.

    Args:
        method: HTTP method (e.g., 'GET', 'PUT').
        endpoint: API endpoint path (e.g., "zones/ZONE_ID/dns_records").
        api_key: Cloudflare API key.
        email: Cloudflare email.
        json_data: Optional dictionary for the JSON body of requests.

    Returns:
        A dictionary representing the JSON response from the API.
        Exits script on error.
    """
    url = f"{CLOUDFLARE_API_BASE_URL}/{endpoint}"
    headers = {
        'X-Auth-Key': api_key,
        'X-Auth-Email': email,
        'Content-Type': 'application/json'
    }

    try:
        response = requests.request(method, url, headers=headers, json=json_data, timeout=10)

        # Check for non-successful status codes
        if not (200 <= response.status_code < 300):
            error_details = response.text
            try:
                # Try to parse JSON for more detailed error, Cloudflare often returns JSON errors
                error_details = response.json()
            except requests.exceptions.JSONDecodeError:
                pass # Keep text if JSON decoding fails
            print(f"Error calling Cloudflare API ({method} {url}). Status: {response.status_code}, Details: {error_details}")
            sys.exit(1)

        # Attempt to parse the JSON response
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Network error calling Cloudflare API ({method} {url}): {e}")
        sys.exit(1)
    except requests.exceptions.JSONDecodeError as e:
        # This can happen if the response is successful (2xx) but not valid JSON
        print(f"Error decoding JSON response from Cloudflare API ({method} {url}): {e}. Response text: {response.text}")
        sys.exit(1)


try:
    with open('config.yaml') as f:
        try:
            config = yaml.load(f, Loader=yaml.FullLoader)
        except yaml.YAMLError as e:
            print(f"Error: Could not parse config.yaml. Please check its formatting. Details: {e}")
            sys.exit(1)
except FileNotFoundError:
    print("Error: config.yaml not found. Please ensure the file exists in the same directory as the script.")
    sys.exit(1)

essential_keys = ['api', 'email', 'zoneID', 'type', 'name', 'proxied']
for key in essential_keys:
    if key not in config:
        print(f"Error: Missing '{key}' key in config.yaml.")
        sys.exit(1)

try:
    IP_API = 'https://api.ipify.org?format=json'
    API_KEY = config['api']
    EMAIL = config['email']
    ZONE_ID = config['zoneID']
# recordID is optional and will be checked by the script logic later
# However, if it's present, it should be loaded. If not, it should default to None or an empty string.
RECORD_ID = config.get('recordID') # Use .get() for optional keys


if not RECORD_ID:  # if there is no record id entered then get it from api response
    print("RECORD_ID not set in config. Fetching available DNS records...")
    list_records_endpoint = f"zones/{ZONE_ID}/dns_records"
    # The initial error handling for the API call itself is now inside call_cloudflare_api
    data = call_cloudflare_api('GET', list_records_endpoint, API_KEY, EMAIL)

    # The following checks are specific to the list DNS records endpoint structure
    if not isinstance(data, dict) or 'result' not in data or not isinstance(data.get('result'), list):
        print(f"Error: Unexpected API response format when listing DNS records. 'result' key missing or not a list.")
        print(f"Received data: {data}")
        sys.exit(1)

    records = data.get('result', [])
    if not records:
        print("No DNS records found for the given Zone ID.")
        sys.exit(0)

    print("Found the following DNS records:")
    for record in records:
        try:
            record_name = record['name']
            record_id = record['id']
            print(f"  Record Name: {record_name}, ID: {record_id}")
        except KeyError:
            print(f"  Warning: Found a record with missing 'name' or 'id': {record}")

    print('\nPlease find the DNS record ID you would like to update and entry the value into the script')
    sys.exit(0)

try:
    resp = requests.get(IP_API)
    resp.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
except requests.exceptions.RequestException as e:
    print(f"Error fetching IP address from {IP_API}: {e}")
    sys.exit(1)

try:
    ip_data = resp.json()
except (json.JSONDecodeError, requests.exceptions.JSONDecodeError):
    print(f"Error: Invalid JSON response from {IP_API}")
    sys.exit(1)

if 'ip' not in ip_data:
    print(f"Error: 'ip' key not found in response from {IP_API}. Response: {ip_data}")
    sys.exit(1)

ip = ip_data['ip']

    # If RECORD_ID was initially missing, user needs to set it after listing.
    # The script exits after listing, so if we are here, RECORD_ID must be set.
    if not RECORD_ID:
        print("Error: RECORD_ID is still not set. Please update config.yaml with the correct ID from the list above.")
        sys.exit(1)

    print(f"Attempting to update DNS record ID: {RECORD_ID} for {config['name']} to IP: {ip}")
    update_record_endpoint = f"zones/{ZONE_ID}/dns_records/{RECORD_ID}"
    payload = {
        'type': config['type'],
        'name': config['name'],
        'content': ip,
        'proxied': config['proxied']
    }

    update_response = call_cloudflare_api('PUT', update_record_endpoint, API_KEY, EMAIL, json_data=payload)

    # The call_cloudflare_api function exits on non-2xx status,
    # so if we reach here, the API call was successful (status 2xx) and response was valid JSON.
    # Cloudflare PUT response for DNS update usually includes the updated record details.
    # We can check 'success' key if API guarantees it, or just assume success if no exit.
    if update_response and update_response.get('success', False): # Common pattern in Cloudflare API
        print('Successfully updated DNS record of ===> {} to ===> {}'.format(config['name'], ip))
    elif update_response: # If success key is not there but we got a 2xx response with valid JSON
        print('DNS record update API call successful for ===> {} to ===> {}. Response: {}'.format(config['name'], ip, update_response))
    else:
        # This case should ideally be caught by call_cloudflare_api if response parsing failed
        # or if it returned None (which it shouldn't with sys.exit in it).
        print('DNS record update for ===> {} to ===> {} seems to have issues, but no direct error reported.'.format(config['name'], ip))
        print("This indicates an issue with the script's response handling from call_cloudflare_api.")

except Exception as e:
    print(f"An unexpected error occurred: {type(e).__name__} - {e}")
    print("Traceback:")
    traceback.print_exc()
    sys.exit(1)
