# SecondLook evaluation report

Model: `openai/gpt-oss-120b`  
Run: 2026-11-01 01:04 · repeats: 1 · errors: 0  
Valid checks per condition: ask_prompted: 40 · message_only: 40 · secondlook: 40  
**All tables below use the 40 messages that every condition answered (matched comparison).** Answers recovered from a malformed final tool call: 9.

## Idea 1: does asking for context help? (all messages)

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg | Tokens |
|---|---|---|---|---|---|---|
| ask_prompted | 0.85 | 5/20 | 5/20 | 1/20 | 0.12 | 16152 |
| message_only | 0.80 | 7/20 | 7/20 | 1/20 | 0.00 | 9115 |
| secondlook | 0.85 | 5/20 | 3/20 | 2/20 | 0.30 | 144695 |


### Category: context_dependent

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 0.62 | 5/8 | 5/8 | 1/8 | 0.31 |
| message_only | 0.50 | 7/8 | 7/8 | 1/8 | 0.00 |
| secondlook | 0.72 | 4/8 | 3/8 | 1/8 | 0.50 |


### Category: context_fits_scam

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 1.00 | 0/6 | 0/6 | - | 0.00 |
| message_only | 1.00 | 0/6 | 0/6 | - | 0.00 |
| secondlook | 0.92 | 1/6 | 0/6 | - | 0.33 |


### Category: clear_scam

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 1.00 | 0/6 | 0/6 | - | 0.00 |
| message_only | 1.00 | 0/6 | 0/6 | - | 0.00 |
| secondlook | 1.00 | 0/6 | 0/6 | - | 0.17 |


### Category: clear_legit

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 1.00 | - | - | 0/12 | 0.00 |
| message_only | 1.00 | - | - | 0/12 | 0.00 |
| secondlook | 0.92 | - | - | 1/12 | 0.08 |


## Focus scope: delivery & e-commerce, phishing, job (+ everyday genuine messages)

Out-of-scope scams (government impersonation, investment, friend impersonation) are excluded here.

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 0.86 | 4/17 | 4/17 | 1/19 | 0.14 |
| message_only | 0.81 | 6/17 | 6/17 | 1/19 | 0.00 |
| secondlook | 0.86 | 4/17 | 2/17 | 2/19 | 0.33 |


### Scam type: delivery_ecommerce

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 1.00 | 0/4 | 0/4 | 0/2 | 0.33 |
| message_only | 0.83 | 1/4 | 1/4 | 0/2 | 0.00 |
| secondlook | 0.92 | 1/4 | 0/4 | 0/2 | 0.50 |


### Scam type: phishing

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 0.82 | 2/10 | 2/10 | 1/7 | 0.18 |
| message_only | 0.76 | 3/10 | 3/10 | 1/7 | 0.00 |
| secondlook | 0.82 | 2/10 | 2/10 | 1/7 | 0.41 |


### Scam type: job

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 0.60 | 2/3 | 2/3 | 0/2 | 0.00 |
| message_only | 0.60 | 2/3 | 2/3 | 0/2 | 0.00 |
| secondlook | 0.90 | 1/3 | 0/3 | 0/2 | 0.20 |


### Scam type: out_of_scope

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 0.75 | 1/3 | 1/3 | 0/1 | 0.00 |
| message_only | 0.75 | 1/3 | 1/3 | 0/1 | 0.00 |
| secondlook | 0.75 | 1/3 | 1/3 | 0/1 | 0.00 |


### Scam type: everyday

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Questions / msg |
|---|---|---|---|---|---|
| ask_prompted | 1.00 | - | - | 0/8 | 0.00 |
| message_only | 1.00 | - | - | 0/8 | 0.00 |
| secondlook | 0.88 | - | - | 1/8 | 0.12 |


## Arena: head-to-head on the same messages

| Rank | Condition | Wins | Losses | Ties |
|---|---|---|---|---|
| 1 | secondlook | 6 | 4 | 70 |
| 2 | ask_prompted | 4 | 2 | 74 |
| 3 | message_only | 2 | 6 | 72 |


| Match | Result |
|---|---|
| ask_prompted vs message_only | 2-0 (38 ties) |
| ask_prompted vs secondlook | 2-2 (36 ties) |
| message_only vs secondlook | 2-4 (34 ties) |


## Idea 2: verdict design (same SecondLook judgements, three ways of showing them)

| Condition | Mean outcome score | Missed scams | Unsafe outcomes | False alarms | Friction on harmless legit msgs |
|---|---|---|---|---|---|
| always_cautious | 0.58 | 0/20 | 0/20 | 20/20 | 12/20 |
| binary | 0.82 | 5/20 | 5/20 | 2/20 | 0/20 |
| tiered | 0.85 | 5/20 | 3/20 | 2/20 | 0/20 |


| Policy | Wins | Losses | Ties |
|---|---|---|---|
| tiered | 20 | 5 | 55 |
| binary | 18 | 7 | 55 |
| always_cautious | 10 | 36 | 34 |


### Evidence checks (SecondLook)

Red-flag phrases found verbatim in the message: 32/32  
Advisory quotes found verbatim in the corpus: 29/32  
Verdicts changed by code guardrails: 5/40
