import copy


def mask_sensitive_values(event: dict, sensitive_keys: list = ["email"]) -> dict:
    _event = copy.deepcopy(event)
    for k, v in _event.items():
        if k in sensitive_keys:
            _event[k] = "*" * len(v)
        elif isinstance(v, dict):
            _event[k] = mask_sensitive_values(v, sensitive_keys)
    return _event
