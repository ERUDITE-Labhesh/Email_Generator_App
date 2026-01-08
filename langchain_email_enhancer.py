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
                f"The recipient is the {designation}. Their professional spans approximately {total_experience: .0f} years, with key roles including \n"
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
    model_name = os.getenv("OPENROUTER_MODEL", "x-ai/grok-4-fast")
    return ChatOpenAI(
        model=model_name,
        openai_api_key=API_KEY,
        openai_api_base=BASE_URL,
        temperature=0.3
    )

async def llm_generate_experience_email(context, company, designation): 
    llm = get_llm()

    SYS_PROMPT_CAREER = """

    You are refining an existing cold email draft that already addresses a relevant company and role-specific problem.
    Personalize this email using the recipient’s career journey and experience patterns, prioritizing:
    Long-term exposure to a specific industry or function
    Repeated responsibility across roles
    Years spent operating, scaling, or owning similar problems
    Founder/operator intuition gained over time

    Your email must naturally reference either:
    A past role or long-term experience pattern
    A specific responsibility across roles

    Do not explicitly reference job titles, companies, or say “I noticed your background at X.”
    Instead:
    Open with a quiet, intuitive hook that signals deep understanding of what someone with this kind of experience thinks about
    Use phrasing like “After years in…”, “Anyone who’s spent time in…”, or “Running this long enough teaches you…”
    Transition quickly into a specific, recurring tension relevant to their role and department

    Maintain:
    Under 50 words
    Confident, peer-to-peer tone
    No sales language, no meeting asks
    End with a curiosity-driven, reflective question
    Maintain a professional, confident, outcome-focused tone.
    End with a low-pressure, curiosity-driven CTA.
    Also no greetings or signatures at end of emails.

    The goal is for the recipient to think:
    “This person understands my world, and they’re not pitching me.”

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

        ### INSTRUCTIONS:
        - Start the email with the role-truth question above
        - Reference the LinkedIn post naturally AFTER the opening question
        - Keep the email under 100 words. 
        - No pitch language

        ### CRITICAL CONSTRAINTS (Spam Prevention & Human Tone):
        1. NO SPAM TRIGGERS: Do not use aggressive sales words (e.g., "Guaranteed," "Free," "100%," "Scale," "Revolutionary," "Optimize," "Unlock").
        2. PUNCTUATION: Use a maximum of ONE (!) exclamation mark in the entire email. No ALL CAPS words.
        3. NUMERICS: Avoid heavy use of percentages or large dollar signs. Focus on qualitative value.
        4. TONE: Professional yet conversational. Write like a colleague, not a vendor. Avoid AI cliches like "Hope you're having a productive week."
        5. STRUCTURE: 
        - Use a clear, benefit-driven bulleted list (2-3 points) if explaining value.
        - Include a low-friction, one-sentence Call to Action. 
        6. Max Word Count: Do NOT exceed 100 words for the entire body.

        ### OUTPUT FORMAT:
        Return ONLY a valid JSON object:
        {{
            "subject_line": "A concise, non-promotional subject line (3-6 words) having a eye catchy hook",
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
    The recipient is the {designation}. They recently shared: "{post_content}..."

    You are refining an existing cold email draft that already addresses a relevant company- and role-specific problem.
    Personalize this email using the recipient’s recent LinkedIn post, comment, or update.
    The email must:
    Open by directly referencing something they posted, shared, or mentioned
    Use the post as a lens, not a compliment
    Draw out a natural implication, tension, or question from what they shared

    Approved opening styles:
    “Saw your post about…”
    “Your update on ___ caught my eye…”
    “When you mentioned ___, it made me think…”

    After the opening:
    Connect their post to a broader pattern seen in similar teams or roles
    Avoid pitching, explaining AI, or introducing your company too early
    If AI is mentioned, it should appear as a quiet pattern others are using, not a solution pitch

    Maintain:
    Under 50 words
    Conversational, observant tone
    No flattery, no “great post” filler
    End with a light, open-ended question that invites reflection or comparison

    The goal is for the recipient to feel:
    “This person actually read what I shared — and thought about it.”

    Your email must naturally reference either:
    A recent LinkedIn post
    A topic they frequently discuss
    A career theme (e.g., “scaling CS teams,” “multi-vendor ops,” “pipeline efficiency,” etc.)

    The email must start with a personalized observation based on their LinkedIn experience or recent post activity.

    Where Consultadd Comes In
    After the opening sentence(s), and only then, introduce Consultadd’s capability as a soft bridge, not a pitch:
    Approved transitions:
    “We’ve been seeing teams solve this with agentic AI…”
    “We recently helped a team automate this without changing their systems…”
    “This is where AI agents tend to remove 10–20 hrs/week for teams like yours…”
    This keeps the email recipient-first, insight-led, and avoids hardsell energy.

    Tone
    Confident, professional, conversational
    Zero fluff, zero corporate jargon
    Short sentences
    No negativity, no fear-based wording
    Outcome-focused

    Role-specific relevance:
    Maintain the same consistency in relevance as earlier for their roles. Adapt benefits, pain points, and CTA depending on role and department.

    Value Proposition
    Highlight that Consultadd builds:
    Custom AI agents 
    Adaptive and intelligent agents 
    Tailored for unique business needs of small businesses 
    Automating repetitive, manual tasks
    Increase productivity 
    Unlock faster growth and business value

    CTA
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

        Write a short, personalized cold email (max 100 words / 250 characters) that naturally references their recent LinkedIn post as the opener. 
        Your goal is to write a high-conversion, short cold email. The post reference should feel like a genuine conversation starter, not a forced compliment or not a marketing bot.

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
    Use a “poking the bear” technique (light contradiction, curiosity, pattern-interrupt — never rude). 

    Your job is to generate a single cold outreach email based on the following information the user provides:
    * The company sending the email (Your client).
    * The company receiving the email (The prospect).
    * The core value proposition / problem solved.

    Tone and Style Requirements:
    - Humor: Light, playful, and confidence-driven. The humor must feel natural and avoid being juvenile or forced.
    - Confidence: Confident, assertive, conversational, and outcome-focused. Avoid sounding salesy, desperate, or robotic.
    - Clarity: Short, punchy, and highly skimmable.
    - Sound human, casual, and natural

    CTA:
    End with a short, curiosity-based question that keeps the conversation going.
    Avoid any reference to meetings, calls, demos, time, or scheduling.
    The CTA should feel like a natural continuation of the email — a prompt to share their experience.

    Approved CTA styles:
    Curiosity loop (“Wondering if that’s familiar on your side.”)
    Pattern-check (“Still happening on your end?”)
    Open-ended reflection (“How does that show up for you these days?”)
    Light peer exchange (“Open to comparing notes?”)
    Or allow the final question in the email body to be the CTA.

    Strict Constraints:
    - Email Count: Generate 1 email only.
    - Max Word Count: Do NOT exceed 100 words for the entire body.
    - Jargon: Do NOT use clichés, hype, or buzzwords (e.g., "synergy," "disrupt," "cutting-edge").
    - Email should followed immediately by the hook. 

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
    You are writing a cold outreach email using the system instructions above.
    Use the following inputs as context and inspiration.
    Do not copy them verbatim — reinterpret, sharpen, and improve them.

    Company: {company}
    Recipient Designation: {designation}

    Original Subject: {subject}
    Original Body: {body}

    Instructions:
    Extract the core value proposition, pain point, and implied benefit from the original subject and body.
    Improve clarity, confidence, and humor while keeping it professional.
    Add light, clever “poking the bear” energy (pattern interrupt or curiosity) Talk more around their competitors. 
    Keep it short, punchy, and skimmable.
    Follow all system prompt constraints strictly.
    Also no greetings or signature at end of emails.
    Output only the final email in the required JSON format.
    Generate the email now.
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

    print(company_name)
    print(designation)
    print(recent_posts)
    print(career_info)

    if career_info:
        print("DEBUG: Generating Career Journey Email...")
        res = await llm_generate_experience_email(
            career_info["personalization_context"], company_name, designation
        )
        emails.append(res)
        
    for post in recent_posts: 
        print("DEBUG: Generating Post Based Email...")
        res = await llm_generate_post_email(
            post["content"], company_name, designation
        )
        emails.append(res)

    for draft in draft_emails: 
        print("DEBUG: Generating Enhance Email...")
        res = await llm_rewrite_email(
            draft["subject_line"], 
            draft["email_body"],
            company_name, 
            designation
        )
        emails.append(res)

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




    



