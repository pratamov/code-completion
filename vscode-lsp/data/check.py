import json
import re

# functions = []
# with open("procedure_keywords.json", "r", encoding="utf-8") as f:
#     data = json.load(f)
#     for k, v in data.get("keywords").items():
#         code = v.replace('\n', ' ')
#         code = re.sub(r'\{.*?\}', '', code, flags=re.DOTALL)
#         code = re.sub(r'\s+', ' ', code).strip()
#         code = code.replace(" ,", ",")
#         code = code.replace(" ;", ";")
#         functions.append(code)
        
# functions = sorted(functions)

# with open("functions.json", "w", encoding="utf-8") as f:
#     json.dump(functions, f, ensure_ascii=False, indent=4)


variables = []
with open("parameters.txt", "r", encoding="utf-8") as f:
    for line in f.read().split("\n"):
        code = line.strip()
        code = re.sub(r'\{.*?\}', '', code, flags=re.DOTALL)
        code = re.sub(r'\s+', ' ', code).strip()
        code = code.replace(" ,", ",")
        code = code.replace(" ;", ";")
        
        if code.endswith(";") and "{" not in code and "}" not in code:
            variables.append(code)
            
variables = sorted(variables)
with open("parameters.json", "w", encoding="utf-8") as f:
    json.dump(variables, f, ensure_ascii=False, indent=4)