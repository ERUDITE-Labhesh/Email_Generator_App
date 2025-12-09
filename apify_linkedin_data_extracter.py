import asyncio
import json
import os
import re
from datetime import datetime 
from apify_client import ApifyClient
from functools import partial
from dotenv import load_dotenv

load_dotenv()
APIFY_ACTOR_PROFILE_POST = "A3cAPGpwBEG8RJwse"
APIFY_ACTOR_PROFILE_DATA = "yZnhB5JewWf9xSmoM"

APIFY_TOKEN = os.getenv("APIFY_KEY")
if not APIFY_TOKEN:
    print("ERROR: APIFY TOKEN is not valid")


if APIFY_TOKEN:
    client = ApifyClient(APIFY_TOKEN)
else:
    client = None

_thread_semaphore = asyncio.Semaphore(10)

def calculate_duration(start_year, end_year):
    if start_year is None: 
        return "N/A"
    
    current_year = datetime.now().year

    if end_year == "Present":
        try: 
            duartion = current_year - int(start_year)
        except (ValueError, TypeError): 
            return "N/A"
        
    else: 
        try: 
            duartion = int(end_year) - int(start_year)
        except (ValueError, TypeError): 
            return "N/A"
    
    return max(0, duartion)

def cleaning_linkedin_post_data(extracted_data_json_data):
    clean_linkedin_post_data = [] 
    quotes_to_remove = ['\u201c', '\u201d', '\u2019', '\u2026','\ud83d\udea8', '\u2014']

    for item in extracted_data_json_data:
        if not isinstance(item, dict):
            print(f"Skipping non-dictionary item: {item}")
            continue

        cleaned_content = item.get("content", "")
        cleaned_date = item.get("date","")

        if not cleaned_content:
            continue

        cleaned_content = cleaned_content.replace('\n', ' ').replace('\t', ' ')
        cleaned_content = cleaned_content.replace('\u2192', '->')
        cleaned_content = cleaned_content.replace('\u00a0', ' ')
        cleaned_content = cleaned_content.replace('\xa0', ' ')
        cleaned_content = cleaned_content.replace(r'\\"', '"')
       
        for quote in quotes_to_remove:
            cleaned_content = cleaned_content.replace(quote, '')

        cleaned_content = cleaned_content.replace(r'\"', '"')
        cleaned_content = cleaned_content.replace('\\', '')
        cleaned_date = cleaned_date.replace('\u2022', '-')
        if ' - ' in cleaned_date:
            cleaned_date = cleaned_date.split(' - ')[0].strip()
        cleaned_date = cleaned_date.strip()

        cleaned_content = re.sub(' {2,}', ' ', cleaned_content)
        cleaned_content = cleaned_content.strip()

        clean_linkedin_post_data.append({
            "content": cleaned_content.strip(),
            "date": cleaned_date.strip()
        })
    return clean_linkedin_post_data

async def _call_actor_in_thread(actor_id, run_input):

    if not client: 
        raise RuntimeError("Apify client is not initialized.")
    
    async with _thread_semaphore: 
        blocking_call = partial(client.actor(actor_id).call, run_input=run_input)
        return await asyncio.to_thread(blocking_call)

async def _fetch_dataset_items_in_thread(dataset_id):
    if not client:
        raise RuntimeError("Apify client is not initialized.")
    
    async with _thread_semaphore:
        iterate_call = partial(client.dataset(dataset_id).iterate_items)
        return await asyncio.to_thread(lambda: list(iterate_call()))

async def run_actor_and_fetch_post_details(url=None, max_posts=3):

    if not client:
        print("Cannot run actor: Apify client is not initialized.")
        return []
    
    target_urls_list = [url] if url else []

    run_input = {
        "targetUrls": target_urls_list,
        "postedLimit": "any",
        "maxPosts": max_posts,
        "includeQuotePosts": True,
        "includeReposts": True,
        "scrapeReactions": False,
        "maxReactions": 3,
        "scrapeComments": False,
        "maxComments": 3,
        "commentsPostedLimit": "any",
    }

    print(f"Starting Apify Post Scrapper actor run for URL: {url}")

    try:
        run =  await _call_actor_in_thread(APIFY_ACTOR_PROFILE_POST, run_input=run_input)
        raw_items = await _fetch_dataset_items_in_thread(run.get("defaultDatasetId"))

        print("Run finished. Fetching results...")

        extracted_data = [] 
        for item in raw_items:
            extracted_data.append({
            "content" : item.get("content", "N/A"), 
            "date" : item.get("postedAt", {}).get("postedAgoText", "N/A")
            })
        
        clean_data = cleaning_linkedin_post_data(extracted_data)
        extracted_data_json_data = json.dumps(clean_data, indent=4)

        print("Done Extracting Post Details")
        return extracted_data_json_data
    
    except Exception as e: 
        print(f"An error occurred during the Apify call: {e}")
        return []
            
async def run_actor_and_fetch_profile_details(url=None):

    if not client:
        print("Cannot run actor: Apify client is not initialized.")
        return
    target_urls_list = [{"url": url}]

    run_input = {
        "urls":target_urls_list,
        "scrapeCompany": True,
        "findContacts": False,
        "findContacts.contactCompassToken": "",
    }
    print(f"Starting Profile Scapping Apify actor run for URL: {url}")

    try:
        extracted_data = []

        run = await _call_actor_in_thread(APIFY_ACTOR_PROFILE_DATA, run_input=run_input)
        raw_items = await _fetch_dataset_items_in_thread(run.get("defaultDatasetId"))
        print("Run finished. Fetching results...")


        for item in raw_items:
            positions = item.get("positions", [])
            for position in positions:
                position_title = position.get("title", "N/A")
                description = position.get("description", "N/A")
                time_period = position.get("timePeriod")
                company_data = position.get("company", {})
                company_name = "N/A"
                if company_data and company_data != {}:
                    company_name = company_data.get("name")

                start_year = None
                end_year = None
                end_date_data = None

                if time_period and time_period != {}:
                    start_year = position.get("timePeriod", {}).get("startDate", {}).get("year")
                    end_date_data = time_period.get("endDate")
                else: 
                    start_year = None

                if end_date_data is None or end_date_data == "None" or end_date_data == {}:
                    end_year = "Present"
                elif isinstance(end_date_data, dict):
                    end_year = end_date_data.get("year")
                else:
                    end_year = end_date_data.get("year")
                
                total_years = calculate_duration(start_year, end_year)

                extracted_data.append({
                "position": position_title,
                "description": description,
                "start_year": start_year,
                "end_year": end_year,
                "company_name": company_name,
                "total_years_experience": total_years
            })
                
        extracted_profile_data_json_data = json.dumps(extracted_data, indent=4)
        print("Done Extracting Profile Details")
        return extracted_profile_data_json_data 

    except Exception as e: 
        print(f"An error occurred during the Apify call: {e}")
        return []
    
async def async_main(url):

    print("--- Starting Concurrent Apify Runs ---")

    post_task = run_actor_and_fetch_post_details(url=url)
    profile_task = run_actor_and_fetch_profile_details(url=url)

    post_result, profile_result = await asyncio.gather(post_task, profile_task)
    print("--- Concurrent Scraping Finished ---")

    return  post_result, profile_result

if __name__ == "__main__": 
    url = "https://www.linkedin.com/in/richard-scherf-b679376/"

    if client:
        output_post, output_profile = asyncio.run(async_main(url))
        print(output_post)
        print("\n\n#########################################")
        print(output_profile)
        

