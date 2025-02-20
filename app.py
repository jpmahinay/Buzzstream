from flask import Flask, render_template, request, jsonify
from datetime import datetime
import requests
import time
import uuid
import urllib.parse
import re
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# Relationship stage mapping (remains unchanged)
RELATIONSHIP_STAGE_MAPPING = {
    "42990175": "Attempting To Reach",
    "42990176": "Replied",
    "42990179": "Successful Placement",
    "182219643": "Unsuccessful - No Reply",
    "243133324": "Manual Sendouts - 1st email",
    "243133325": "Manual Sendouts - 2nd email",
    "243133326": "Manual Sendouts - 3rd email",
    "43017713": "Client Link Sent",
    "62427773": "Client Link Sent - 1st Follow-Up",
    "62427774": "Client Link Sent - 2nd Follow-Up",
    "62427775": "Client Link Sent - 3rd Follow-Up",
    "78207176": "Client link sent - 4th follow-up",
    "43017709": "Contact Form Attempt",
    "43017710": "Contact Form Attempt (2nd)",
    "43017711": "Contact Form Attempt (3rd)",
    "74855452": "Contact Form Attempt (4th)",
    "43703894": "Existing Link - Do Not Outreach",
    "75356660": "Forwarded",
    "42990174": "Lead Approved",
    "42990178": "Lead Inactive",
    "43158513": "Lost (Email Blocked / Do Not Contact)",
    "43017715": "Lost (EMail Bounced)",
    "46305485": "Lost (No Response)",
    "43017716": "Lost (WM Declined)",
    "43018748": "Manual Follow-Up",
    "43018749": "Manual Follow-Up (2nd)",
    "110283369": "Manual Follow-Up (3rd)",
    "110283370": "Manual Follow-Up (4th)",
    "69037241": "Nego Zombie (15+ days)",
    "67336029": "Nego Zombie (31+ days)",
    "69037242": "Nego Zombie (60+ days)",
    "88539391": "Not Sent (Possible Issues)",
    "42990173": "Not Started",
    "43018746": "Opened",
    "43017714": "Out of Office",
    "88297641": "Positive Reply Received",
    "43537578": "Recycled - Not Started",
    "52881604": "Rejected by Approver",
    "62380086": "Rejected by Contact Hunter",
    "42990177": "Rejected by LinkDev",
    "60711551": "Sending Failed - See Error(s)",
    "82148650": "WM Promised to Publish Link/Article",
    "89961311": "--- # PHASE 5 ONLY # ---",
    "62610487": "Client Link Sent (Content)",
    "62610489": "Client Sent - Follow-Up (Max Price Offer)",
    "62610488": "Client Sent - Follow-Up (Price Increased)",
    "62610492": "Manual Follow-Up (Max Price Offer)",
    "62610491": "Manual Follow-Up (Price Increased)",
    "43017712": "Negotiating",
    "53135910": "Pending Approval",
    "62610490": "Topic Sent - Follow-up",
    "62610486": "Topics Sent",
    "90480418": "--- # OTHERS # ---",
    "43017707": "Attempting To Reach (2nd)",
    "43017708": "Attempting To Reach (3rd)",
    "74567975": "Attempting to Reach (4th)",
    "43018747": "Client Link Clicked",
    "44736674": "Client Webmail 1st Attempt",
    "44736675": "Client Webmail 2nd Attempt",
    "44736676": "Client Webmail 3rd Attempt",
    "45365975": "Delayed",
    "59250074": "Draft Forwarded to Client Inbox",
    "101549404": "Future-dated Lead",
    "44654869": "Live Link (Won)",
    "58386717": "Not Started - 2nd Priority",
    "58386716": "Not Started - High Priority",
    "43302550": "Pending (Export / Sendouts)",
    "45364088": "Personalizing",
    "43537589": "Quick Win (New)",
    "46477768": "Re-assessment Needed",
    "108180157": "STOPLIST (Client)",
    "171075184": "Dropped / Deactivated",
    "182219641": "Scheduled",
    "182219642": "Paused",
    "182219644": "Bounce",
    "182219645": "Send Failure",
    "182219643": "Unsuccessful - No Reply"
}

# Function to generate OAuth header (remains unchanged)
def get_auth_header(consumer_key, consumer_secret):
    timestamp = int(time.time())
    nonce = str(uuid.uuid4())
    signature = urllib.parse.quote(consumer_secret) + "&"
    return (f'OAuth '
            f'oauth_consumer_key="{consumer_key}",'
            f'oauth_nonce="{nonce}", '
            f'oauth_signature="{signature}",'
            f'oauth_signature_method="PLAINTEXT",'
            f'oauth_timestamp="{timestamp}"')

# Fetch projects from BuzzStream API (remains unchanged)
def fetch_projects(consumer_key, consumer_secret):
    api_url = 'https://api.buzzstream.com/v1/projects'
    params = {
        'active': 'true',
        'expand': 'true',
        'max_results': 200
    }
    headers = {
        'Authorization': get_auth_header(consumer_key, consumer_secret)
    }
    phases = {'Phase 1', 'Phase 3', 'Phase 5', 'Phase 8'}
    try:
        response = requests.get(api_url, headers=headers, params=params)
        response.raise_for_status()
        projects = response.json().get('list', [])
       # print(f"Raw API response: {response.json()}")  # Keep for debugging

        filtered_projects = [
            project for project in projects
            if project.get('name') and
               any(project['name'].startswith(phase) for phase in phases) # Corrected filtering
        ]

        result = []
        for p in filtered_projects:
            if 'id' in p and 'name' in p:  # Keep the 'name' check
                result.append({
                    'originalName': p['name'],
                    'cleanedName': clean_project_name(p['name']),
                    'id': p['id']
                })
            else:
                print(f"Skipping project due to missing 'id' or 'name': {p}")  # Keep for debugging
        return sorted(
            result,
            key=lambda x: list(phases).index(x['cleanedName'].split(' - ')[0])
        )

    except requests.RequestException as e:
        print(f'Error fetching projects: {e}')
        return []
    except Exception as e:
        print(f'An unexpected error: {e}')
        return []

# Clean project name (remains unchanged)
def clean_project_name(project_name):
    import re
    phase_match = re.search(r'Phase \d+', project_name, re.IGNORECASE)
    domain_match = re.search(r'([A-Za-z0-9-]+\.(?:com|co\.uk|net|org))', project_name, re.IGNORECASE)

    if phase_match and domain_match:
        return f"{phase_match.group()} - {domain_match.group(1)}"
    return project_name

# Format date (remains unchanged)
def format_date(date_string):
    if not date_string:
      return ""
    try:
        date = datetime.fromtimestamp(int(date_string) / 1000)
        return date.strftime('%m-%d-%Y') # CORRECTED DATE FORMAT
    except (ValueError, TypeError):
        return ""

# Find relationship stage URL (remains unchanged)
def find_relationship_stage_url(website):
    if not website.get('stateForProject', {}).get('relationshipStage'):
        return ''
    match = re.search(r'/(\d+)$', website['stateForProject']['relationshipStage'])
    return RELATIONSHIP_STAGE_MAPPING.get(match.group(1), '') if match else ''

# Fetch website details (remains unchanged)
def fetch_website_details(consumer_key, consumer_secret, website_url, project_id, start_date, end_date):
    if not website_url:
        print("Error: No website URL provided.")
        return {}

    headers = {
        'Authorization': get_auth_header(consumer_key, consumer_secret)
    }
    try:
        details_url = f"{website_url}?project_state_added_after={start_date}&project_state_added_before={end_date}&expand=true&show_project_state={project_id}"
        response = requests.get(details_url, headers=headers)
        response.raise_for_status()
        website = response.json()
        return website
    except requests.RequestException as e:
        print(f'Error fetching website details: {e}')
        return {}

# Fetch chronicle data
def fetch_chronicle(consumer_key, consumer_secret, chronicle_url):
    if not chronicle_url:
        print("Error: No chronicle URL provided.")
        return ""

    headers = {
        'Authorization': get_auth_header(consumer_key, consumer_secret)
    }
    try:
        response = requests.get(chronicle_url, headers=headers)
        response.raise_for_status()
        chronicle = response.json()
        return chronicle.get('body', '')
    except requests.RequestException as e:
        print(f'Error fetching chronicle: {e}')
        return ""

# Fetch domain rating (remains unchanged)
def fetch_domain_rating(consumer_key, consumer_secret, contact_id):
    if not contact_id:
        print("Error: No contact ID provided.")
        return ""

    headers = {
        'Authorization': get_auth_header(consumer_key, consumer_secret)
    }
    try:
        metrics_url = f'https://api.buzzstream.com/v1/metrics/contact?id={contact_id}'
        response = requests.get(metrics_url, headers=headers)
        response.raise_for_status()
        data = response.json()

        if data and data.get(contact_id) and data[contact_id].get('domain-rating'):
            return data[contact_id]['domain-rating'].get('value', '')
        return ""
    except requests.RequestException as e:
        print(f'Error fetching domain rating: {e}')
        return ""

# Fetch links (remains unchanged)
def fetch_links(consumer_key, consumer_secret, website_id, project_id):
    headers = {
        'Authorization': get_auth_header(consumer_key, consumer_secret)
    }
    try:
        links_url = f'https://api.buzzstream.com/v1/links?website={website_id}&expand=true&project={project_id}'
        response = requests.get(links_url, headers=headers)
        response.raise_for_status()
        links = response.json().get('list', [])
        return links[0] if links else {}
    except requests.RequestException as e:
        print(f'Error fetching links for website {website_id}: {e}')
        return {}




def fetch_history(consumer_key, consumer_secret, website_id, project_id):
    headers = {
        'Authorization': get_auth_header(consumer_key, consumer_secret)
    }
    history_url = f'https://api.buzzstream.com/v1/history?contact={website_id}&expand=true&type=email&project={project_id}'
    try:
        response = requests.get(history_url, headers=headers)
        response.raise_for_status()
        return response.json().get('list', [])
    except requests.RequestException as e:
        print(f"Error fetching history for website {website_id}: {e}")
        return []

def process_website(consumer_key, consumer_secret, website, project_id, start_date, end_date):
    if not website or not isinstance(website, dict):
        print(f"Warning: Invalid website received: {website}")
        return None

    website_id = website.get('id')
    if not website_id:
        print("Warning: No website ID found.")
        return None

    with ThreadPoolExecutor(max_workers=30) as executor:
        future_website_details = executor.submit(fetch_website_details, consumer_key, consumer_secret, website.get('uri') or website.get('url'), project_id, start_date, end_date)
        future_links = executor.submit(fetch_links, consumer_key, consumer_secret, website_id, project_id)

        website_details = future_website_details.result()
        links = future_links.result()

        if not website_details:
            print("Warning: Could not fetch website details, skipping.")
            return None

    chronicle_data = fetch_chronicle(consumer_key, consumer_secret, website_details.get('mostRecentNonCommunicationChronicle'))
    contact_id = str(website.get('stateForProject', {}).get('contact', '')).split("/").pop() if website.get('stateForProject') else ""
    domain_rating = fetch_domain_rating(consumer_key, consumer_secret, contact_id) if contact_id else ""

    associated_people_id = ''
    if isinstance(website.get("associatedPeople", ()), list) and len(website.get("associatedPeople", [])) > 0:
        associated_people_id = website.get("associatedPeople", [])[0].get('id', '')

    # Process history entries
    history = fetch_history(consumer_key, consumer_secret, website_id, project_id)
    
    # Sort history by chronicleDate ascending and filter valid entries
    sorted_history = sorted(
        [h for h in history if 
         h.get('chronicleDate') and 
         start_date <= h['chronicleDate'] <= end_date],
        key=lambda x: x.get('chronicleDate', 0)
    )
    # Process up to 4 history entries
    history_entries = []
    for h in sorted_history:
        entry = {
            'date': format_date(h.get('chronicleDate')),
            'direction': h.get('emailDirection', ''),
            'hisID': h.get('id', '')
        }
        history_entries.append(entry)

    # Pad with empty entries if needed
    while len(history_entries) < 4:
        history_entries.append({'date': '', 'direction': '', 'hisID': ''})
    history_entries = history_entries[:4]

    formatted_website = {
        'id': website.get('id', ''),
        'name': website.get("name", ""),
        'primaryDomain': website.get("primaryDomain", ""),
        'associatedPeopleId': associated_people_id,
        'chronicle': chronicle_data,
        'projectName': website.get("stateForProject", {}).get("project", {}).get("name", ""),
        'projectAddedDate': format_date(website_details.get("stateForProject", {}).get("createdDate", "")),
        'relationshipStage': find_relationship_stage_url(website_details),
        'domainRating': domain_rating,
        'sendoutType': website.get("stateForProject", {}).get("fieldValues", {}).get(".Sendout Type", ""),
        'activeProjects': website.get("stateForProject", {}).get("fieldValues", {}).get("Active Projects", ""),
        'agingStatus': website.get("stateForProject", {}).get("fieldValues", {}).get("Aging Status", ""),
        'contactHunter': website.get("stateForProject", {}).get("fieldValues", {}).get("Contact Hunter", ""),
        'leadSource': website.get("stateForProject", {}).get("fieldValues", {}).get("Lead Source (NEW)", ""),
        'linkDev': website.get("stateForProject", {}).get("fieldValues", {}).get("LinkDev", ""),
        'sequenceStage': website.get("stateForProject", {}).get("fieldValues", {}).get("Sequence Stage", ""),
        'template': website.get("stateForProject", {}).get("fieldValues", {}).get("Template", ""),
        'wmDeclineReason': website.get("stateForProject", {}).get("fieldValues", {}).get("WM Decline Reason", ""),
        'wmFeedback': website.get("stateForProject", {}).get("fieldValues", {}).get("WM Feedback (WM Decline)", ""),
        'linkId': links.get("id", '') if links else '',
        'linkingFrom': links.get('linkingFrom', '') if links else '',
        'linkingFromTLD': links.get('linkingFromTLD', '') if links else '',
        'linkCreatedDate': format_date(links.get('createdDate', '')) if links else '',
        'lastCommunicationDate': format_date(website_details.get("lastCommunicationDate", "")),
        # History columns
        'chronicleDate1st': history_entries[0]['date'],
        'emailDirection1st': history_entries[0]['direction'],
        'hisID1st': history_entries[0]['hisID'],
        'chronicleDate2nd': history_entries[1]['date'],
        'emailDirection2nd': history_entries[1]['direction'],
        'hisID2nd': history_entries[1]['hisID'],
        'chronicleDate3rd': history_entries[2]['date'],
        'emailDirection3rd': history_entries[2]['direction'],
        'hisID3rd': history_entries[2]['hisID'],
        'chronicleDate4th': history_entries[3]['date'],
        'emailDirection4th': history_entries[3]['direction'],
        'hisID4th': history_entries[3]['hisID'],
        
        'websiteNote': chronicle_data,
        'websiteProject': website.get("stateForProject", {}).get("project", {}).get("name", ""),
        'websiteDateAddedToProject': format_date(website_details.get("stateForProject", {}).get("createdDate", "")),
        'websiteRelationshipStage': find_relationship_stage_url(website_details),
        'ahrefsDomainRating': domain_rating,
    }
    return formatted_website

# Fetch websites data (remains unchanged)
def fetch_websites_data(consumer_key, consumer_secret, project_id, start_date, end_date):
    api_url = f'https://api.buzzstream.com/v1/websites?project={project_id}&project_state_added_after={start_date}&project_state_added_before={end_date}'
    headers = {
        'Authorization': get_auth_header(consumer_key, consumer_secret)
    }
    all_websites = []
    offset = 0
    max_results = 200
    with ThreadPoolExecutor(max_workers=30) as executor:
        while True:
            paginated_url = f"{api_url}&max_results={max_results}&offset={offset}"
            try:
                response = requests.get(paginated_url, headers=headers)
                response.raise_for_status()
                data = response.json()
                website_urls = data.get("list", [])  # Now we expect a list of URLs
                if not website_urls:
                    break

                # Fetch details for each website URL concurrently
                futures = [
                    executor.submit(fetch_website_details, consumer_key, consumer_secret, url, project_id, start_date, end_date)
                    for url in website_urls
                ]
                website_details_list = [future.result() for future in futures]

                #Now same threadpool processes the websites
                futures_process = [
                      executor.submit(process_website, consumer_key, consumer_secret, website, project_id, start_date, end_date)
                      for website in website_details_list
                ]


                for future in futures_process:
                    result = future.result()
                    if result:  # Only process if we got details
                        all_websites.append(result)


                offset += max_results
            except requests.RequestException as e:
                print(f'Error fetching websites: {e}')
                return []

    return all_websites


# Flask routes (remains unchanged)
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/projects')
def get_projects():
    CONSUMER_KEY = 'dcf0884b-bb81-490a-8709-efab05170b1d'
    CONSUMER_SECRET = 'w7FFlxlbtctZUFtEyW7ePTVkXAUlDb3qLKAUVLUJgenq7dVt15Tcb9R-YqLn0Em8'
    projects = fetch_projects(CONSUMER_KEY, CONSUMER_SECRET)
    return jsonify(projects)

@app.route('/process', methods=['POST'])
def process_selection():
    data = request.json
    project_name = data.get('projectName')
    project_id = data.get('projectId')
  # Convert start date to beginning of the day (midnight)
    start_date = int(datetime.fromtimestamp(data.get('startDate') / 1000).replace(
        hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
    
    # Convert end date to end of the day (23:59:59)
    end_date = int(datetime.fromtimestamp(data.get('endDate') / 1000).replace(
        hour=23, minute=59, second=59, microsecond=999999).timestamp() * 1000)
    
    print(f"Project Name: {project_name}")
    print(f"Project ID: {project_id}")
    print(f"Start Date: {start_date}")
    print(f"End Date: {end_date}")

    # Retrieve keys securely (e.g., environment variables, config file)
    CONSUMER_KEY = 'dcf0884b-bb81-490a-8709-efab05170b1d'
    CONSUMER_SECRET = 'w7FFlxlbtctZUFtEyW7ePTVkXAUlDb3qLKAUVLUJgenq7dVt15Tcb9R-YqLn0Em8'

    websites = fetch_websites_data(CONSUMER_KEY, CONSUMER_SECRET, project_id, start_date, end_date)
    return jsonify({"status": "success", "websites": websites})

if __name__ == '__main__':
    app.run(debug=True)








