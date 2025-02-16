import os
import time
from datetime import datetime, timedelta
import requests
import json
import concurrent.futures
import logging
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
endpoint = "https://workspan-staging-2.qa.workspan.app/"
email = "user1@automp.com"
password = "restingpoint1"
MAX_WORKERS = 25

def get_auth_headers():
    """Get authentication headers"""
    login_url = endpoint + "_ah/api/network/v1/person/login"
    login_data = {
        "auth_provider": "PASSWORD",
        "email": email,
        "password": password
    }
    login_resp = requests.post(login_url, json=login_data)
    token = login_resp.json()["token"]
    headers = {
        'X-Authorization': f'Bearer {token}',
        'User-Agent': 'Mozilla/5.0'
    }
    logger.info("Authentication successful")
    return headers

def get_objects_ids(headers):
    """Get all object IDs that need to be processed"""
    previous_date = datetime.now().strftime("%Y-%m-%d")
    objects_ids = []
    
    # Load and prepare payloads
    payloads = {
        "plan": ("ws-partner-plan", True),
        "offer": ("ws-offer", True),
        "opportunity": ("ws-opportunity", False)
    }
    
    for object_type, (category, needs_extra_filter) in payloads.items():
        # Get count
        count_payload = json.loads(open("cleanup_marketplace_count.json").read()
            .replace("${previous_2_date}", previous_date)
            .replace("${category}", category))
            
        if needs_extra_filter:
            # Add specific filters for plan and offer
            if object_type == "plan":
                count_payload['filters']['group'].append({
                    "op": "OR",
                    "fieldFilters": [{
                        "colId": f"project.{category}.name",
                        "type": "TEXT",
                        "filter": {
                            "op": "CONTAIN",
                            "negate": False,
                            "values": ["auto"]
                        },
                        "criteria": "value"
                    }],
                    "group": []
                })
            elif object_type == "offer":
                count_payload['filters']['group'].append({
                    "op": "OR",
                    "fieldFilters": [{
                        "colId": f"project.{category}.stage",
                        "type": "TEXT",
                        "filter": {
                            "op": "IN",
                            "negate": True,
                            "values": ["42a1b0fc_614f_4675_b30c_b0ec8995b7ad"]
                        },
                        "criteria": "value"
                    }],
                    "group": []
                })

        count_resp = requests.post(
            endpoint + "_main/api/tableView/landing-page/count",
            headers=headers,
            json=count_payload
        )
        count = count_resp.json()['result']
        
        # Get rows
        rows_payload = json.loads(open("cleanup_marketplace_rows.json").read()
            .replace("${previous_2_date}", previous_date)
            .replace("${category}", category))
        
        if needs_extra_filter:
            rows_payload['query']['filters']['group'] = count_payload['filters']['group']

        num_pages = (count // 100) + 1
        for page in range(1, num_pages + 1):
            rows_payload["page"]["number"] = page
            rows_resp = requests.post(
                endpoint + "_main/api/tableView/landing-page/rows",
                headers=headers,
                json=rows_payload
            )
            if "rows" in rows_resp.json():
                objects_ids.extend(row["data"]["ws_global_id"] for row in rows_resp.json()["rows"])
    
    logger.info(f"Found {len(objects_ids)} objects to process")
    return objects_ids

def process_object(args):
    """Process a single object (archive and delete)"""
    object_id, headers = args
    try:
        # Archive
        archive_url = f"{endpoint}_ah/api/marketing_project/v1/marketing_project/{object_id}/archive"
        archive_resp = requests.post(archive_url, headers=headers, json={"archive": True})
        
        # Wait briefly
        time.sleep(0.5)
        
        # Delete
        delete_url = f"{endpoint}_ah/api/marketing_project/v1/marketing_project/{object_id}"
        delete_resp = requests.delete(delete_url, headers=headers)
        
        logger.info(f"Processed object {object_id}: Archive={archive_resp.status_code}, Delete={delete_resp.status_code}")
        return object_id, True
        
    except Exception as e:
        logger.error(f"Error processing object {object_id}: {str(e)}")
        return object_id, False

def main():
    start_time = time.time()
    logger.info("Starting marketplace cleanup")
    
    # Get authentication headers
    headers = get_auth_headers()
    
    # Get objects to process
    objects_ids = get_objects_ids(headers)
    
    # Process objects in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        args = [(obj_id, headers) for obj_id in objects_ids]
        results = list(executor.map(process_object, args))
    
    # Summary
    total = len(results)
    successful = sum(1 for _, success in results if success)
    failed = total - successful
    
    logger.info(f"""
    Cleanup Summary:
    Total objects processed: {total}
    Successful: {successful}
    Failed: {failed}
    Time taken: {time.time() - start_time:.2f} seconds
    """)

if __name__ == "__main__":
    main()