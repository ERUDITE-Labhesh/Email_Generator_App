import asyncio
import json
import os
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from dotenv import load_dotenv
from langchain_gap_analyser import run_full_pipeline

load_dotenv()

# ---------- SAFE JSON PARSING HELPERS ----------

def safe_parse_json(response_text: str):
    """
    Tries to parse LLM output as JSON safely.
    Falls back to extracting valid JSON substring if malformed.
    """
    if not response_text or not response_text.strip():
        return None

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        print("⚠️ JSON parse error, attempting recovery...")
        try:
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start != -1 and end != -1:
                partial = response_text[start:end]
                return json.loads(partial)
        except Exception as e:
            print("❌ JSON recovery failed:", e)
        return None

def normalize_email_output(parsed):
    """
    Ensure consistent output format:
    { "emails": [ { "subject_line": ..., "email_body": ... } ] }
    """
    if not parsed:
        return {"emails": []}

    # Case 1: Expected format already
    if "emails" in parsed:
        return parsed

    # Case 2: Single email dict
    if "subject_line" in parsed and "email_body" in parsed:
        return {"emails": [parsed]}

    # Case 3: List of emails directly
    if isinstance(parsed, list) and all(isinstance(e, dict) and "subject_line" in e for e in parsed):
        return {"emails": parsed}

    return {"emails": []}

async def generate_email_and_subject_async(data):
    MODEL_NAME = os.getenv("OPENROUTER_MODEL", "x-ai/grok-4-fast")
    BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
    API_KEY = os.getenv("OPENROUTER_API_KEY")

    if not API_KEY:
        raise ValueError("OPENROUTER_API_KEY not set in environment variables")

    # Use consistent argument names (ChatOpenAI expects `openai_api_base` etc.)
    llm = ChatOpenAI(
        model=MODEL_NAME,
        openai_api_base=BASE_URL,
        openai_api_key=API_KEY,
        temperature=0.4,
    )

    SYSTEM_PROMPT = """
        You are an expert copywriter and sales strategist generating highly personalized cold emails for Consultadd, 
        a custom AI solutions company for SMBs and enterprises. Your company has the USP of rapidly deploying 
        tailor-made solutions for unique challenges of a company.

        Follow these strict rules:
        - Keep email concise: max 100 words / 250 characters.
        - Avoid jargon or buzzwords.
        - Start with personalized opening referencing company or industry challenge.
        - Briefly mention gap and hint at solution (without giving away much).
        - Highlight Consultadd's value: tailor-made custom AI solutions that unlock efficiency, automate what matters, 
          and fit each company's AI journey.
        - End with curiosity-driven, low-pressure CTA.
        - Avoid spammy words, excessive punctuation, or signatures.
        
        SUBJECT LINE RULES:
        - Catchy, 6–8 words max.
        - Include company name if possible.
        - No spam triggers like FREE, !!!, etc.

        Output must be in **valid JSON** format:
        {
          "subject_line": "...",
          "email_body": "..."
        }
    """

    async def generate_for_gap(gap_item):
        company_name = data.get("company", "")
        ai_solution = gap_item.get("ai_solution", "") or gap_item.get("ai solution", "")
        gap_analysis = gap_item.get("gap_analysis", "")
        pain_points = gap_item.get("pain_points", [])

        user_prompt = f"""
        Generate a personalized cold email for:

        Company: {company_name}

        AI Solution Opportunity:
        {ai_solution}

        Gap Analysis:
        {gap_analysis}

        Key Pain Points:
        {chr(15).join(f"- {pp}" for pp in pain_points[:2])}

        Follow all formatting and output JSON as instructed.
        """

        messages = [
            SystemMessage(content=SYSTEM_PROMPT.strip()),
            HumanMessage(content=user_prompt.strip())
        ]

        response = None
        try:
            response = await llm.ainvoke(messages)
            raw_output = response.content.strip()
            parsed = safe_parse_json(raw_output)

            if not parsed:
                raise ValueError("Model did not return valid JSON")

            parsed["email_body"] = parsed.get("email_body", "").replace("\n", " ").strip()

        except Exception as e:
            error_message = str(e)
            if "Error code: 402" in error_message or "Insufficient credits" in error_message:
                raise ValueError("INSUFFICIENT_CREDITS_ERROR")
            
            print(f"Email generation failed: {e}")
            fallback_text = raw_output if 'raw_output' in locals() else "Unable to generate email."
            parsed = {
                "subject_line": "Quick AI Insight for You",
                "email_body": fallback_text.replace("\n", " ").strip()
            }

        return parsed

    tasks = [generate_for_gap(item) for item in data.get("ai_gap_analysis", [])]
    emails_output = await asyncio.gather(*tasks)

    # Normalize output format
    final_output = normalize_email_output({"emails": emails_output})
    final_output["company"] = data.get("company", "")
    final_output["model_used"] = MODEL_NAME

    return final_output

# ---------- SYNC WRAPPER ----------

def generate_email_and_subject(data):
    return asyncio.run(generate_email_and_subject_async(data))

# ---------- PIPELINE RUNNER ----------

def run_email_generation_pipeline(analysis_id, custom_model=None):
    try: 
        enriched_data = run_full_pipeline(analysis_id)

    # Override model temporarily for regeneration
        if custom_model:
            os.environ["OPENROUTER_MODEL"] = custom_model

        result = generate_email_and_subject(enriched_data)
        print(f"Email generation completed using model: {os.getenv('OPENROUTER_MODEL')}")
        return result
    
    except ValueError as e:
        # Bubble up custom credit exhaustion error
        if "INSUFFICIENT_CREDITS_ERROR" in str(e) or "Insufficient credits" in str(e):
            raise ValueError("INSUFFICIENT_CREDITS_ERROR")
        raise

    except Exception as e:
        print(f"Unexpected pipeline error: {e}")
        raise


