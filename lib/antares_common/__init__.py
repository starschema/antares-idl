

def str2bool (val):
    if type(val) is not str:
        raise ValueError(f"invalid value type {type(val)}")

    val = val.lower()
    if val in ('y', 'yes', 't', 'true', 'on', '1'):
        parsed_val = True
    elif val in ('n', 'no', 'f', 'false', 'off', '0'):
        parsed_val = False
    else:
        raise ValueError(f"invalid truth value {val}")
        
    return parsed_val