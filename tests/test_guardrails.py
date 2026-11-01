from secondlook.guardrails import apply_policy, check_red_flags, detect_risky_requests


def base(**kw):
    v = {"message_type": "delivery", "risky_requests": [], "tier": "looks_fine", "summary": "s",
         "red_flags": [], "safe_next_step": "", "context_used": [], "memory_suggestions": []}
    v.update(kw)
    return v


def test_negated_code_warning_is_not_a_request():
    assert "share_code_or_password" not in detect_risky_requests("OTP 1234. Never share this OTP with anyone.")


def test_forward_code_is_a_request():
    assert "share_code_or_password" in detect_risky_requests("I sent my OTP code to you. Can you forward it to me?")


def test_receipt_is_not_a_payment_request():
    assert detect_risky_requests("Thanks for riding. SGD 14.20 was charged to your Visa.") == set()


def test_looks_fine_is_raised_when_message_has_a_link():
    v, notes = apply_policy(base(), "Update your address: singpost-redeliver.com/sg")
    assert v["tier"] == "verify_safe_route" and notes


def test_context_never_unlocks_the_message_link():
    text = "Pay the fee here: sg-parcel-fee.top/pay"
    v, notes = apply_policy(base(tier="verify_safe_route", safe_next_step="Pay at sg-parcel-fee.top/pay"), text)
    assert "sg-parcel-fee.top" not in v["safe_next_step"]
    assert any("own link" in n for n in notes)


def test_likely_scam_gets_report_line():
    v, _ = apply_policy(base(tier="likely_scam", safe_next_step="Delete it."), "Click dbs-secure-login.com now")
    assert "1799" in v["safe_next_step"]


def test_looks_fine_kept_for_harmless_message():
    v, notes = apply_policy(base(), "Dinner at 7 at the usual place?")
    assert v["tier"] == "looks_fine" and not notes


def test_fabricated_phrase_and_quote_are_caught():
    rf = [{"phrase": "click here now", "reason": "r", "advisory_id": "phishing_scams",
           "advisory_quote": "Banks will always call you to confirm."}]
    checked = check_red_flags(rf, "Your parcel is waiting.")[0]
    assert not checked["phrase_verified"] and not checked["quote_verified"]


def test_real_phrase_and_quote_verify():
    rf = [{"phrase": "Spoofed", "reason": "r", "advisory_id": "phishing_scams",
           "advisory_quote": "Spoofed website addresses"}]
    checked = check_red_flags(rf, "spoofed site")[0]
    assert checked["phrase_verified"] and checked["quote_verified"]
