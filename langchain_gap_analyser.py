import re
import asyncio
import json
import os
from dotenv import load_dotenv
from inital_analysis_data_extractor import main_extractor

load_dotenv()

_llm_instance = None 
_llm_model_name = None 

def get_llm():
    global _llm_instance, _llm_model_name

    MODEL_NAME = os.getenv("OPENROUTER_MODEL", "x-ai/grok-4-fast")
    BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
    API_KEY = os.getenv("OPENROUTER_API_KEY")

    if not API_KEY:
        raise ValueError("OPENROUTER_API_KEY not set in environment variables")
    
    if _llm_instance is None or _llm_model_name != MODEL_NAME:
        from langchain_openai import ChatOpenAI
        _llm_instance = ChatOpenAI(
            model=MODEL_NAME,
            openai_api_base=BASE_URL,
            openai_api_key=API_KEY,
            temperature=0.4,
        )
        _llm_model_name = MODEL_NAME
    
    return _llm_instance

async def generate_gap_analysis_async(data):
    from langchain.schema import SystemMessage, HumanMessage 
    llm = get_llm()

    SYSTEM_PROMPT = """
                        You are an expert in AI transformation for all the industries.
                        Generate concise and relevant 'gap analysis' and 'pain points' for each AI solution.
                        Each output must be in JSON format and directly relate to the provided solution and company context.
                        Keep it short, professional, and insightful. It should have a hook so that can helpful for sales executive to pitch the painpoints
                        Provide only 2-3 pain points it should be consise and can act as eye opener

                        You MUST output ONLY valid JSON. 
                        No explanations, no markdown, no code fences, no prefixes.
                        Output a raw JSON object ONLY.
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
            content = response.content.strip()
            json_blocks = re.findall(r"\{(?:[^{}]|(?:\{[^{}]*\}))*\}", content)
            parsed = None

            for block in json_blocks:
                try:
                    parsed = json.loads(block)
                    break
                except:
                    continue

            # Fallback: try parsing entire content
            if parsed is None:
                parsed = json.loads(content)

        except Exception as e:
            print(f"LLM call failed: {e}")
            error_message = str(e)
            if "Error code: 402" in error_message or "Insufficient credits" in error_message:
                raise ValueError("INSUFFICIENT_CREDITS_ERROR")
            parsed = {
                "ai solution": opp.get("solution"),
                "gap_analysis": getattr(response, 'content', 'N/A').strip(),
                "pain_points": []
            }
        return parsed

    tasks = [process_opportunity(opp) for opp in data.get("ai_opportunities", [])]
    results = await asyncio.gather(*tasks)
    data["ai_gap_analysis"] = results

    import gc
    gc.collect()

    return data

def generate_gap_analysis(data):
    return asyncio.run(generate_gap_analysis_async(data))

def run_full_pipeline(analysis_id):
    try: 
        output = main_extractor(analysis_id)
        enriched_output = generate_gap_analysis(output)
        print(enriched_output)
        return enriched_output
    except ValueError as e:
        # Bubble up custom credit exhaustion error
        if "INSUFFICIENT_CREDITS_ERROR" in str(e) or "Insufficient credits" in str(e):
            raise ValueError("INSUFFICIENT_CREDITS_ERROR")
        raise