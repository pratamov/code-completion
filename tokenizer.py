import re
import json
from typing import List, Dict, Union, Callable

# Define type aliases for better readability
TokenDefinition = Dict[str, Union[str, Callable]]
TokenList = List[TokenDefinition]

def get_special_tokens() -> TokenList:
    """Returns a list of token definitions with their corresponding regex patterns."""
    return [
        # Submodule tokens
        {"token": " #<# ", "regex": r"\s*<\s*"},
        {"token": " #># ", "regex": r"\s*>\s*"},
        
        # String and comment tokens
        {"token": " #<STRING_VAL># ", "regex": r"\"(.*?)\""},
        {"token": " #<COMMENT># ", "regex": r"\{([\s\S]*?)\}"},
        {"token": " #<EOL># ", "regex": r"\n"},
        
        # Bracket tokens
        {"token": " #{# ", "regex": r"\{"},
        {"token": " #}# ", "regex": r"\}"},
        {"token": " #(# ", "regex": r"\("},
        {"token": " #)# ", "regex": r"\)"},
        {"token": " #[# ", "regex": r"\["},
        {"token": " #]# ", "regex": r"\]"},
        
        # If expression tokens
        {"token": " #IfThen# #(# ", "regex": r"\s+IfThen\s*#\(#"},
        {"token": " #If# ", "regex": r"\s+If\s+"},
        
        # Parameter metadata token
        {"token": " #<:# #PARAM_META# #:>#", "regex": r"<:(.*?):>"},

        # Operator tokens
        {"token": " #=# #SPC# #.# ", "regex": r"=\s*\."},
        {"token": " #=# #SPC# #\\# ", "regex": r"=\s*\\"},
        {"token": " #=# #SPC# #*# ", "regex": r"=\s*\*"},
        {"token": " #=# #SPC# #&# ", "regex": r"=\s*&"},
        {"token": " #=# #SPC# #!# ", "regex": r"=\s*!"},
        {"token": " #<<# ", "regex": r"<<"},
        {"token": " #>># ", "regex": r">>"},
        {"token": " #>=# ", "regex": r">="},
        {"token": " #<=# ", "regex": r"<="},
        {"token": " #!=# ", "regex": r"!="},
        {"token": " #+=# ", "regex": r"\+="},
        {"token": " #-=# ", "regex": r"-="},
        {"token": " #/=# ", "regex": r"/="},
        {"token": " #%=# ", "regex": r"%="},
        {"token": " #*=# ", "regex": r"\*="},
        {"token": " #&&# ", "regex": r"&&"},
        {"token": " #||# ", "regex": r"\|\|"},
        {"token": " #=# #SPC# #-# ", "regex": r"=\s*-"},
        {"token": " #/# ", "regex": r"/"},
        {"token": " #%# ", "regex": r"%"},
        {"token": " #*# ", "regex": r"\*"},
        {"token": " #-# ", "regex": r"-"},
        {"token": " #--# ", "regex": r"#-# #-#"},
        {"token": " #+# ", "regex": r"\+"},
        {"token": " #++# ", "regex": r"#\+# #\+#"},
        {"token": " #^# ", "regex": r"\^"},
        
        # Comma token
        {"token": " #,# #SPC# ", "regex": r","},
        
        # Equality tokens
        {"token": " #=# ", "regex": r"\s+=\s+"},
        {"token": " #==# ", "regex": r"#=# #=#"},
        
        # CONSTANT declaration token (using lambda for dynamic token generation)
        {
            "token": lambda x: f" #<CONSTANT># #<SPC># #<CONST_NAME>:{x.group(1)}# #<SPC># #=# #<SPC># #<CONST_VAL>:{x.group(2)}# #;# #<EOL># ",
            "regex": r"CONSTANT\s+([A-Za-z0-9_]+)\s*=\s*(.*?)\s*;"
        },
    ]

def sanitize(snippets: str) -> str:
    """Cleans up the processed snippets by removing excessive whitespace and newlines."""
    # Remove double whitespaces
    snippets = re.sub(r'\s+', ' ', snippets).strip()
    
    # Remove consecutive EOL tokens
    while "#<EOL># #<EOL>#" in snippets:
        snippets = snippets.replace("#<EOL># #<EOL>#", "#<EOL>#")
        
    return snippets

def process_semicolons(snippets: str) -> str:
    """Handles special semicolon token processing."""
    snippets = snippets.replace("#;#", "#SEMICOLON#")
    snippets = snippets.replace(";", " #;# ")
    return snippets.replace("#SEMICOLON#", "#;#")

def tokenize_functions(tokens: List[str]) -> List[str]:
    """Identifies and marks function names in the token list."""
    for i in range(1, len(tokens)):
        if tokens[i] == "#(#" and re.fullmatch(r'^[a-zA-Z_\\][a-zA-Z0-9_\\\.]*[a-zA-Z0-9_]$', tokens[i-1]):
            tokens[i-1] = f" #<FUNC>:{tokens[i-1]}# "
    return tokens

def tokenize_states(tokens: List[str]) -> List[str]:
    """Identifies and marks state names in the token list."""
    for i in range(1, len(tokens)):
        if tokens[i] == "#[#" and re.fullmatch(r'^[a-zA-Z][a-zA-Z0-9_]*$', tokens[i-1]):
            tokens[i-1] = f" #<STATE>:{tokens[i-1]}# "
    return tokens

def tokenize_values(tokens: List[str]) -> List[str]:
    """Identifies and marks special values and variables in the token list."""
    special_values = {"1", "0"}
    for i, token in enumerate(tokens):
        if token in special_values:
            tokens[i] = f"#{token}#"
        elif re.fullmatch(r'^[a-zA-Z\\][a-zA-Z0-9\\\.]*$', token):
            tokens[i] = f"#<VARPARAM>:{token}#"
    return tokens

def process(snippets: str, remove_comments: bool = False) -> str:
    """Main processing function that tokenizes the input snippets."""
    # Apply all token substitutions
    for token_def in get_special_tokens():
        token = token_def["token"]
        regex = token_def["regex"]
        snippets = re.sub(regex, token if not callable(token) else token, snippets)
    
    # Process semicolons and clean up
    snippets = process_semicolons(snippets)
    snippets = sanitize(snippets)
    
    # Split into tokens and apply additional tokenization
    tokens = snippets.split(" ")
    tokens = tokenize_functions(tokens)
    tokens = tokenize_states(tokens)
    tokens = tokenize_values(tokens)
    
    # Remove comments if requested
    if remove_comments:
        tokens = [t for t in tokens if "<COMMENT>" not in t]
    
    # Rejoin and clean up
    snippets = " ".join(tokens)
    return sanitize(snippets)

import os
def build_dataset(datapath="snippets", output_filepath="dataset.json"):
    dataset = []
    
    token_pattern = r'^#(?:<([^>]+)>:)?([^#]+)#$'
    for file in os.listdir(datapath):
        filename = os.fsdecode(file)
        if filename.endswith(".SRC"): 
            values, namespaces = [], []
            with open(f"{datapath}/{filename}", "r", encoding="utf-8") as f:
                text = f.read()
                processed_text = process(text, remove_comments=True)
                # processed_text = processed_text.replace("#<EOL>#", "#<EOL>#\n")
                
                with open(f"{datapath}/{filename}.TOKEN", "w", encoding="utf-8") as ff:
                    ff.write(processed_text)
                
                tokens = processed_text.split(" ")
                for token in tokens:
                    match = re.fullmatch(token_pattern, token)
                    if match:
                        namespace, value = match.groups()
                        if value:
                            values.append(value)
                            namespaces.append(namespace or "ANY")
                        else: print(f"ERROR {token} -> <{namespace}>:{value}")
                        
                    if values and values[-1] == ";" and len(values) > 5:
                        dataset.append((
                            " ".join(values),
                            " ".join(namespaces)
                        ))
                        values = []
                        namespaces = []
            
                if values and dataset:
                    last_data = (
                        f"{dataset[-1][0]} {' '.join(values)}",
                        f"{dataset[-1][1]} {' '.join(namespaces)}"
                    )
                    dataset = dataset[:-1] + [last_data]
                    
    if dataset:
        print("Obtain", len(dataset), "sequences")
        with open(output_filepath, "w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    build_dataset("test", "test/test.json")