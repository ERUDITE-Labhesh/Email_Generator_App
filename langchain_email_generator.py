import os
import json
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from dotenv import load_dotenv

import textwrap

from langchain_gap_analyser import run_full_pipeline

load_dotenv()


def generate_email_and_subject(data):

    MODEL_NAME = os.getenv("OPENROUTER_MODEL", "x-ai/grok-4-fast")
    BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    API_KEY = os.getenv("OPENROUTER_API_KEY")

    if not API_KEY:
        raise ValueError("OPENROUTER_API_KEY not set in environment variables")
    
    llm = ChatOpenAI(
        model=MODEL_NAME,
        openai_api_base=BASE_URL,
        openai_api_key=API_KEY,
        temperature=0.4,
        streaming=True
        
    )

    SYSTEM_PROMPT = """
                        You are an expert copywriter and sales strategist generating highly personalized cold emails for Consultadd, 
                        a custom AI solutions company for SMBs and enterprises. Your company has the USP of rapidly deploying 
                        tailor-made solutions for unique challenges of a company.

                        Your emails must be crafted to appeal respectfully and relevantly to individuals at specific companies, taking into account their role, department, industry, and business needs while positioning Consultadd as their ideal AI transformation partner.
                        While you are getting inputs to use a particular gap, follow the guidelines below while drafting the first email
                        Keep the email concise with a character limit of 100 words or 250 characters max. Ensures that message is impactful, making it personalised to the person and the company he is working for.
                        Avoid jargon and buzzwords and use simplified language.
                        Begin with a personalized opening referencing company news, recent activity, or an industry challenge relevant to the prospect.
                        After the opening, briefly address a potential gap very quickly, also touching upon a probable solution without giving away much information but generating curiosity to know further.
                        Whenever mentioning Consultadd, clearly communicate the brand's central value proposition: helping companies with tailor made custom AI solutions that unlock efficiency, rapidly automate what matters, and fit their specific stage in the AI journey.
                        Close with a clear, low-pressure CTA inviting a short meeting or a discovery call. However, it should drive curiosity. Don't make it an open ended question around whether they are interested, because you don't want no for an answer.
                        Maintain an empowering, consultative, and approachable tone throughout.


                        EMAIL GUIDELINES:
                            - Keep email concise: 100 words or 250 characters max
                            - Avoid jargon and buzzwords, use simplified language
                            - Begin with personalized opening referencing company or industry challenge
                            - Briefly address a potential gap and hint at solution without revealing too much (generate curiosity)
                            - Clearly communicate Consultadd's value: tailor-made custom AI solutions that unlock efficiency, 
                            rapidly automate what matters, and fit their specific stage in the AI journey
                            - Close with clear, low-pressure CTA inviting short meeting or discovery call (drive curiosity, avoid open-ended questions)
                            - Maintain empowering, consultative, and approachable tone
    
                        SPAM-FREE REQUIREMENTS:
                            - Avoid spammy keywords tied to scams or aggressive sales tactics
                            - Use max 1 exclamation mark if needed
                            - No excessive punctuation or ALL CAPS
                            - No overuse of links or suspicious URLs
                            - Use short paragraphs with clear structure
                            - Focus on value/benefits, not feature dumps
                            - Conversational, professional, human-like tone
                            - Include email signature at end
                            - Avoid excessive numeric values
                            - Don't keyword-stuff or repeat phrases
                            - IMPORTANT: Do NOT add any email signature, sender name, role, or contact information. End the email right after the CTA.

                            
                        SUBJECT LINE GUIDELINES:
                            - Create catchy, curiosity-driven subject line (6-8 words max)
                            - Generate a Marketing Hook
                            - Personalize with company name when possible
                            - Avoid spam triggers (FREE, ACT NOW, !!!, etc.)
                            - Make it relevant to their specific pain point
                            
                        Output must be in JSON format with keys: "subject_line" and "email_body"
                    """
    emails_output = []

    company_name = data.get("company", "")
    about_company = data.get("about", "")
    ai_gap_items = data.get("ai_gap_analysis", [])

    for gap_item in ai_gap_items:
        ai_solution = gap_item.get("ai solution", "")
        gap_analysis = gap_item.get("gap_analysis", "")
        pain_points = gap_item.get("pain_points", [])

        user_prompt = f"""
        Generate a personalized cold email for the following context:
        
        COMPANY INFORMATION:
        Company Name: {company_name}
        
        AI SOLUTION OPPORTUNITY:
        Solution: {ai_solution}
        
        GAP ANALYSIS:
        {gap_analysis}
        
        KEY PAIN POINTS:
        {chr(15).join(f"- {pp}" for pp in pain_points[:2])}
    
        Generate:
        1. A catchy, personalized subject line (6-8 words, no spam triggers)
        2. A concise email body (max 100 words/250 characters) following all guidelines
        
        The email should:
        - Reference {company_name} specifically
        - Touch on their {gap_analysis} gap/challenge without being too detailed
        - Hint at how Consultadd's custom AI solutions can help
        - End with a curiosity-driven CTA (not an open-ended question)
        - Add a Hook into an email which will make recipent reply
        
        Output JSON format:
        {{
            "subject_line": "...",
            "email_body": "..."
        }}
        """

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt.strip())
        ]

        response_text = llm.invoke(messages).content.strip()

        try:
            parsed = json.loads(response_text)
            parsed["email_body"] = parsed["email_body"].replace("\n", " ").strip()

        except Exception:
            parsed = {
                "subject_line": "Quick AI Insight for You",
                "email_body": response_text.replace("\n", " ").strip()
            }

        emails_output.append(parsed)
    
    return {
        "company": company_name,
        "emails": emails_output
    }

def run_email_generation_pipeline(analysis_id):
    enriched_data = run_full_pipeline(analysis_id)
    result = generate_email_and_subject(enriched_data)
    print(result)
    return result





   