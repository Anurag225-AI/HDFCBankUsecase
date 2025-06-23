import requests
import re
import datetime
from credit_logic import recommend_credit_card

state = {
    "step": "start",
    "retries": 0,
    "data": {}
}

def reset_flow():
    state["step"] = "start"
    state["retries"] = 0
    state["data"] = {}

def calculate_age(dob_str):
    dob = datetime.datetime.strptime(dob_str, "%d-%m-%Y").date()
    today = datetime.date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

def process_credit_flow(user_input: str):
    user_input = user_input.strip()

    if state["step"] == "start":
        state["step"] = "phone"
        return "Please enter your 10-digit mobile number to check your profile.", "phone"

    elif state["step"] == "phone":
        if not re.match(r'^[789]\d{9}$', user_input):
            return "Please enter a valid Indian 10-digit phone number.", "phone"
        state["data"]["phone"] = user_input
        res = requests.get(f"https://hdfcbankusecase.onrender.com/profile?phone={user_input}")
        if res.status_code == 404:
            reset_flow()
            return ("Dear User, We are unable to find your profile with your phone number in our HDFC Database. "
    'Please feel free to visit our website for credit card related services: '
    '<a href="https://www.hdfcbank.com/" target="_blank">https://www.hdfcbank.com/</a>',
    "done")
        state["step"] = "pan"
        return "✅ Phone verified. Now, please enter your PAN number (e.g., ABCDE1234F).", "pan"

    elif state["step"] == "pan":
        if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', user_input):
            state["retries"] += 1
            if state["retries"] >= 3:
                reset_flow()
                return ("Dear User, You have entered the wrong PAN number. "
    'Please feel free to visit our website for credit card related services: '
    '<a href="https://www.hdfcbank.com/" target="_blank">https://www.hdfcbank.com/</a>',
    "done")
            return "Dear User, You have provided PAN number in invalid format. Please provide your PAN Number again (e.g., ABCDE1234F).", "pan"
        state["data"]["pan"] = user_input
        state["step"] = "dob"
        state["retries"] = 0
        return "Thanks. Now enter your Date of Birth (format: DD-MM-YYYY).", "dob"

    elif state["step"] == "dob":
        if not re.match(r'^\d{2}-\d{2}-\d{4}$', user_input):
            state["retries"] += 1
            if state["retries"] >= 3:
                reset_flow()
                return ("Dear User, You have entered the wrong date of birth number. "
    'Please feel free to visit our website for credit card related services: '
    '<a href="https://www.hdfcbank.com/" target="_blank">https://www.hdfcbank.com/</a>',
    "done")
            return "Dear User, You have provided Date of Birth in invalid format. Please provide your DOB in DD-MM-YYYY format.", "dob"
        try:
            dob_obj = datetime.datetime.strptime(user_input, "%d-%m-%Y")
            if dob_obj.date() > datetime.date.today():
                return "Date of birth cannot be in the future.", "dob"
        except:
            return "Invalid date. Please re-enter in DD-MM-YYYY format.", "dob"
        state["data"]["dob"] = user_input
        pan = state["data"]["pan"]
        dob = user_input
        res = requests.get(f"https://hdfcbankusecase.onrender.com/profile?pan={pan}&dob={dob}")
        if res.status_code == 404:
            reset_flow()
            return (
    'Dear User, We are unable to fetch your KYC details with your PAN Number and DOB. '
    'Please check your KYC status on NPCI: <a href="https://www.npci.org.in/" target="_blank">https://www.npci.org.in/</a> '
    'or feel free to visit the HDFC website: <a href="https://www.hdfcbank.com/" target="_blank">https://www.hdfcbank.com/</a>',
    "done")
        kyc_data = res.json()
        if isinstance(kyc_data, list) and kyc_data:
            profile = kyc_data[0]
        else:
            reset_flow()
            return (
    'Dear User, We are unable to fetch your KYC details with your PAN Number and DOB. '
    'Please check your KYC status on NPCI: <a href="https://www.npci.org.in/" target="_blank">https://www.npci.org.in/</a> '
    'or feel free to visit the HDFC website: <a href="https://www.hdfcbank.com/" target="_blank">https://www.hdfcbank.com/</a>',
    "done"
)
        state["data"]["kyc"] = profile
        state["step"] = "confirm"
        return f"""Here are your details:<br><br>
<b>Name:</b> {profile['FULLNAME']}<br>
<b>DOB:</b> {profile['DOB']}<br>
<b>PAN:</b> {profile['PAN']}<br>
<b>Address:</b> {profile['Address']}<br>
<b>Mobile:</b> +{profile['MOB_CODE']} {profile['MOB_NUM']}<br>
<b>Email:</b> {profile['EMAIL_ID']}<br>
<b>Age:</b> {calculate_age(profile['DOB'])}<br><br>
Please confirm if these details are correct (Yes/No).
""", "confirm"


    elif state["step"] == "confirm":
        if user_input.lower() == "yes":
            state["step"] = "employment"
            return "Great! Please select your employment type:", "employment"
        else:
            reset_flow()
            return ("Dear User, We are unable to find the data."
    'Please feel free to visit our website for credit card related services: '
    '<a href="https://www.hdfcbank.com/" target="_blank">https://www.hdfcbank.com/</a>',
    "done")

    elif state["step"] == "employment":
        emp = user_input.lower()
        if "salaried" in emp:
            state["data"]["employment_type"] = "salaried"
            state["step"] = "salary"
            return "Please enter your Net Monthly Salary (in INR).", "salary"
        elif "self" in emp:
            state["data"]["employment_type"] = "self-employed"
            state["step"] = "salary"
            return "Please enter your Annual ITR amount (in INR).", "salary"
        else:
            return "Invalid input. Please type or select: Salaried or Self-Employed.", "employment"

    elif state["step"] == "salary":
        try:
            cleaned_input = re.sub(r"[^\d.]", "", user_input.replace(",", ""))
            if not cleaned_input or not re.match(r"^\d+(\.\d+)?$", cleaned_input):
                return "❌ Please enter a valid numeric value for salary.", "salary"
            income = float(cleaned_input)
            state["data"]["income"] = income
            user_info = f"I am {state['data']['employment_type']}, {calculate_age(state['data']['dob'])}, earning {income}"
            result = recommend_credit_card(user_info)
            reset_flow()
            return result, "done"
        except Exception as e:
            return f"⚠️ Error: {str(e)}", "salary"
