def mask_sensitive_values(event: dict, sensitive_keys: list = ["email"]) -> dict:
    for k, v in list(event.items()):
        if k in sensitive_keys:
            event[k] = "*" * len(v)
        elif isinstance(v, dict):
            mask_sensitive_values(v, sensitive_keys)
    return event
