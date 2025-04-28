import json
import os
import re

def reverse_tokenize(tokenized_text: str, property_text: str) -> str:
    """Converts tokenized text back to original source code format."""
    # First, handle special token patterns
    # token_pattern = r'#(?:<([^>]+)>:)?([^#]+)#'
    
    def replace_token(namespace, value):
        if namespace == "<STRING_VAL>":
            return f'"{value}"'
        elif namespace == "COMMENT":
            return f'{{{value}}}'
        elif namespace == "<EOL>":
            return '\n'
        elif namespace == "CONST_NAME":
            return value
        elif namespace == "CONST_VAL":
            return value
        elif namespace == "FUNC":
            return value
        elif namespace == "STATE":
            return value
        elif namespace == "VARPARAM":
            return value
        elif value == ";":
            return ";"
        elif value == ",":
            return ", "
        elif value == "=":
            return " = "
        elif value == "{":
            return "{"
        elif value == "}":
            return "}"
        elif value == "(":
            return "("
        elif value == ")":
            return ")"
        elif value == "[":
            return "["
        elif value == "]":
            return "]"
        elif value == "<":
            return " < "
        elif value == ">":
            return " > "
        elif value == "+":
            return "+"
        elif value == "-":
            return "-"
        elif value == "*":
            return "*"
        elif value == "/":
            return "/"
        elif value == "%":
            return "%"
        elif value == "&":
            return "&"
        elif value == "|":
            return "|"
        elif value == "!":
            return "!"
        elif value == "^":
            return "^"
        elif value == "==":
            return "=="
        elif value == "!=":
            return "!="
        elif value == "<=":
            return "<="
        elif value == ">=":
            return ">="
        elif value == "<<":
            return "<<"
        elif value == ">>":
            return ">>"
        elif value == "&&":
            return " && "
        elif value == "||":
            return " || "
        elif value == "+=":
            return "+="
        elif value == "-=":
            return "-="
        elif value == "*=":
            return "*="
        elif value == "/=":
            return "/="
        elif value == "%=":
            return "%="
        elif value == "++":
            return "++"
        elif value == "--":
            return "--"
        elif value == "If":
            return "If"
        elif value == "IfThen":
            return "IfThen"
        elif value == "PARAM_META":
            return f"<:{value}:>"
        elif value == "CONSTANT":
            return "CONSTANT"
        elif value == "SPC":
            return " "
        else:
            return namespace

    # # Replace all tokens
    # detokenized = re.sub(token_pattern, replace_token, tokenized_text)
    
    tokenized_text_split = tokenized_text.split(" ")
    property_text_split = property_text.split(" ")
    
    if len(tokenized_text_split) != len(property_text_split):
        return ""
    
    detokenized_list = []
    for i, namespace in enumerate(tokenized_text_split):
        value = property_text_split[i]
        detokenized_list.append(replace_token(namespace, value))    
    
    # Post-processing to clean up spacing
    detokenized = " ".join(detokenized_list)
    detokenized = detokenized.replace("( ", "(").replace(" )", ")")
    detokenized = detokenized.replace("[ ", "[").replace(" ]", "]")
    detokenized = detokenized.replace("{ ", "{").replace(" }", "}")
    detokenized = detokenized.replace(" ;", ";")
    detokenized = detokenized.replace(" ,", ",")
    
    # Handle special cases for operators
    detokenized = re.sub(r'\s*([+\-*/%&|^])\s*', r' \1 ', detokenized)
    detokenized = re.sub(r'\s*([=!<>]=)\s*', r' \1 ', detokenized)
    
    # Handle CONSTANT declarations
    const_pattern = r'CONSTANT\s+([A-Za-z0-9_]+)\s*=\s*(.*?)\s*;'
    detokenized = re.sub(const_pattern, r'CONSTANT \1 = \2;', detokenized)
    
    return detokenized.strip()

from typing import List
def detokenize(dataset: List[List]) -> List[str]:
    
    lines, lines_tokenized, lines_property = [], [], []
    for tokenized_text, property_text in dataset:
        detokenized = reverse_tokenize(tokenized_text, property_text)
        lines.append(detokenized)
        lines_tokenized.append(tokenized_text)
        lines_property.append(property_text)
    
    return lines, lines_tokenized, lines_property

if __name__ == "__main__":
    with open("dataset.json", "r", encoding="utf-8") as f:
        dataset = json.load(f)
        lines, lines_tokenized, lines_property = detokenize(dataset[:100])
        for i, line in enumerate(lines):
            print("====================================")
            # print(lines_tokenized[i])
            # print("----------")
            print(line)