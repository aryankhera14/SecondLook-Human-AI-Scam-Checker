"""Builds data/messages.json. Messages are written by the project team to follow scam
patterns documented in the advisories under data/advisories/ (no real victims' messages).
Organisation names appear only as the impersonated party, as in the official advisories."""
import json, pathlib

def m(id, text, label, category, context, channel="SMS", sender="", pair=None, note=""):
    return dict(id=id, text=text, channel=channel, sender=sender, label=label,
                category=category, context=context, pair_id=pair, note=note)

msgs = []
# ---- 8 context-dependent pairs: identical text, label decided only by the user's context ----
pairs = [
 ("otp_payment", "SMS", "DBS",
  "DBS: OTP 482913 is for your SGD 1,240.00 card payment to SHOPEE SG. Never share this OTP with anyone.",
  "requested_otp_or_login", "Genuine only if the user is making this payment; otherwise someone is using their card."),
 ("app_code", "SMS", "Telegram",
  "Telegram code: 55123. Do not give this code to anyone, even if they say they are from Telegram!",
  "requested_otp_or_login", "Unrequested login code = account takeover attempt."),
 ("singpass_login", "SMS", "gov.sg",
  "Singpass: You logged in to Singpass on a new device (iPhone) at 10:42pm on 03 Oct. If this was not you, reset your password in the Singpass app.",
  "requested_otp_or_login", "Genuine alert either way, but if not the user, the account is compromised."),
 ("recruiter_call", "WhatsApp", "+65 8123 4471",
  "Hi, this is Jess from the recruitment team at Grab. We received your application for the Operations Intern role. Are you free for a 15-min call tomorrow at 3pm?",
  "applied_for_job", "Unsolicited recruiter contact is a common job-scam opener."),
 ("interview_slot", "Email", "careers@kellyservices.sg",
  "Thank you for applying for the Part-time Data Entry Assistant role. Please reply with your preferred interview slot this week (Mon-Fri, 10am-5pm).",
  "applied_for_job", "Only genuine if the user applied."),
 ("cod_delivery", "SMS", "+65 9022 5813",
  "Ninja Van: Your COD parcel (SGD 48.90) will arrive today between 2-6pm. Please prepare exact cash for the driver.",
  "expecting_delivery", "Unordered cash-on-delivery parcels are a known e-commerce scam."),
 ("transfer_alert", "SMS", "OCBC",
  "OCBC: You have transferred SGD 2,000.00 to TAN K M on 03 Oct 21:14. If you did not make this transfer, call the number on the back of your card.",
  "initiated_payment_or_refund", "If not initiated by the user, it is fraud in progress."),
 ("new_number", "WhatsApp", "+65 8890 1123",
  "Hey it's Wei Ming, this is my new number. Save it ya!",
  "knows_sender_personally", "Genuine only if the user knows this person changed number; impersonation opener otherwise."),
]
# For a payment OTP or a transfer alert, "did you request this code?" and "did you make this payment?"
# are the same question, so the context card answers both (added after the first live pilot run,
# where the agent asked the second form and the simulated user could only say "Not sure").
EQUIVALENT_KEYS = {"otp_payment": "initiated_payment_or_refund", "transfer_alert": "requested_otp_or_login"}
for i, (pid, ch, snd, text, key, note) in enumerate(pairs, 1):
    keys = [key] + ([EQUIVALENT_KEYS[pid]] if pid in EQUIVALENT_KEYS else [])
    msgs.append(m(f"CD{i:02d}a", text, "legit", "context_dependent", {k: True for k in keys}, ch, snd, pid, note))
    msgs.append(m(f"CD{i:02d}b", text, "scam", "context_dependent", {k: False for k in keys}, ch, snd, pid, note))

# ---- context fits the scam: the user's real situation matches the scam story ----
fits = [
 ("SingPost: We could not deliver your parcel due to an incomplete address. Update your details within 24h: singpost-redeliver.com/sg", "SMS", "+65 8231 0094", {"expecting_delivery": True}),
 ("Customs: Your parcel is held pending a SGD 2.80 customs fee. Pay now to avoid return: sg-parcel-fee.top/pay", "SMS", "+60 11-2384 9921", {"expecting_delivery": True}),
 ("Hi! I want to buy your camera. I have paid via Carousell Protection. Click to receive your payment: carousell-payout.co/claim", "WhatsApp", "+65 8012 7733", {"made_listing_selling_item": True}),
 ("Congrats! You are shortlisted for the remote job. Earn $300/day liking posts. Pay a $50 refundable deposit to start today.", "Telegram", "@hr_rina_sg", {"applied_for_job": True}),
 ("Shopee: Your refund of $35.90 failed. Log in here to re-submit your bank details: shopee-refund-sg.com", "SMS", "+65 9301 2268", {"initiated_payment_or_refund": True}),
 ("DBS: Your OTP is 771204. A DBS officer will call you to verify it. Please share the OTP when asked.", "SMS", "+65 8412 5567", {"requested_otp_or_login": True}),
]
for i, (text, ch, snd, ctx) in enumerate(fits, 1):
    msgs.append(m(f"CF{i:02d}", text, "scam", "context_fits_scam", ctx, ch, snd))

# ---- clear scams ----
scams = [
 ("DBS: Your account has been locked due to suspicious activity. Verify immediately at dbs-secure-login.com to avoid suspension.", "SMS", "+65 8723 1190", {"has_account_with_named_org": True}),
 ("This is an officer from the Ministry of Health. Your NRIC was used in a money laundering case. You must transfer your savings to a safe account for investigation.", "Phone/WhatsApp", "+65 6123 0000", {}),
 ("Hi, I accidentally sent my OTP code to your number. Can you forward it to me? Very urgent pls", "WhatsApp", "+65 9112 4408", {"knows_sender_personally": False}),
 ("IRAS: You are eligible for a tax refund of $612.40. Claim within 48 hours: iras-refund.gov-sg.co", "SMS", "+65 8890 2276", {}),
 ("Join our VIP stock group! Guaranteed 30% weekly returns. Limited slots, transfer to our investment manager today.", "WhatsApp", "+852 5123 9981", {}),
 ("Netflix: Your payment failed and your membership will be suspended today. Update your card: netflix-billing-sg.com", "SMS", "+65 8199 0032", {"has_account_with_named_org": True}),
]
for i, (text, ch, snd, ctx) in enumerate(scams, 1):
    msgs.append(m(f"S{i:02d}", text, "scam", "clear_scam", ctx, ch, snd))

# ---- clear legitimate (some contain a link or phone number on purpose) ----
legit = [
 ("Your HDB appointment is confirmed for 12 Oct, 10:00am at HDB Hub. No reply is needed.", "SMS", "gov.sg", {}),
 ("Dinner at 7 at the usual place? Bring the board game!", "WhatsApp", "Mum (saved contact)", {"knows_sender_personally": True}),
 ("Shopee: Your order 241003XYZ has been shipped. Track it in the Shopee app.", "SMS", "Shopee", {"expecting_delivery": True}),
 ("Reminder: CS619 project proposal is due tonight at 11:59pm on eLearn.", "Email", "course-noreply@university.edu.sg", {}),
 ("Thanks for riding with Grab. SGD 14.20 was charged to your Visa ending 1234.", "Email", "no-reply@grab.com", {"initiated_payment_or_refund": True}),
 ("You received SGD 20.00 from TAN WEI via PayNow. Note: dinner", "SMS", "DBS", {"knows_sender_personally": True}),
 ("Smile Dental: Reminder of your appointment on 8 Oct, 2:30pm. Call 6123 4567 to reschedule.", "SMS", "SmileDental", {}),
 ("NLB: Your loan 'Thinking, Fast and Slow' is due on 10 Oct. Renew at nlb.gov.sg or in the NLB Mobile app.", "SMS", "NLB", {}),
 ("Reached home already. Call me when you're free.", "WhatsApp", "Dad (saved contact)", {"knows_sender_personally": True}),
 ("Singtel: Your bill of $45.80 for Sep is ready. View it in the My Singtel app.", "SMS", "Singtel", {"has_account_with_named_org": True}),
 ("Project meeting moved to 3pm, same room. See you!", "Telegram", "CS619 group", {"knows_sender_personally": True}),
 ("UNIQLO: 20% off all outerwear this weekend in stores. Reply STOP to opt out.", "SMS", "UNIQLO", {}),
]
for i, (text, ch, snd, ctx) in enumerate(legit, 1):
    msgs.append(m(f"L{i:02d}", text, "legit", "clear_legit", ctx, ch, snd))

# ---- topic tags (added after the professor's feedback; labels and context are unchanged) ----
# Focus types: delivery_ecommerce, phishing (bank / OTP / login), job. Three scams fall outside
# them (out_of_scope) and everyday genuine messages are tagged everyday (they test false alarms).
TOPIC = {
    "otp_payment": "phishing", "app_code": "phishing", "singpass_login": "phishing", "transfer_alert": "phishing",
    "recruiter_call": "job", "interview_slot": "job", "cod_delivery": "delivery_ecommerce", "new_number": "out_of_scope",
    "CF01": "delivery_ecommerce", "CF02": "delivery_ecommerce", "CF03": "delivery_ecommerce", "CF04": "job",
    "CF05": "phishing", "CF06": "phishing",
    "S01": "phishing", "S02": "out_of_scope", "S03": "phishing", "S04": "phishing", "S05": "out_of_scope", "S06": "phishing",
    "L01": "everyday", "L02": "everyday", "L03": "delivery_ecommerce", "L04": "everyday", "L05": "phishing",
    "L06": "phishing", "L07": "everyday", "L08": "everyday", "L09": "everyday", "L10": "phishing",
    "L11": "everyday", "L12": "everyday",
}
for x in msgs:
    x["topic"] = TOPIC[x["pair_id"] or x["id"]]

assert len(msgs) == 40, len(msgs)
pathlib.Path(__file__).with_name("messages.json").write_text(json.dumps(msgs, indent=2))
focus = [x for x in msgs if x["label"] == "scam" and x["topic"] not in ("out_of_scope", "everyday")]
print(f"{len(focus)}/20 scams are in the three focus types")
print(len(msgs), "messages;", sum(x["label"] == "scam" for x in msgs), "scam /", sum(x["label"] == "legit" for x in msgs), "legit")
