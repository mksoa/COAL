import re
from coal.identity import AttemptIdentity

SHA = "a" * 40


def ident(**kw):
    d = dict(repository="owner/repo", subject="mission-1", epoch="E1", operation_id="op-1",
             source_binding="src-1")
    d.update(kw)
    return AttemptIdentity(**d)


def mini_validate(schema, inst, path="$"):
    """Tiny JSON-Schema subset validator (type/required/properties/additionalProperties/enum/const/pattern/min*)."""
    errs = []
    t = schema.get("type")
    tmap = {"object": dict, "string": str, "integer": int, "boolean": bool, "null": type(None)}
    if t is not None:
        ts = t if isinstance(t, list) else [t]
        ok = any(isinstance(inst, tmap[x]) and not (x == "integer" and isinstance(inst, bool)) for x in ts)
        if not ok:
            return [f"{path}: type"]
    if "enum" in schema and inst not in schema["enum"]:
        errs.append(f"{path}: enum")
    if "const" in schema and inst != schema["const"]:
        errs.append(f"{path}: const")
    if isinstance(inst, str):
        if "pattern" in schema and not re.search(schema["pattern"], inst):
            errs.append(f"{path}: pattern")
        if len(inst) < schema.get("minLength", 0) or len(inst) > schema.get("maxLength", 10**9):
            errs.append(f"{path}: length")
    if isinstance(inst, int) and not isinstance(inst, bool) and inst < schema.get("minimum", inst):
        errs.append(f"{path}: minimum")
    if isinstance(inst, dict):
        for r in schema.get("required", []):
            if r not in inst:
                errs.append(f"{path}.{r}: required")
        props = schema.get("properties", {})
        for k, v in inst.items():
            if k in props:
                errs += mini_validate(props[k], v, f"{path}.{k}")
            elif schema.get("additionalProperties") is False:
                errs.append(f"{path}.{k}: additional")
    return errs
