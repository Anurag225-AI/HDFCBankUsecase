import os
import re
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv

# === Load Environment Variables ===
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# ✅ Explicitly configure Gemini API
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment. Please check your .env file.")
genai.configure(api_key=GOOGLE_API_KEY)

# === Load Credit Card Dataset ===
df = pd.read_csv("HDFC Bank Eligibility Doc(Credit Card Details).csv", encoding="latin1")
df.columns = df.columns.str.strip()

# === Initialize Gemini Model ===
model = genai.GenerativeModel("gemini-1.5-flash")


def recommend_credit_card(user_input: str) -> str:
    """
    Extracts employment type, age, and income from the user message
    and recommends HDFC credit cards based on eligibility criteria.
    """

    # -- Step 1: Intent Classification --
    intent_prompt = f"""
You are a helpful assistant for HDFC Bank credit card eligibility.

Classify the user message as:
- 'eligibility_query' → if it contains info about employment type, age, income
- 'other' → if not about HDFC Credit Card eligibility

User: {user_input}
Reply ONLY with: eligibility_query or other
"""
    intent_response = model.generate_content(intent_prompt)
    intent = intent_response.text.strip().lower()

    if intent != "eligibility_query":
        return (
            "I can help you only with HDFC Credit Card eligibility queries.\n"
            "Please provide your **age**, **employment type** (salaried or self-employed), and **income**."
        )

    # -- Step 2: Extract Fields (employment_type, age, income) --
    extract_prompt = f"""
Extract these fields from the user message:

1. employment_type: 'salaried' or 'self-employed'
2. age: integer
3. income: numeric (monthly for salaried, annual ITR for self-employed)

Convert lakhs/crores into rupees (e.g., '12 lakh' → 1200000).

Return in this format:
employment_type: <value>
age: <value>
income: <value>

User: {user_input}
"""
    extract_response = model.generate_content(extract_prompt)
    extracted = extract_response.text.strip()

    emp_match = re.search(r'employment_type:\s*(.+)', extracted, re.IGNORECASE)
    age_match = re.search(r'age:\s*(\d+)', extracted)
    income_match = re.search(r'income:\s*([\d,\.]+)', extracted)

    if not (emp_match and age_match and income_match):
        return (
            "I couldn't extract all required fields.\n"
            "Please mention your age, employment type (salaried/self-employed), and income clearly."
        )

    # -- Step 3: Parse Extracted Fields --
    employment_type = emp_match.group(1).strip().lower()
    age = int(age_match.group(1).strip())
    income = float(income_match.group(1).replace(",", "").strip())

    # -- Step 4: Filter Based on Employment Type --
    if employment_type == "salaried":
        filtered = df[
            (df['Employment Type Salaried'].str.lower() == 'yes') &
            (df['Salaried Minimum Age'].astype(float) <= age) &
            (df['Salaried Maximum Age'].astype(float) >= age) &
            (df['Minimum Net Monthly Salary for Salaried Person in Rupees'].astype(float) <= income)
        ]
    elif employment_type == "self-employed":
        filtered = df[
            (df['Employment Type Self Employeed'].str.lower() == 'yes') &
            (df['Self Employeed Minimum Age'].astype(float) <= age) &
            (df['Self Employeed Maximum Age'].astype(float) >= age) &
            (df['Minimum ITR for Self Employeed Person per annum in Rupees'].astype(float) <= income)
        ]
    else:
        return "Invalid employment type detected. Please specify as either 'salaried' or 'self-employed'."

    # -- Step 5: Respond Based on Filter Result --
    if filtered.empty:
        return "Sorry! You are not eligible for any HDFC credit cards based on the provided details."

    # Eligible Cards List
    cards = filtered["Card Name"].dropna().unique().tolist()
    card_list = "\n".join(f"- {card}" for card in cards)
    card_list_html = "<br>".join(f"• {card}" for card in cards)
    return f"Based on your profile, you're eligible for the following HDFC Credit Cards:<br><br>{card_list_html}"
