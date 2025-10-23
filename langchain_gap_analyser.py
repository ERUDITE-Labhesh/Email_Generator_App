# import json 
# import os 
# from langchain_openai import ChatOpenAI 
# from langchain.schema import SystemMessage, HumanMessage
# from dotenv import load_dotenv
# from inital_analysis_data_extractor import main_extractor

# load_dotenv()


# def generate_gap_analysis(data):

#     MODEL_NAME = os.getenv("OPENROUTER_MODEL", "x-ai/grok-4-fast")
#     BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
#     API_KEY = os.getenv("OPENROUTER_API_KEY")

#     if not API_KEY:
#         raise ValueError("OPENROUTER_API_KEY not set in environment variables")
    
#     llm = ChatOpenAI(
#         model=MODEL_NAME,
#         openai_api_base=BASE_URL,
#         openai_api_key=API_KEY,
#         temperature=0.4,
#         streaming=True
        
#     )


#     SYSTEM_PROMPT = """
#                         You are an expert in AI transformation for scientific and laboratory industries.
#                         Generate concise and relevant 'gap analysis' and 'pain points' for each AI solution.
#                         Each output must be in JSON format and directly relate to the provided solution and company context.
#                         Keep it short, professional, and insightful. It should have a hook so that can helpful for sales executive to pitch the painpoints
#                         Provide only 2-3 pain points it should be consise and can act as eye opener
#                     """
    
#     results = [] 

#     for opp in data.get("ai_opportunities", []):
#         user_prompt = f""" 
#         Company: {data.get('company')}
#         AI Solution: {opp["solution"]}
#         Why Need of AI Solution: {opp['why']}

#         Generate:
#         1. A short 'gap_analysis' (what is missing today or challenge faced)
#         2. Specific 'pain_points' that this AI solution helps to solve. Provide only 2-3 pain points it should be consise and can act as eye opener

#         Output JSON format:
#         {{
#         "ai solution": "...",
#         "gap_analysis": "...",
#         "pain_points": ["...", "..."]
#         }}
#         """

#         messages = [
#             SystemMessage(content=SYSTEM_PROMPT),
#             HumanMessage(content=user_prompt)
#         ]

#         try: 
#             response = llm.invoke(messages)
#             parsed = json.loads(response.content)
#         except Exception as e:
#             print(f"LLM call failed: {e}")
#             parsed = {
#                 "solution": opp.get("solution"),
#                 "gap_analysis": response.content.strip() if hasattr(response, "content") else "N/A",
#                 "pain_points": []
#             }

#         results.append(parsed)
#         data["ai_gap_analysis"] = results

#     return data

# def run_full_pipeline(analysis_id): 
#     output = main_extractor(analysis_id)
#     enriched_output = generate_gap_analysis(output)
#     return enriched_output


#------------------------------ New Code --------------------------------------# 
import asyncio
import json
import os
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from dotenv import load_dotenv
from inital_analysis_data_extractor import main_extractor

load_dotenv()

async def generate_gap_analysis_async(data):
    MODEL_NAME = os.getenv("OPENROUTER_MODEL", "x-ai/grok-4-fast")
    BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()  # ⚠️ strip whitespace!
    API_KEY = os.getenv("OPENROUTER_API_KEY")

    if not API_KEY:
        raise ValueError("OPENROUTER_API_KEY not set in environment variables")

    llm = ChatOpenAI(
        model=MODEL_NAME,
        base_url=BASE_URL,  # Use base_url (not openai_api_base in newer versions)
        api_key=API_KEY,
        temperature=0.4,
    )

    SYSTEM_PROMPT = """
                        You are an expert in AI transformation for all the industries.
                        Generate concise and relevant 'gap analysis' and 'pain points' for each AI solution.
                        Each output must be in JSON format and directly relate to the provided solution and company context.
                        Keep it short, professional, and insightful. It should have a hook so that can helpful for sales executive to pitch the painpoints
                        Provide only 2-3 pain points it should be consise and can act as eye opener
                    """

    async def process_opportunity(opp):
        user_prompt = f"""
        Company: {data.get('company')}
        AI Solution: {opp["solution"]}
        Why Need of AI Solution: {opp['why']}

        Generate:
        1. A short 'gap_analysis' (what is missing today or challenge faced)
        2. Specific 'pain_points' that this AI solution helps to solve. Provide only 2-3 pain points it should be consise and can act as eye opener

        Output JSON format:
        {{
        "ai solution": "...",
        "gap_analysis": "...",
        "pain_points": ["...", "..."]
        }}
        """

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt.strip())
        ]

        try:
            response = await llm.ainvoke(messages)
            parsed = json.loads(response.content)
        except Exception as e:
            print(f"LLM call failed: {e}")
            parsed = {
                "ai solution": opp.get("solution"),
                "gap_analysis": getattr(response, 'content', 'N/A').strip(),
                "pain_points": []
            }
        return parsed

    tasks = [process_opportunity(opp) for opp in data.get("ai_opportunities", [])]
    results = await asyncio.gather(*tasks)

    data["ai_gap_analysis"] = results
    return data

def generate_gap_analysis(data):
    return asyncio.run(generate_gap_analysis_async(data))

def run_full_pipeline(analysis_id):
    output = main_extractor(analysis_id)
    enriched_output = generate_gap_analysis(output)
    print(enriched_output)
    return enriched_output
