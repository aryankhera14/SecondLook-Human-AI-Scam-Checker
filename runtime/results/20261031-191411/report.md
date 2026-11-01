# SecondLook evaluation report

Model: `openai/gpt-oss-120b`  
Run: 2026-10-31 19:33 · messages: 40 · repeats: 1 · errors: 31

## Idea 1: does asking for context help? (all messages)

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg | Tokens |
|---|---|---|---|---|---|---|
| ask_prompted | 0.90 | 2/12 | 2/12 | 0/8 | 0.05 | 10556 |
| message_only | 0.82 | 7/20 | 7/20 | 0/20 | 0.00 | 12761 |
| secondlook | 0.89 | 2/15 | 2/15 | 1/14 | 0.21 | 158912 |


### Category: context_dependent

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 0.60 | 2/3 | 2/3 | 0/2 | 0.20 |
| message_only | 0.56 | 7/8 | 7/8 | 0/8 | 0.00 |
| secondlook | 0.68 | 2/6 | 2/6 | 1/4 | 0.40 |


### Category: context_fits_scam

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 1.00 | 0/3 | 0/3 | - | 0.00 |
| message_only | 1.00 | 0/6 | 0/6 | - | 0.00 |
| secondlook | 1.00 | 0/4 | 0/4 | - | 0.00 |


### Category: clear_scam

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 1.00 | 0/6 | 0/6 | - | 0.00 |
| message_only | 1.00 | 0/6 | 0/6 | - | 0.00 |
| secondlook | 1.00 | 0/5 | 0/5 | - | 0.00 |


### Category: clear_legit

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 1.00 | - | - | 0/6 | 0.00 |
| message_only | 1.00 | - | - | 0/12 | 0.00 |
| secondlook | 1.00 | - | - | 0/10 | 0.20 |


## Focus scope: delivery & e-commerce, phishing, job (+ everyday genuine messages)

Out-of-scope scams (government impersonation, investment, friend impersonation) are excluded here.

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 0.89 | 2/10 | 2/10 | 0/8 | 0.06 |
| message_only | 0.83 | 6/17 | 6/17 | 0/19 | 0.00 |
| secondlook | 0.91 | 1/12 | 1/12 | 1/13 | 0.24 |


### Scam type: delivery_ecommerce

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 1.00 | 0/3 | 0/3 | 0/1 | 0.00 |
| message_only | 1.00 | 0/4 | 0/4 | 0/2 | 0.00 |
| secondlook | 1.00 | 0/2 | 0/2 | 0/1 | 0.00 |


### Scam type: phishing

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 0.89 | 1/6 | 1/6 | 0/3 | 0.11 |
| message_only | 0.76 | 4/10 | 4/10 | 0/7 | 0.00 |
| secondlook | 0.83 | 1/7 | 1/7 | 1/6 | 0.15 |


### Scam type: job

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 0.50 | 1/1 | 1/1 | 0/1 | 0.00 |
| message_only | 0.60 | 2/3 | 2/3 | 0/2 | 0.00 |
| secondlook | 1.00 | 0/3 | 0/3 | - | 0.67 |


### Scam type: out_of_scope

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 1.00 | 0/2 | 0/2 | - | 0.00 |
| message_only | 0.75 | 1/3 | 1/3 | 0/1 | 0.00 |
| secondlook | 0.75 | 1/3 | 1/3 | 0/1 | 0.00 |


### Scam type: everyday

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 1.00 | - | - | 0/3 | 0.00 |
| message_only | 1.00 | - | - | 0/8 | 0.00 |
| secondlook | 1.00 | - | - | 0/6 | 0.33 |


## Arena: head-to-head on the same messages

| Rank | Condition | Wins | Losses | Ties |
|---|---|---|---|---|
| 1 | secondlook | 5 | 2 | 36 |
| 2 | message_only | 2 | 5 | 42 |
| 3 | ask_prompted | 1 | 1 | 32 |


| Match | Result |
|---|---|
| ask_prompted vs message_only | 1-0 (19 ties) |
| ask_prompted vs secondlook | 0-1 (13 ties) |
| message_only vs secondlook | 2-4 (23 ties) |


## Idea 2: verdict design (same SecondLook judgements, three ways of showing them)

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Friction on harmless legit msgs |
|---|---|---|---|---|---|
| always_cautious | 0.61 | 0/15 | 0/15 | 14/14 | 10/14 |
| binary | 0.90 | 2/15 | 2/15 | 1/14 | 0/14 |
| tiered | 0.89 | 2/15 | 2/15 | 1/14 | 1/14 |


| Policy | Wins | Losses | Ties |
|---|---|---|---|
| binary | 14 | 2 | 42 |
| tiered | 13 | 3 | 42 |
| always_cautious | 4 | 26 | 28 |


### Evidence checks (SecondLook)

Red-flag phrases found verbatim in the message: 26/28  
Advisory quotes found verbatim in the corpus: 27/28  
Verdicts changed by code guardrails: 1/29


## Errors

- ask_prompted CD01a: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'json' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "json", "arguments": {"is_scam": true, "reason": "Unsolicited OTP for a large payment you did not confirm, indicating a potential phishing scam"}}'}}
- ask_prompted CD01b: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'json' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "json", "arguments": {"is_scam": true, "reason": "Unsolicited OTP for a payment you are unsure about indicates a likely phishing attempt"}}'}}
- ask_prompted CD02a: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'json' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "json", "arguments": {"is_scam": false, "reason": "The message is a legitimate Telegram verification code, not a request for personal info or money"}}'}}
- secondlook CD02b: RateLimitError: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01m3pp34sneda8asgb19yp0kfd` service tier `on_demand` on tokens per minute (TPM): Limit 8000, Used 6159, Requested 1849. Please try again in 60ms. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- secondlook CD03a: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'search_advisals' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "search_advisals", "arguments": {\n  "message_type": "government",\n  "query": "login alert phishing government app no link"\n}}'}}
- ask_prompted CD03b: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'json' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "json", "arguments": {"is_scam": false, "reason": "The message is a standard security alert from Singpass, not a request for personal info or money."}}'}}
- ask_prompted CD04a: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'json' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "json", "arguments": {"is_scam": false, "reason": "You applied for the Operations Intern role at Grab, so the recruitment call request is expected and not a scam."}}'}}
- secondlook CD04a: RateLimitError: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01m3pp34sneda8asgb19yp0kfd` service tier `on_demand` on tokens per minute (TPM): Limit 8000, Used 7431, Requested 2389. Please try again in 13.65s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- secondlook CD05a: RateLimitError: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01m3pp34sneda8asgb19yp0kfd` service tier `on_demand` on tokens per minute (TPM): Limit 8000, Used 7173, Requested 1751. Please try again in 6.93s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- ask_prompted CD05b: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'json' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "json", "arguments": {"is_scam": true, "reason": "Unsolicited interview request for a job you didn\'t apply for, indicating a likely scam."}}'}}
- ask_prompted CD06a: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'json' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "json", "arguments": {"is_scam": false, "reason": "The user is indeed expecting a COD parcel, so the message aligns with a legitimate delivery notification"}}'}}
- secondlook CD06a: RateLimitError: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01m3pp34sneda8asgb19yp0kfd` service tier `on_demand` on tokens per minute (TPM): Limit 8000, Used 6198, Requested 1840. Please try again in 285ms. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- ask_prompted CD06b: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'JSON' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "JSON", "arguments": {"is_scam": true, "reason": "Unsolicited COD delivery request while you are not expecting any parcel"}}'}}
- secondlook CD06b: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'json' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "json", "arguments": {\n  "message_type": "delivery",\n  "risky_requests": ["pay_money"],\n  "tier": "likely_scam",\n  "summary": "You received a text claiming a Ninja Van cash‑on‑delivery parcel of SGD\u202f48.90 is arriving today, but you are not expecting any delivery.",\n  "red_flags": [\n    {\n      "phrase": "Your COD parcel (SGD 48.90) will arrive today between 2-6pm. Please prepare exact cash for the driver.",\n      "reason": "Unsolicited cash‑on‑delivery request for a parcel you did not order; common tactic in delivery‑related phishing scams.",\n      "advisory_id": "ecommerce_scams",\n      "advisory_quote": "Asks you to pay additional customs or delivery fees after the deal is confirmed"\n    },\n    {\n      "phrase": "Your COD parcel (SGD 48.90) will arrive today between 2-6pm.",\n      "reason": "Spoofed delivery messages are used to trick recipients; verify with official source.",\n      "advisory_id": "delivery_phishing",\n      "advisory_quote": "Verify the authenticity of the information with the official website or sources."\n    }\n  ],\n  "safe_next_step": "Do not prepare cash or reply. Open the official Ninja Van app or website, or call the official Ninja Van customer service number you find yourself, to confirm whether any delivery is pending.",\n  "context_used": ["expecting_delivery: No"],\n  "memory_suggestions": []\n}}'}}
- ask_prompted CD07a: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'JSON' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "JSON", "arguments": {"is_scam": false, "reason": "User confirms they made the SGD 2,000 transfer, so the message is a legitimate notification"}}'}}
- ask_prompted CD08a: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'json' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "json", "arguments": {"is_scam": false, "reason": "The message only informs about a new phone number without any request for money or personal data, indicating no scam."}}'}}
- ask_prompted CD08b: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'json' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "json", "arguments": {"is_scam": false, "reason": "The message is simply a personal contact update with no request for money or sensitive information, indicating no scam."}}'}}
- secondlook CF01: BadRequestError: Error code: 400 - {'error': {'message': 'Failed to parse tool call arguments as JSON', 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "search_advisories", "arguments": {\n  "message_type": "delivery",\n  parcel: "delivery"\n}"}'}}
- ask_prompted CF04: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'json' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "json", "arguments": {"is_scam": true, "reason": "It promises high earnings for simple tasks and demands a refundable deposit, a classic job scam pattern."}}'}}
- ask_prompted CF05: RateLimitError: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01m3pp34sneda8asgb19yp0kfd` service tier `on_demand` on tokens per minute (TPM): Limit 8000, Used 6851, Requested 1283. Please try again in 1.005s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- secondlook CF05: RateLimitError: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01m3pp34sneda8asgb19yp0kfd` service tier `on_demand` on tokens per minute (TPM): Limit 8000, Used 7373, Requested 1723. Please try again in 8.22s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- ask_prompted CF06: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'json' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "json", "arguments": {"is_scam": true, "reason": "The message asks you to share an OTP with a caller, a classic phishing scam to steal your banking credentials."}}'}}
- secondlook S03: RateLimitError: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01m3pp34sneda8asgb19yp0kfd` service tier `on_demand` on tokens per minute (TPM): Limit 8000, Used 5977, Requested 2615. Please try again in 4.439999999s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- ask_prompted L01: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'json' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "json", "arguments": {"is_scam": true, "reason": "Unsolicited appointment confirmation from a government sender is a common phishing tactic"}}'}}
- ask_prompted L02: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'JSON' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "JSON", "arguments": {"is_scam": false, "reason": "The message is a personal dinner invitation from a known contact, not requesting money or sensitive info."}}'}}
- ask_prompted L04: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'JSON' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "JSON", "arguments": {"is_scam": false, "reason": "The email is a routine academic reminder with no suspicious requests or links"}}'}}
- ask_prompted L05: BadRequestError: Error code: 400 - {'error': {'message': 'Failed to parse tool call arguments as JSON', 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "ask_user", "arguments": {"context_key":"has_account_with_named_org","options":["Yes","No","Not sure"],"question":"Did you take a ride with Grab in the last 24 hours?","}"}'}}
- secondlook L09: BadRequestError: Error code: 400 - {'error': {'message': 'Failed to parse tool call arguments as JSON', 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "json", "arguments": {\n  "message_type": "personal",\n  "risky_requests": ["call_number"],\n  "tier": "verify_safe_route",\n  "summary": "The message from a contact labelled “Dad” asks you to call them. There are no obvious scam signs, but you should verify the sender’s identity before calling.",\n  "red_flags": [],\n  **"safe_next_step**": "Check Dad’s phone number from a trusted source (e.g., your contacts or another messaging app) and call that number, or send a quick message to confirm it’s really him before calling.",\n  "context_used": [],\n  "memory_suggestions": []\n}"}'}}
- ask_prompted L11: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'json' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "json", "arguments": {"is_scam": false, "reason": "The message is a simple meeting time change with no request for money or personal data, indicating no scam."}}'}}
- ask_prompted L12: BadRequestError: Error code: 400 - {'error': {'message': "Tool call validation failed: tool call validation failed: attempted to call tool 'JSON' which was not in request.tools", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '{"name": "JSON", "arguments": {"is_scam": false, "reason": "It\'s a standard promotional offer without any request for personal or financial information"}}'}}
- secondlook L12: RateLimitError: Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01m3pp34sneda8asgb19yp0kfd` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199331, Requested 1731. Please try again in 7m38.784s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}