def copy_omit_keys(d, omit_keys):
    return {k: d[k] for k in set(list(d.keys())) - set(omit_keys)}
