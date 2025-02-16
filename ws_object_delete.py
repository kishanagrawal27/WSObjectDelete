import os
import allure
import time
from datetime import datetime, timedelta
import requests
import json
import concurrent.futures
import pytest

# login
endpoint = os.environ.get("ENDPOINT")
email = os.environ.get("EMAIL")
password = os.environ.get("PASSWORD")
login = "_ah/api/network/v1/person/login"
table_count_url = "_main/api/tableView/landing-page/count"
table_rows_url = "_main/api/tableView/landing-page/rows"
login_resp = requests.post(endpoint + login, json={"auth_provider":"PASSWORD","email":email,"password":password})
login_resp = login_resp.json()
headers = {'X-Authorization': 'Bearer ' + login_resp["token"], 'User-Agent': 'Mozilla/5.0'}
print("Headers: {}".format(headers))

# date
previous_date = (datetime.now() + timedelta(days=0)).strftime("%Y-%m-%d")

# count payload
plan_payload = json.loads(open("cleanup_marketplace_count.json").read().replace("${previous_2_date}", previous_date).replace("${category}", "ws-partner-plan"))
plan_payload['filters']['group'].append({
        "op": "OR",
        "fieldFilters": [
          {
            "colId": "project.ws-partner-plan.name",
            "type": "TEXT",
            "filter": {
              "op": "CONTAIN",
              "negate": False,
              "values": [
                "auto"
              ]
            },
            "criteria": "value"
          }
        ],
        "group": []
      })
offer_payload = json.loads(open("cleanup_marketplace_count.json").read().replace("${previous_2_date}", previous_date).replace("${category}", "ws-offer"))
offer_payload['filters']['group'].append({
                    "op": "OR",
                    "fieldFilters": [
                        {
                            "colId": "project.ws-offer.stage",
                            "type": "TEXT",
                            "filter": {
                                "op": "IN",
                                "negate": True,
                                "values": [
                                    "42a1b0fc_614f_4675_b30c_b0ec8995b7ad"
                                ]
                            },
                            "criteria": "value"
                        }
                    ],
                    "group": []
                })
opportunity_payload = json.loads(open("cleanup_marketplace_count.json").read().replace("${previous_2_date}", previous_date).replace("${category}", "ws-opportunity"))

# rows payload
plan_rows_payload = json.loads(open("cleanup_marketplace_rows.json").read().replace("${previous_2_date}", previous_date).replace("${category}", "ws-partner-plan"))
plan_rows_payload['query']['filters']['group'].append({
        "op": "OR",
        "fieldFilters": [
          {
            "colId": "project.ws-partner-plan.name",
            "type": "TEXT",
            "filter": {
              "op": "CONTAIN",
              "negate": False,
              "values": [
                "auto"
              ]
            },
            "criteria": "value"
          }
        ],
        "group": []
      })
offer_rows_payload = json.loads(open("cleanup_marketplace_rows.json").read().replace("${previous_2_date}", previous_date).replace("${category}", "ws-offer"))
offer_rows_payload['query']['filters']['group'].append({
                    "op": "OR",
                    "fieldFilters": [
                        {
                            "colId": "project.ws-offer.stage",
                            "type": "TEXT",
                            "filter": {
                                "op": "IN",
                                "negate": True,
                                "values": [
                                    "42a1b0fc_614f_4675_b30c_b0ec8995b7ad"
                                ]
                            },
                            "criteria": "value"
                        }
                    ],
                    "group": []
                })
opportunity_rows_payload = json.loads(open("cleanup_marketplace_rows.json").read().replace("${previous_2_date}", previous_date).replace("${category}", "ws-opportunity"))

# get count - offer, plan & opportunity
plan_count = requests.request("POST", endpoint+table_count_url, headers=headers, json=plan_payload).json()['result']
offer_count = requests.request("POST", endpoint+table_count_url, headers=headers, json=offer_payload).json()['result']
opportunity_count = requests.request("POST", endpoint+table_count_url, headers=headers, json=opportunity_payload).json()['result']
total_count = plan_count + offer_count + opportunity_count

objects_ids = []

payloads = {
        "plan": (plan_rows_payload, plan_count),
        "opportunity": (opportunity_rows_payload, opportunity_count),
        "offer": (offer_rows_payload, offer_count)
}

for object_type, (payload, count) in payloads.items():
    num = (count // 100) + 1
    for i in range(1, num + 1):
        payload["page"]["number"] = i
        response = requests.request("POST", endpoint + table_rows_url, headers=headers, json=payload).json()
        if "rows" in response:
            for j in response["rows"]:
                objects_ids.append(j["data"]["ws_global_id"])
print(len(objects_ids))


@allure.parent_suite("MarketPlace Data Cleanup")
@pytest.mark.MarketPlaceDataCleanup
class TestMarketplaceCleanup:

    @allure.title("Archive and Delete Projects")
    @pytest.mark.parametrize("index", range(total_count))
    def test_marketplace_archive_delete(self, index):
        archive_url = endpoint + "_ah/api/marketing_project/v1/marketing_project/" + objects_ids[index] + "/archive"
        a_payload = {"archive": True}
        a_resp = requests.request("POST", archive_url, headers=headers, json=a_payload)
        print(a_resp.status_code)
        time.sleep(0.5)
        delete_url = endpoint + "_ah/api/marketing_project/v1/marketing_project/" + objects_ids[index]
        d_resp = requests.request("DELETE", delete_url, headers=headers)
        print(d_resp.status_code)