import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from dotenv import load_dotenv


load_dotenv()

POST_DATE_THRESHOLD = timedelta(days=90)

MODEL_NAME = os.getenv("OPENROUTER_MODEL", "x-ai/grok-4-fast")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
API_KEY = os.getenv("OPENROUTER_API_KEY")

if not API_KEY:
    raise ValueError("OPENROUTER_API_KEY not set in environment variables")


def safe_parse_json(response_text: str):
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
                return json.loads(response_text[start:end])
        except Exception as e:
            print("JSON recovery failed:", e)
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

def parse_linkedin_date(date_string):
    now = datetime.now()
    date_string = date_string.lower().strip()

    try: 
        if 'ago' in date_string:
            parts = date_string.split()
            if len(parts) >= 2:
                value = int(parts[0])
                unit = parts[1]
            
            if 'week' in unit:
                    return now - timedelta(weeks=value)
            elif 'month' in unit:
                return now - timedelta(days=value * 30.4)
            elif 'day' in unit:
                return now - timedelta(days=value)
        
        elif date_string.startswith('0 month'):
            return now
    except Exception:
        print("Error Occur!")
        pass
    return None

def filter_recent_posts(posts):
    recent_post = []

    for post in posts: 
        post_date = parse_linkedin_date(post.get("date", ""))
        if post_date and (datetime.now() - post_date) <= POST_DATE_THRESHOLD:
            post["strategy"] = "RECENT_POST"
            recent_post.append(post)
    return recent_post

def format_career_journey_context(experience, designation):
    career_summary = [] 
    total_experience = 0
    if not experience: 
        return None 
    try: 
        for pos in experience:
            position = pos.get('position', "N/A")
            company = pos.get("company_name", "N/A")

            if position !="N/A" and company !="N/A":
                career_summary.append(f"- {position} at {company} (Experience: {pos.get('total_years_experience', 0)} years)")
            
            years = pos.get("total_years_experience",1)

            if isinstance(years, (int, float)):
                total_experience += years 
            
        if career_summary: 
            context = (
                f"The recipient is the {designation}. Thier professional spans approximately {total_experience: .0f} years, with key roles including \n"
                f"{chr(10).join(career_summary)}\n\n"
                "Use this specific career background to frame the conversation"
            )
            return {
                "strategy": "CAREER_JOURNEY",
                "personalization_context": context
            }
        else: 
            return None

    except (json.JSONDecodeError, TypeError):
        return None

# LLM SETUP - INITALIZER 

def get_llm():
    return ChatOpenAI(
        model=MODEL_NAME,
        openai_api_key=API_KEY,
        openai_api_base=BASE_URL,
        temperature=0.3
    )

async def llm_generate_experience_email(context, company, designation): 
    llm = get_llm()

    SYS_PROMPT_CAREER = """
    You are an expert B2B cold email strategist.Generate ONE concise(max 100 words / 250 characters), personalized cold email using career experience subtly, recipient's professional background and career journey.

    The recipient is the {designation}. Their career spans X years with key roles like [details in context].

    STRICT WRITING RULES (NON-NEGOTIABLE):
    - The email MUST open with a role-truth question.
    - The role-truth question must reflect a common, lived experience.
    - It must be phrased as a question.
    - Do NOT pitch, explain, or introduce Consultadd before the question.

    Instructions:
    - Keep the email under 100 words.
    - Weave the career context naturally into the opening or body, showing awareness of their experience.
    - Maintain a professional, confident, outcome-focused tone.
    - End with a low-pressure, curiosity-driven CTA.
    - Always output valid JSON:
    {{
        "subject_line": "...",
        "email_body": "..."
    }}
    """
    user_prompt = f"""
        Company: {company}
        Recipient Designation: {designation}

        Based on this career journey that is Career Context:
        {context}

        Act as a senior, human-centric Sales Development Representative (SDR).(max 100 words / 250 characters), Your task is to write a short, high-impact cold email to a {designation} based on the narrative of their professional journey.
        ### INPUT DATA:
        - Recipient Designation: {designation}
        - Career Background Context: {context}

        ### INSTRUCTIONS FOR THE "CAREER JOURNEY" OPENER:
        1. Identify a key transition or a common thread in the recipient's career context (e.g., their growth from {designation} or their long-standing tenure at specific companies).
        2. Start the email by acknowledging this professional path in a way that shows you’ve actually looked at their profile. Avoid "I was looking at your LinkedIn."

        INSTRUCTIONS:
        - Start the email with the role-truth question above
        - Reference the LinkedIn post naturally AFTER the opening question
        - Keep the email under 100 words
        - No pitch language

        ### CRITICAL CONSTRAINTS (Spam Prevention & Human Tone):
        1. NO SPAM TRIGGERS: Do not use aggressive sales words (e.g., "Guaranteed," "Free," "100%," "Scale," "Revolutionary," "Optimize," "Unlock").
        2. PUNCTUATION: Use a maximum of ONE (!) exclamation mark in the entire email. No ALL CAPS words.
        3. NUMERICS: Avoid heavy use of percentages or large dollar signs. Focus on qualitative value.
        4. TONE: Professional yet conversational. Write like a colleague, not a vendor. Avoid AI cliches like "Hope you're having a productive week."
        5. STRUCTURE: 
        - Use a clear, benefit-driven bulleted list (2-3 points) if explaining value.
        - Include a low-friction, one-sentence Call to Action. 

        ### OUTPUT FORMAT:
        Return ONLY a valid JSON object:
        {{
            "subject_line": "A concise, non-promotional subject line (3-6 words)",
            "email_body": "The complete email body content"
        }}
        """
    response = await llm.ainvoke([
        SystemMessage(content=SYS_PROMPT_CAREER),
        HumanMessage(content=user_prompt)
    ])
    parsed = safe_parse_json(response.content)
    if not parsed:
        raise ValueError("Invalid JSON from experience LLM")

    return parsed

async def llm_generate_post_email(post_content, company, designation):
    llm = get_llm()

    SYS_PROMPT_POST = """
    You are an expert B2B copywriter and sales strategist specializing in ultra-personalized cold emails for Consultadd, a custom AI solutions company that helps SMBs deploy agentic AI systems rapidly and effectively.

    Your job:
    Generate short, high-impact emails (max 100 words / 250 characters) that feel human, specific, and rooted in the recipient’s real world, post activity.
    The recipient is the {designation}. They recently shared: "{post_content_truncated}..."

    Your email must naturally reference either:
    A recent LinkedIn post
    A topic they frequently discuss
    A career theme (e.g., “scaling CS teams,” “multi-vendor ops,” “pipeline efficiency,” etc.)

    The email must start with a personalized observation based on their LinkedIn experience or recent post activity.

    The opening should:
    Reference something specific they said, posted, shared, or did
    Or reference a responsibility pattern from their past roles
    Or highlight a universal truth of their role in a conversational way
    The opening must NOT start with what Consultadd has done.
    It must start in their world.
    Approved opening styles (pick one):
    Post-based opener
    “Saw your post about tightening compliance workflows…”
    “Noticed your update about hiring two fulfillment specialists…”

    Role-truth opener (pattern recognition, not flattery)
    “When something escalates, does it still land on your desk first?”
    “When a source looks off, are you still the one untangling it?”

    Industry pattern opener
    “Across most supply-chain teams, vendor updates still end up owning half the week…”
    “In many CS orgs, escalations still skip the playbooks and land on one desk…”

    2. Where Consultadd Comes In

    After the opening sentence(s), and only then, introduce Consultadd’s capability as a soft bridge, not a pitch:

    Approved transitions:
    “We’ve been seeing teams solve this with agentic AI…”
    “We recently helped a team automate this without changing their systems…”
    “This is where AI agents tend to remove 10–20 hrs/week for teams like yours…”
    This keeps the email recipient-first, insight-led, and avoids hardsell energy.

    3. Tone
    Confident, professional, conversational
    Zero fluff, zero corporate jargon
    Short sentences
    No negativity, no fear-based wording
    Outcome-focused

    4. Role-specific relevance:
    Maintain the same consistency in relevance as earlier for their roles. Adapt benefits, pain points, and CTA depending on role and department.

    5. Value Proposition

    Highlight that Consultadd builds:
    Custom AI agents 
    Adaptive and intelligent agents 
    Tailored for unique business needs of small businesses 
    Automating repetitive, manual tasks
    Increase productivity 
    Unlock faster growth and business value

    6. CTA

    End with a short, curiosity-based question that keeps the conversation going.
    Avoid any reference to meetings, calls, demos, time, or scheduling.
    The CTA should feel like a natural continuation of the email — a prompt to share their experience.

    Approved CTA styles:
    Curiosity loop (“Wondering if that’s familiar on your side.”)
    Pattern-check (“Still happening on your end?”)
    Open-ended reflection (“How does that show up for you these days?”)
    Light peer exchange (“Open to comparing notes?”)
    Or allow the final question in the email body to be the CTA.

    Avoid:
    “10-minute chat?”
    “Jump on a call?”
    “Interested in exploring?”
    Anything that feels like a pitch or ask.

    Always output valid JSON:
    {{
        "subject_line": "...",
        "email_body": "..."
    }}
    """

    user_prompt = f"""

        Company: {company}
        Recipient Designation: {designation}

        Recent LinkedIn Post:
        {post_content}

        Write a short, personalized cold email (max 100 words / 250 characters) that naturally references their recent LinkedIn post as the opener. Your goal is to write a high-conversion, short cold email. The post reference should feel like a genuine conversation starter, not a forced compliment or not a marketing bot.

        **Critical Requirements - Email Deliverability & Spam Prevention:**

        1. **Avoid ALL Spam Triggers:**
        - No words like: FREE, GUARANTEED, ACT NOW, LIMITED TIME, EXCLUSIVE OFFER, CLICK HERE, URGENT, AMAZING, INCREDIBLE
        - No aggressive sales language: "buy now", "sign up today", "don't miss out"
        - No scam-associated phrases: "make money fast", "risk-free", "no obligation"
        - No excessive punctuation (max 1 exclamation mark if absolutely needed)
        - NO ALL CAPS words or sentences
        - No symbols like $$$ or excessive emojis

        2. **Structure & Readability:**
        - Use short paragraphs (2-3 sentences max per paragraph)
        - Natural line breaks between ideas
        - One clear, simple call-to-action at the end
        - NO long, dense blocks of text

        3. **Tone & Language:**
        - Conversational and human - write like a real person, not a marketing robot
        - Professional but warm and approachable
        - No jargon or buzzwords ("synergy", "leverage", "bleeding-edge", "game-changer")
        - Focus on practical benefits, not feature lists
        - Don't repeat the same phrases or keywords multiple times

        4. **Content Guidelines:**
        - Keep numeric values minimal (avoid "50% faster", "10x ROI", "100+ clients")
        - Reference their post naturally in the first 1-2 sentences as an authentic opener
        - Connect their post topic to a relevant pain point or opportunity
        - Position Consultadd's AI solutions as a natural next step, not a hard sell
        - Include a low-pressure, curiosity-driven CTA (e.g., "Would you be open to a brief chat?" not "Schedule a demo now!")

        Return only a JSON object:
        {{
            "subject_line": "Brief, 3-5 word non-clickbait subject",
            "email_body": "The full email body text"
        }}
        """
    
    resp = await llm.ainvoke([
        SystemMessage(content= SYS_PROMPT_POST),
        HumanMessage(content=user_prompt)
    ])

    parsed = safe_parse_json(resp.content)
    if not parsed:
        raise ValueError("Invalid JSON from post LLM")

    return parsed

async def llm_rewrite_email(subject, body, company, designation):
    llm = get_llm()

    SYS_PROMPT_REFINE = """

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
    - Max Word Count: Do NOT exceed 100 words for the entire body.
    - Jargon: Do NOT use clichés, hype, or buzzwords (e.g., "synergy," "disrupt," "cutting-edge").
    - Greeting: The email body must start with a casual greeting (e.g., "Hey," "Quick question," or similar) followed immediately by the hook. Do NOT use the generic "Hi [Name]."

    Email Structure:
    1. Subject Line: Must be catchy, curiosity-driven, and include a touch of humor (e.g., "I think we found where your missing weeks went," "Want a tireless intern who never sleeps?").
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
        Company: {company}
        Recipient Designation: {designation}

        Original Subject: {subject}
        Original Body: {body}

        Rewrite for clarity, persuasion, and personalization.
        """
    
    resp = await llm.ainvoke([
        SystemMessage(content= SYS_PROMPT_REFINE),
        HumanMessage(content=user_prompt)
    ])

    parsed = safe_parse_json(resp.content)
    if not parsed:
        raise ValueError("Invalid JSON from rewrite LLM")

    return parsed

async def _run_enhancer_async(email_generation_result, linkedin_data):
    emails = []
    try:
        posts = json.loads(linkedin_data.get("posts", "[]"))
        experience = json.loads(linkedin_data.get("profile", "[]"))
    except Exception as e:
        print(f"Error parsing LinkedIn data JSON strings: {e}. Defaulting to empty lists.")
        posts = []
        experience = []

    draft_emails = email_generation_result.get("emails", [])
    print(draft_emails)
    company_name = email_generation_result.get("company", "Company")
    designation = email_generation_result.get("designation", "Decision Maker")

    recent_posts = filter_recent_posts(posts)
    career_info = format_career_journey_context(experience, designation)

    print(recent_posts)
    print(career_info)

    if career_info:
        print("DEBUG: Generating Career Journey Email...")
        res = await llm_generate_experience_email(
            career_info["personalization_context"], company_name, designation
        )
        print(f"CLI OUTPUT (Career): {res['subject_line']}")
        emails.append(res)
        
    for post in recent_posts: 
        emails.append(await llm_generate_post_email(
            post["content"], company_name, designation
        ))
    
    for draft in draft_emails: 
        emails.append(await llm_rewrite_email(
            draft["subject_line"], 
            draft["email_body"],
            company_name, 
            designation
        ))
    
    unique = []
    seen = set()
    for e in emails:
        key = (e["subject_line"].lower() + e["email_body"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(e)

    return normalize_output({"emails": unique})

def run_email_enhancer_pipeline(email_generation_result, linkedin_data):
    result =  asyncio.run(
        _run_enhancer_async(email_generation_result, linkedin_data)
    )

    return result




    



