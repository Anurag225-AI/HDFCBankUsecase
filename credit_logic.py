# credit_logic.py

import google.generativeai as genai
import pandas as pd
import re

# === CONFIG ===
GEMINI_API_KEY = "AIzaSyBJLgcXQBIjSjAyU2nzjCHeQ1V7GLxeCoo"
genai.configure(api_key=GEMINI_API_KEY)

# === LOAD CSV ===
df = pd.read_csv("HDFC Bank Eligibility Doc(Credit Card Details).csv", encoding="latin1")
df.columns = df.columns.str.strip()

# === GEMINI MODEL ===
model = genai.GenerativeModel("gemini-1.5-pro")

def recommend_credit_card(user_input: str) -> str:
    """
    Extracts employment type, age, income from the user's sentence
    and filters the credit card CSV to recommend matching cards.
    """

    # Intent Classification Prompt
    intent_prompt = f"""
You are a helpful assistant for HDFC Bank credit card eligibility.

Classify user message as:
- 'eligibility_query' → if it contains info about employment type, age, income
- 'other' → if not about HDFC Credit Card eligibility

User: {user_input}
Reply ONLY with: eligibility_query or other
"""

    intent_response = model.generate_content(intent_prompt)
    intent = intent_response.text.strip().lower()

    if intent != "eligibility_query":
        return "❌ I can help you only with HDFC Credit Card eligibility queries. Please provide your age, employment type, and income."

    # Extraction Prompt
    extract_prompt = f"""
Extract these fields from user message:

1. employment_type: 'salaried' or 'self-employed'
2. age: integer
3. income: numeric (in rupees per month for salaried, per annum ITR for self-employed)

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
        return "❌ Could not extract required details. Please provide age, employment type, and income clearly."

    # Extracted Values
    employment_type = emp_match.group(1).strip().lower()
    age = int(age_match.group(1).strip())
    income_str = income_match.group(1).replace(",", "").strip()
    income = float(income_str)

    # Filter cards
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
        return "❌ Invalid employment type detected."

    if filtered.empty:
        return "❌ Sorry, you are not eligible for any credit cards based on your details."

    # Return eligible cards
    cards = filtered["Card Name"].dropna().unique().tolist()
    return "🎉 Based on your profile, you're eligible for the following HDFC Credit Cards:\n\n" + "\n".join(f"- {card}" for card in cards)
