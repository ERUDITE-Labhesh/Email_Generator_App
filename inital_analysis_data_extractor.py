import requests
import time
import json
from dotenv import load_dotenv
import os

load_dotenv()

def main_extractor(analysis_id):
    base_url = os.getenv("API_BASE_URL", "https://biz-api.log1.com/api/v1/analyze")
    bearer_token = os.getenv("API_BEARER_TOKEN")

    if not bearer_token:
        raise ValueError("API_BEARER_TOKEN is not set in environment variables")
    
    headers = {
            'Authorization': f'Bearer {bearer_token}',
            'Content-Type': 'application/json'
        }
    inital_analysis_url = f"{base_url}/{analysis_id}/files/initial_analysis"

    result, data = get_inital_analysis_status(inital_analysis_url, headers)
    output = get_inital_analysis_data(data)
    return output

def get_inital_analysis_status(status_url, headers): 
    try: 
        status_response = requests.get(status_url, headers=headers)
        if status_response.status_code == 200:
            status_data = status_response.json()
            if status_data["overall_status"] == 'initial_complete' or status_data["status"] == 'completed' or status_data["overall_status"] == 'completed':
                FLAG = 1
            else: 
                FLAG = 0
        else: 
            print(f"Error: Received status code {status_response.status_code}")
            return False 
              
    except requests.exceptions.RequestException as e:
            print(f"Error during status check: {e}")
            print(e)
    
    if FLAG != 1:
        print("NOT COMPLETED .. CAN'T GENERATE THE INFORMATION")
        return False
    else: 
        print("INITAL ANALYSIS IS COMPLETED")
        return True, status_data

def get_inital_analysis_data(file_data): 

    inital_analysis_url = file_data.get('presigned_url')
    inital_analysis_data = requests.get(inital_analysis_url).json()

    company_name = inital_analysis_data.get("company",{}).get("name", "")
    about_company = inital_analysis_data.get("more_info", {})

# ai_opportunity_hypotheses 
    ai_opportunities = []
    ai_opportunity = inital_analysis_data.get("ai_opportunity_hypotheses", {})

    
    for item in ai_opportunity:
        ai_opportunities.append({
            "solution": item.get("hypothesis", ""),
             "why": item.get("why", "")
        })
       
    # value_prop_angles
    value_prop_angles_data = []
    value_prop_angles = inital_analysis_data.get("value_prop_angles", {})

    for item in value_prop_angles:
        value_prop_angles_data.append(item.get("angle", ""))

    #pain_points_and_goals

    pain_points_and_goals = []
    pp_g = inital_analysis_data.get("pain_points_and_goals", {})
    for item in pp_g:
        pain_points_and_goals.append({
            "pain_point": item.get("item", ""),
            "goal": item.get("why", "")
        })

    # icps_to_contact
    hook_message = []
    icps_to_contact = inital_analysis_data.get("icps_to_contact", {})

    for item in icps_to_contact: 
        hook_message.append(item.get("messaging_hook", ""))

    json_output = {
        "company": company_name,
        "about":  about_company,
        "ai_opportunities": ai_opportunities,
        "pain_points_and_goals": pain_points_and_goals,
        "value_prop_angles": value_prop_angles_data,
        "hooks": hook_message
    }

    return json_output