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
        print("JSON parse error, attempting recovery...")
        try:
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start != -1 and end != -1:
                partial = response_text[start:end]
                return json.loads(partial)
        except Exception as e:
            print("JSON recovery failed:", e)
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

async def generate_email_and_subject_async(data, designation=""):
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

    # NEW: Enhanced system prompt with designation awareness
    SYSTEM_PROMPT = f"""

            You are an expert B2B copywriter and sales strategist specializing in personalized cold emails for Consultadd, a custom AI solutions company that helps SMBs deploy agentic AI systems rapidly and effectively. Keep email concise: max 100 words / 250 characters.
            Your goal is to write short, high-impact, **personalized cold emails** that reflect Consultadd’s brand: confident, professional, outcome-focused, and conversational.
            Consultadd’s USP:
            We build tailor-made AI solutions for unique business challenges, helping teams automate manual, repetitive tasks with smart agents, so they can focus on high-value work like customer relationships and innovation. Consultadd is a partner in taking business performance to the next level, reinventing how work gets done.
            Required Start:** The email must begin with a phrase referencing Consultadd's past success (e.g., "We have helped...", "We assisted...", or similar).
            Follow these strict rules while generating each email:
    
            Length:
            Keep the body under 50 words or 250 characters.
            Write in short, clear sentences.

            Tone:
            Confident, professional, conversational, never salesy or robotic.
            Use positive framing; avoid problem-heavy or negative language.

            Opening:
            Start with impact, a quantifiable benefit or intriguing outcome (e.g., “We helped a client cut processing time by 50% using AI-driven automation.”).
            Required Start:** The email must begin with a phrase referencing Consultadd's past success (e.g., "We have helped...", "We assisted...", or similar).
            Personalize naturally, refer to the company, role, or a relevant context, but avoid flattery.

            *Starting Phrase (Mandatory):** The email must begin by referencing Consultadd's capability or past success. Select one phrase from the list below and integrate a specific, quantified benefit or outcome:
            * *Starter Pool:*
                * We’ve been helping companies...
                * We’ve been working closely with [industry]...
                * We've successfully been able to do...
                * We’ve been exploring ways to simplify...
                * We helped...
                * We can help reduce [pain\_point]...
                * We've assisted...
                * We implemented...
                * We are equipped to achieve [Solution]...
                * We provide the capability to resolve [pain\_point]...
                * We offer solutions that cut [pain\_point]...

            **Personalization:** Reference the company, role, or relevant context naturally (avoid generic flattery).

            Value Proposition:
            Emphasize Consultadd’s expertise in agentic AI and its speed of deployment.
            Show how our AI agents can simplify operations, reduce costs, or improve decision-making.

            Call-to-Action (CTA):
            End with a curiosity-driven, low-pressure invitation (e.g., “Worth a 10-min chat to explore?” or “Open to a quick discovery call to see how this could work for you?”).

            Language Rules:
            Avoid jargon, buzzwords, or filler.
            Avoid spam triggers (e.g., “guaranteed,” “free,” “act now,” “exclusive”).
            No excessive punctuation or signatures.

            The email recipient is a {designation or 'decision maker'} at the company.
            Tailor the message to the {designation or 'recipient'} role:

            For "CEO": 
                "focus": "strategic vision, ROI, competitive advantage, business transformation",
                "tone": "high-level, outcome-focused, emphasizing long-term value",
                "pain_points_angle": "market positioning, revenue growth, operational efficiency at scale",
                "cta_style": "strategic discussion about competitive edge" 
        
            For "Co-Founder": 
                "focus": "innovation, scalability, product-market fit, growth acceleration",
                "tone": "collaborative, growth-oriented, emphasizing agility and innovation",
                "pain_points_angle": "scaling challenges, product differentiation, rapid deployment",
                "cta_style": "explore innovative solutions together"
        
            For "Marketing Manager": 
                "focus": "customer engagement, lead generation, personalization, campaign effectiveness",
                "tone": "results-driven, metrics-focused, emphasizing measurable outcomes",
                "pain_points_angle": "customer insights, conversion rates, marketing automation",
                "cta_style": "discuss measurable marketing improvements"
        
            For "Chief Revenue Officer":
                "focus": "revenue growth, sales efficiency, pipeline optimization, customer lifetime value",
                "tone": "numbers-driven, emphasizing revenue impact and sales acceleration",
                "pain_points_angle": "sales productivity, deal velocity, revenue predictability",
                "cta_style": "explore revenue acceleration opportunities"
            
            For "CRO": Alias for Chief Revenue Officer
                "focus": "revenue growth, sales efficiency, pipeline optimization, customer lifetime value",
                "tone": "numbers-driven, emphasizing revenue impact and sales acceleration",
                "pain_points_angle": "sales productivity, deal velocity, revenue predictability",
                "cta_style": "explore revenue acceleration opportunities"

            - Highlight Consultadd's value: tailor-made custom AI solutions that unlock efficiency, automate what matters, 
            and fit each company's AI journey.
            - End with curiosity-driven, low-pressure CTA.
            - Avoid spammy words, excessive punctuation, or signatures.
            - Show understanding of challenges specific to their role
            - Highlight outcomes that matter to their role (ROI for CEOs, efficiency for CROs, etc.)
            
            SUBJECT LINE RULES:
            - Catchy, 6–8 words max.
            - Include company name if possible.
            - No spam triggers like FREE, !!!, etc.

            Output must be in **valid JSON** format:
            {{
            "subject_line": "...",
            "email_body": "..."
            }}

    """
    async def generate_for_gap(gap_item):
        company_name = data.get("company", "")
        ai_solution = gap_item.get("ai_solution", "") or gap_item.get("ai solution", "")
        gap_analysis = gap_item.get("gap_analysis", "")
        pain_points = gap_item.get("pain_points", [])

        user_prompt = f"""
            You are an expert cold email copywriter specializing in B2B AI outreach. 
            Write a short, high-impact cold email designed to engage a professional who holds this role:
            {designation or 'business decision maker'}.
            Before writing, consider:
            - What does this person care about most in their role?
            - What language/metrics resonate with them? (ROI, efficiency, growth, etc.)
            - What would make THEM stop scrolling and read this email?

            The email must:
            Start with a phrase referencing Consultadd’s past success or ongoing impact.
            Approved starting patterns (choose one naturally based on context):
            - “We’ve been helping companies...”
            - “We’ve been working closely with {"industry"} teams...”
            - “We’ve successfully been able to...”
            - “We’ve been exploring ways to simplify...”
            - “We helped...”
            - “We can help reduce [pain_point]...”
            - “We’ve assisted...”
            - “We implemented...”
            - “We are equipped to achieve [solution]...”
            - “We provide the capability to resolve [pain_point]...”
            - “We offer solutions that cut [pain_point]...”
            - “I noticed...”

            Do **not** mention or reference the person’s title in the email.
            Instead, shape the tone, priorities, and message style so it naturally appeals to that role’s mindset and goals.
            START WITH IMPACT: Begin the email with a quantifiable benefit, an intriguing outcome, or a specific, relevant challenge faced by the company.
            Context
            - Company: {company_name}
            - AI Solution Opportunity: {ai_solution}
            - Gap Analysis: {gap_analysis}
            - Key Pain Points:
            {chr(15).join(f"- {pp}" for pp in pain_points[:2])}

            Writing Objectives
            - Briefly reference the gap or missed opportunity (from the analysis).  
            - Subtly position the AI solution as the next logical step — valuable, practical, and worth exploring.  
            - End with a light, curiosity-driven CTA (e.g., “worth a quick chat?”).  
            - Keep tone professional, confident, and concise — no buzzwords, no exaggeration.  
            - Do **not** include greetings like “Dear CEO” or mention any designation directly.  

            Style Guidance by Role
            - CEO / Co-Founder → strategic vision, efficiency, future readiness, ROI focus.  
            - Marketing Manager → campaign results, automation, customer insight, data-driven wins.  
            - Chief Revenue Officer → revenue impact, pipeline visibility, performance uplift.  
            - Default → operational excellence, innovation, efficiency, value creation.

            End with a **curiosity-driven, low-pressure CTA**, e.g.:
            - “Worth a quick chat to explore?”
            - “Open to a brief conversation to see how this might help?”
            - “Would you be open to exploring this next week?”

            Output Format (must be valid JSON)
            {{
            "subject_line": "string (6–8 words max, catchy, natural, may include company name)",
            "email_body": "string (concise email, under 100 words, written toward the mindset of the specified role)"
            }}

            Pro tip: After writing, ask yourself: "If I received this, would I reply?" If not, make it more specific and human.
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
    # NEW: Include designation in output
    final_output["designation"] = designation

    return final_output

# ---------- SYNC WRAPPER ----------
def generate_email_and_subject(data, designation=""):
    return asyncio.run(generate_email_and_subject_async(data, designation))

# ---------- PIPELINE RUNNER ----------
def run_email_generation_pipeline(analysis_id, custom_model=None, designation=""):
    try: 
        enriched_data = run_full_pipeline(analysis_id)

        # Override model temporarily for regeneration
        if custom_model:
            os.environ["OPENROUTER_MODEL"] = custom_model

        result = generate_email_and_subject(enriched_data, designation=designation)
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
