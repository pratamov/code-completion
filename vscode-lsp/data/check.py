import json
import re

functions = []
with open("procedure_keywords.json", "r", encoding="utf-8") as f:
    data = json.load(f)
    for k, v in data.get("keywords").items():
        code = v.replace('\n', ' ')
        code = re.sub(r'\{.*?\}', '', code, flags=re.DOTALL)
        code = re.sub(r'\s+', ' ', code).strip()
        code = code.replace(" ,", ",")
        code = code.replace(" ;", ";")
        functions.append(code)
        
functions = sorted(functions)

with open("functions.json", "w", encoding="utf-8") as f:
    json.dump(functions, f, ensure_ascii=False, indent=4)