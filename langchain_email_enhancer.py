import asyncio
import json
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage

load_dotenv()



def safe_parse_json(response_text: str):
    if not response_text or not response_text.strip():
        return None
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        try:
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start != -1 and end != -1:
                return json.loads(response_text[start:end])
        except Exception:
            return None
    return None


def normalize_output(parsed):
    """
    Ensures output always follows:
    { "emails": [ { subject_line, email_body } ] }
    """
    if not parsed:
        return {"emails": []}

    if "emails" in parsed:
        return parsed

    if isinstance(parsed, list):
        return {"emails": parsed}

    if "subject_line" in parsed and "email_body" in parsed:
        return {"emails": [parsed]}

    return {"emails": []}

async def enhance_email_async(email_block: dict, company: str = "", designation: str = ""):
    """
    Enhances a single email (subject + body).
    """

    MODEL_NAME = os.getenv("OPENROUTER_MODEL", "x-ai/grok-4-fast")
    BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
    API_KEY = os.getenv("OPENROUTER_API_KEY")

    if not API_KEY:
        raise ValueError("OPENROUTER_API_KEY is missing")

    llm = ChatOpenAI(
        model=MODEL_NAME,
        openai_api_key=API_KEY,
        openai_api_base=BASE_URL,
        temperature=0.3
    )

    system_prompt = f"""

    You are an expert B2B copywriter and sales strategist specializing in personalized cold emails. Your unique niche is generating short, highly **attention-grabbing, humorous** emails that remain professional enough for business outreach.

    Your job is to generate a single cold outreach email based on the following information the user provides:
    * The company sending the email (Your client).
    * The company receiving the email (The prospect).
    * The core value proposition / problem solved.
    * Specific details, metrics, or benefits to include.

    Tone and Style Requirements:
    - Humor: Light, playful, and confidence-driven. The humor must feel natural and avoid being juvenile or forced.
    - Confidence: Confident, assertive, conversational, and outcome-focused. Avoid sounding salesy, desperate, or robotic.
    - Clarity: Short, punchy, and highly skimmable.

    Strict Constraints:
    - Email Count: Generate 1 email only.
    - Max Word Count: Do NOT exceed 130 words for the entire body.
    - Jargon: Do NOT use clichés, hype, or buzzwords (e.g., "synergy," "disrupt," "cutting-edge").
    - Greeting: The email body must start with a casual greeting (e.g., "Hey," "Quick question," or similar) followed immediately by the hook. Do NOT use the generic "Hi [Name]."

    Email Structure:
    1. Subject Line: Must be catchy, curiosity-driven, and include a touch of humor (e.g., "I think we found where your missing 2–4 weeks went," "Want a tireless intern who never sleeps?").
    2. Opening Hook: The email must start with a humorous, attention-grabbing sentence that relates to the prospect's pain point or the benefit you provide.
    3. Value Explanation: A brief explanation (1–2 sentences) of the core value proposition/problem solved.
    4. Personalization: Tie the value directly to the recipient’s specific situation using the user-provided details.
    5. Call-to-Action (CTA): End with a low-pressure, curiosity-driven invitation for a short chat (e.g., "Worth 5 minutes to see how that works?" or "Fancy a quick chat?").

    Output Format:
    Always output valid JSON:
    {{
        "subject_line": "...",
        "email_body": "..."
    }}

    """

    user_prompt = f"""
        You are an expert cold-email copywriter.
        Rewrite and improve the following cold email for the company {company}.

        INPUT EMAIL
        Subject: {email_block.get("subject_line", "")}
        Body: {email_block.get("email_body", "")}

        REQUIREMENTS

        Preserve the original intent, but significantly improve clarity, persuasion, and flow.

        Do not include any greeting such as “Hello [Recipient]” or similar.

        Keep the tone professional, human, and tailored toward the mindset of the target role.

        The email must be under 100 words.

        The subject line must be 6–8 words, catchy, natural, and may reference the company name.

        OUTPUT FORMAT (STRICT JSON ONLY)

        Before finalizing, evaluate your output by asking:
        “If I received this email, would I reply?”
        If not, revise to make it more specific, relevant, and compelling.

        Output Format (must be valid JSON)
                {{
                "subject_line": "string (6–8 words max, catchy, natural, may include company name)",
                "email_body": "string (concise email, under 100 words, written toward the mindset of the specified role)"
                }}

        Pro tip: After writing, ask yourself: "If I received this, would I reply?" If not, make it more specific and human.

    """

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    try:
        response = await llm.ainvoke(messages)
        raw = response.content.strip()
        parsed = safe_parse_json(raw)

        if not parsed:
            raise ValueError("Invalid JSON returned.")

        parsed["email_body"] = parsed.get("email_body", "").replace("\n", " ").strip()
        return parsed

    except Exception as e:
        print("Enhancer Error:", e)
        return {
            "subject_line": email_block.get("subject_line", "Updated AI Insight"),
            "email_body": email_block.get("email_body", "").strip()
        }


async def enhance_email_set_async(email_output: dict):
    """
    Takes output from langchain_email_generator.py and enhances each email.
    """
    
    all_emails =[]
    print("Incoming email_output:", email_output)
    company = email_output.get("company", "")
    designation = email_output.get("designation", "")

    for e in email_output.get('emails', []):
        all_emails.append({
        "subject_line": e.get("subject_line", ""),
        "email_body": e.get("email_body", "")
        })

    print("Parsed emails for enhancement:", all_emails)

    tasks = [
        enhance_email_async(email, company, designation)
        for email in all_emails
    ]

    enhanced_results = await asyncio.gather(*tasks)

    final = normalize_output({"emails": enhanced_results})
    final["company"] = company
    final["designation"] = designation
    final["model_used"] = os.getenv("OPENROUTER_MODEL")

    return final


def enhance_email_set(email_output: dict):
    return asyncio.run(enhance_email_set_async(email_output))


def run_email_enhancer_pipeline(raw_email_output):
    try:
        enhanced = enhance_email_set(raw_email_output)
        return enhanced
    except Exception as e:
        print("Enhancer Pipeline Error:", e)
        raise