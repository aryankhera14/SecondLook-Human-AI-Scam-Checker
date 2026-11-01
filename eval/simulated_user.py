"""A simulated person who answers ask_user truthfully from a context card."""


def answer_from_card(question: dict, card: dict) -> str:
    value = card.get(question.get("context_key"))
    word = {True: "Yes", False: "No"}.get(value, "Not sure")
    for opt in question.get("options") or []:  # use the model's own option wording when it matches
        if opt.strip().lower().startswith(word.lower()):
            return opt
    return word
