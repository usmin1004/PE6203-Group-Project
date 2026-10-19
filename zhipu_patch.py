import openai.resources.chat.completions as comp

_orig = comp.Completions.create


def _flatten(messages):
    out = []
    for m in messages:
        m = dict(m)
        c = m.get("content")
        if isinstance(c, list):
            m["content"] = "".join(p.get("text", "") for p in c if isinstance(p, dict))
        out.append(m)
    return out


def create(self, *args, **kwargs):
    if "messages" in kwargs:
        kwargs["messages"] = _flatten(kwargs["messages"])
    return _orig(self, *args, **kwargs)


comp.Completions.create = create