import json
import os
import re
from typing import Dict, Any, List, Union

# --- Global Data Structures ---
function_list: List[str] = []
parameter_list: List[str] = []
variable_list: List[str] = []
structured_functions: Dict[str, Any] = {} # New structure for STATE block completions

# --- Function for parsing and structuring functions.json ---

def parse_function_string(func_str: str) -> Dict[str, Any]:
    """
    Parses a single function signature string into its components.
    e.g., "System.WriteSectINI(\"C:\\VTScada\\Setup.INI\", \"System\", Vals, 0 );"
    """
    cleaned_str = func_str.strip()
    # Remove trailing ');' or ';'
    if cleaned_str.endswith(');'):
        cleaned_str = cleaned_str[:-2]
    elif cleaned_str.endswith(';'):
        cleaned_str = cleaned_str[:-1]

    # Use regex to split function name from arguments
    match = re.match(r'^(.*?)\((.*)$', cleaned_str)
    if not match:
        # Handle cases like "System." if they appear without parentheses (as object prefixes)
        if cleaned_str.endswith('.'):
            return {"name": cleaned_str.rstrip('.'), "type": "object_prefix", "full_signature": func_str}
        return {"name": cleaned_str, "type": "unknown", "full_signature": func_str} # Fallback for unparseable strings

    name_part = match.group(1).strip()
    args_part = match.group(2).strip() # This contains arguments until the end of the parentheses

    obj_name: str | None = None
    method_name: str = name_part

    if '.' in name_part:
        parts = name_part.split('.')
        obj_name = parts[0]
        method_name = ".".join(parts[1:]) # Rejoin if method name itself has dots (unlikely here but robust)

    # Parse arguments while respecting quotes and nested parentheses
    params = []
    if args_part:
        current_param = []
        paren_level = 0
        in_quote = False
        
        for char in args_part:
            if char == '"':
                in_quote = not in_quote
            elif char == '(' and not in_quote:
                paren_level += 1
            elif char == ')' and not in_quote:
                paren_level -= 1 # This should ideally balance to 0 for a complete arg list
            
            # Split by comma only if not inside quotes or nested parentheses
            if char == ',' and paren_level == 0 and not in_quote:
                params.append("".join(current_param).strip())
                current_param = []
            else:
                current_param.append(char)
        
        if current_param: # Add the last parameter
            params.append("".join(current_param).strip())

    return {
        "name": method_name,
        "object": obj_name,
        "type": "function",
        "full_signature": func_str, # Store original for reference
        "params": params
    }

def structure_functions_data(function_strings: List[str]) -> Dict[str, Any]:
    """
    Transforms a list of raw function signature strings into a structured dictionary
    for hierarchical completion.
    """
    structured_data: Dict[str, Any] = {}

    for func_str in function_strings:
        parsed = parse_function_string(func_str)
        
        if parsed["type"] == "function":
            obj_name = parsed["object"]
            method_name = parsed["name"]
            
            target_dict = structured_data
            if obj_name:
                if obj_name not in target_dict:
                    target_dict[obj_name] = {"type": "object", "members": {}}
                target_dict = target_dict[obj_name]["members"]
            
            # Store functions as a list to handle potential overloads (same name, different params)
            if method_name not in target_dict:
                target_dict[method_name] = [] 
            
            # Add only relevant info for completion
            target_dict[method_name].append({
                "type": "function",
                "signature_full": parsed["full_signature"], # The original full string
                "params": parsed["params"]
            })
        elif parsed["type"] == "object_prefix":
            obj_name = parsed["name"]
            if obj_name not in structured_data:
                structured_data[obj_name] = {"type": "object", "members": {}}
    
    return structured_data

# --- Load Data ---
try:
    with open("data/functions.json", "r", encoding="utf-8") as f:
        function_list = json.load(f)
    structured_functions = structure_functions_data(function_list) # Build structured data on load
    # print("DEBUG: Loaded structured_functions data.")
    # print(json.dumps(structured_functions, indent=2)) # Uncomment to see the full structure

    with open("data/parameters.json", "r", encoding="utf-8") as f:
        parameter_list = json.load(f)

    with open("data/variables.json", "r", encoding="utf-8") as f:
        variable_list = json.load(f)

except FileNotFoundError as e:
    print(f"Error: Required data file not found: {e.filename}. Please ensure 'data/functions.json', 'data/parameters.json', and 'data/variables.json' exist in the 'data/' directory.")
    raise # Re-raise the exception to halt execution as per request
except json.JSONDecodeError as e:
    print(f"Error: Malformed JSON in data file: {e}. Please check the content of your JSON files for syntax errors.")
    raise # Re-raise the exception to halt execution

# --- Core Logic Functions ---

def detect_block(pos_line: int, pos_char: int, lines: List[str]) -> str | None:
    """
    Detects the most specific block (STATE, PARAMETER, VARIABLE) the cursor is currently within.
    This function handles cases where the cursor is on the opening line after the bracket.
    """
    
    current_block_type = None
    last_open_line = -1

    # Iterate backwards from the cursor line to find the most recent open bracket
    for i in range(pos_line, -1, -1):
        line_clean = lines[i].strip()
        if line_clean == '(':
            last_open_line = i
            current_block_type = 'PARAMETER'
            break 
        elif line_clean == '[':
            last_open_line = i
            current_block_type = 'VARIABLE'
            break 
        elif line_clean.endswith('[') and not line_clean.startswith(('{', '//')):
            last_open_line = i
            current_block_type = 'STATE'
            break 
            
    if last_open_line == -1:
        return None # No opening bracket found before or at the cursor

    # Find the first corresponding closing bracket after the detected open_line
    first_close_line = -1
    for i in range(last_open_line + 1, len(lines)):
        line_clean = lines[i].strip()
        if (current_block_type == 'PARAMETER' and ')' in line_clean) or \
           ((current_block_type == 'VARIABLE' or current_block_type == 'STATE') and ']' in line_clean):
            first_close_line = i
            break
            
    # Check if the cursor is within the block boundaries
    if pos_line > last_open_line: # Cursor is on a line strictly after the opener
        if first_close_line == -1 or pos_line < first_close_line:
            return current_block_type
    elif pos_line == last_open_line: # Cursor is on the opening line
        line_content = lines[pos_line]
        # Ensure cursor is AFTER the opening bracket on the same line
        if current_block_type == 'STATE' and pos_char > line_content.find('['):
            return current_block_type
        elif current_block_type == 'PARAMETER' and pos_char > line_content.find('('):
            return current_block_type
        elif current_block_type == 'VARIABLE' and pos_char > line_content.find('['):
            return current_block_type
            
    return None

def block_context_valid(position: Dict[str, Any], lines: List[str], block_type: str) -> bool:
    """
    Validates if the context within the detected block allows suggestions.
    This function now correctly handles different line ending expectations for each block type.
    It's more lenient on the current line being typed.
    """
    # Find the actual open_line for the detected block_type by searching backwards
    open_line = -1
    for i in range(position['line'], -1, -1):
        line_clean = lines[i].strip()
        if (block_type == 'PARAMETER' and line_clean == '(') or \
           (block_type == 'VARIABLE' and line_clean == '[') or \
           (block_type == 'STATE' and line_clean.endswith('[') and not line_clean.startswith(('{', '//'))):
            open_line = i
            break
    
    if open_line == -1: 
        # print("DEBUG: block_context_valid: No open_line found.")
        return False # This case should ideally not be reached if detect_block worked correctly

    # If cursor is on the open_line
    if position['line'] == open_line:
        line_content = lines[position['line']]
        char_after_bracket = -1
        if block_type == 'STATE':
            char_after_bracket = line_content.find('[') + 1
        elif block_type == 'PARAMETER':
            char_after_bracket = line_content.find('(') + 1
        elif block_type == 'VARIABLE':
            char_after_bracket = line_content.find('[') + 1
        
        # Cursor must be at or after the character immediately following the opening bracket
        if position['character'] < char_after_bracket:
            # print(f"DEBUG: block_context_valid: Cursor before bracket on open_line.")
            return False 

        # The content *after* the opening bracket up to the cursor must be empty or a valid identifier prefix
        current = line_content[char_after_bracket : position['character']].strip()
        # print(f"DEBUG: block_context_valid: On open_line, current prefix='{current}'")
        # Allow empty string, or any sequence of identifier characters and dots/parentheses
        # We are lenient here to allow partial typing for completions.
        return True

    # If cursor is on a line strictly *after* the open_line (inside the block)
    # This loop validates lines *before* the current cursor line.
    for i in range(open_line + 1, position['line']): # Iterate up to, but not including, the current line
        line = lines[i].strip()
        # print(f"DEBUG: block_context_valid: Checking previous line {i}: '{line}'")
        if line == '' or line.startswith('{') or line.startswith('//'):
            continue
        
        # Validate the ending of the previous line based on block type
        is_valid_previous_line = False
        if block_type == 'STATE':
            # STATE block lines (like function calls) are expected to end with ');'
            if line.endswith(');'):
                is_valid_previous_line = True
        elif block_type == 'PARAMETER' or block_type == 'VARIABLE':
            # PARAMETER/VARIABLE block lines (like declarations/assignments) are expected to end with ';'
            if line.endswith(';'):
                is_valid_previous_line = True
        
        # If the line content doesn't match the expected ending for its block type, return False
        if not is_valid_previous_line:
            # print(f"DEBUG: block_context_valid: Previous line {i} '{line}' has invalid ending for {block_type} block.")
            return False
    
    # Check current line prefix: must be empty, an identifier, or a partial object/function call.
    # This specifically targets the line the cursor is on.
    # print(f"DEBUG: block_context_valid: On current line {position['line']}, now allowing any prefix for completion.")
    return True # We allow any prefix on the current line for completion purposes, as long as we're in a block.


def get_simple_completions(prefix: str, position: Dict[str, Any], entries: List[str]) -> List[Dict[str, Any]]:
    """Filters and formats completions for simple (non-contextual) lists."""
    completions = []
    for item in entries:
        if item.lower().startswith(prefix.lower()):
            completions.append({
                "insertText": item,
                "range": {
                    "start": {
                        "line": position['line'],
                        "character": position['character'] - len(prefix)
                    },
                    "end": {
                        "line": position['line'],
                        "character": position['character']
                    }
                },
                "command": {
                    "command": "demo-ext.command1",
                    "title": "Completion Accepted",
                    "arguments": [prefix, item]
                }
            })
    return completions

def get_contextual_completions(current_text_before_cursor: str, structured_data: Dict[str, Any], position: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Provides context-aware completions for STATE block based on parsed function signatures.
    Handles top-level, object.member, and function parameters.
    """
    completions = []
    current_text_stripped = current_text_before_cursor.strip()
    
    # print(f"DEBUG: get_contextual_completions called.")
    # print(f"DEBUG: current_text_before_cursor='{current_text_before_cursor}'")
    # print(f"DEBUG: current_text_stripped='{current_text_stripped}'")
    # print(f"DEBUG: position={position}")

    last_dot_idx = -1
    last_open_paren_idx = -1
    
    # Find last unmatched '(' and '.'
    paren_balance = 0
    in_quote = False
    for i in range(len(current_text_stripped) - 1, -1, -1):
        char = current_text_stripped[i]
        if char == '"':
            in_quote = not in_quote
        elif char == ')' and not in_quote:
            paren_balance += 1
        elif char == '(' and not in_quote:
            paren_balance -= 1
            if paren_balance == -1: # Found an unmatched open parenthesis
                last_open_paren_idx = i
                break # We care about the innermost unmatched
        elif char == '.' and paren_balance == 0 and not in_quote:
            if last_dot_idx == -1: # Capture the rightmost dot outside of parens/quotes
                last_dot_idx = i
            
    # State: Inside function parameters
    # If we found an unmatched '(', we are likely inside parameters.
    if last_open_paren_idx != -1:
        # print(f"DEBUG: Entering PARAMETERS state.")
        function_call_prefix = current_text_stripped[:last_open_paren_idx].strip()
        params_string = current_text_stripped[last_open_paren_idx + 1:]

        # print(f"DEBUG: function_call_prefix='{function_call_prefix}'")
        # print(f"DEBUG: params_string='{params_string}'")

        # Extract the full function name (e.g., "System.WriteSectINI" or "TGet")
        func_name_match = re.search(r'([a-zA-Z0-9_.]+)$', function_call_prefix)
        if func_name_match:
            full_func_path = func_name_match.group(1)
            # print(f"DEBUG: full_func_path='{full_func_path}'")
            
            parts = full_func_path.split('.')
            data_pointer = structured_data
            target_func_info: Union[List[Dict[str, Any]], None] = None

            for i, part in enumerate(parts):
                if part in data_pointer:
                    if isinstance(data_pointer[part], dict) and data_pointer[part].get("type") == "object":
                        data_pointer = data_pointer[part]["members"]
                    elif isinstance(data_pointer[part], list) and i == len(parts) - 1: # Last part is the function name itself
                        target_func_info = data_pointer[part]
                        break
                    else: # Unexpected structure, or part is not an object/function list
                        target_func_info = None
                        break
                else: # Path not found
                    target_func_info = None
                    break
            
            # print(f"DEBUG: target_func_info found: {bool(target_func_info)}")
            if target_func_info:
                # Determine current parameter index based on commas outside of quotes/parens
                param_index = 0
                temp_paren_level = 0
                temp_in_quote = False
                for char in params_string:
                    if char == '"':
                        temp_in_quote = not temp_in_quote
                    elif char == '(' and not temp_in_quote:
                        temp_paren_level += 1
                    elif char == ')' and not temp_in_quote:
                        temp_paren_level -= 1
                    elif char == ',' and temp_paren_level == 0 and not temp_in_quote:
                        param_index += 1
                
                current_param_prefix_match = re.search(r'[^,]*$', params_string.strip())
                current_param_prefix = current_param_prefix_match.group(0).strip() if current_param_prefix_match else ''
                
                # print(f"DEBUG: param_index={param_index}, current_param_prefix='{current_param_prefix}'")

                for func_signature_data in target_func_info:
                    # print(f"DEBUG: Checking signature: {func_signature_data.get('signature_full')}, params len: {len(func_signature_data.get('params', []))}")
                    
                    all_params_for_signature = func_signature_data.get("params", [])
                    num_params_in_signature = len(all_params_for_signature)

                    if func_signature_data["type"] == "function" and num_params_in_signature > param_index:
                        param_to_suggest = all_params_for_signature[param_index]
                        
                        # Only suggest if the prefix matches
                        if param_to_suggest.lower().startswith(current_param_prefix.lower()):
                            display_text_suffix = ""
                            insert_text_suffix = ""

                            if param_index < num_params_in_signature - 1:
                                # Not the last parameter, append comma and space for display/insert
                                display_text_suffix = ","
                                insert_text_suffix = "," 
                            else:
                                # Last parameter, append closing parenthesis and semicolon
                                display_text_suffix = " );"
                                insert_text_suffix = " );"
                            
                            # Construct the full text to display and insert
                            # Strip quotes for display label, keep for insertion if present
                            display_label = param_to_suggest.strip('"') + display_text_suffix
                            insert_completion_text = param_to_suggest + insert_text_suffix 

                            completions.append({
                                "label": display_label,
                                "insertText": insert_completion_text,
                                # Range should replace the current partial parameter text
                                "range": {
                                    "start": {
                                        "line": position['line'],
                                        "character": position['character'] - len(current_param_prefix)
                                    },
                                    "end": {
                                        "line": position['line'],
                                        "character": position['character']
                                    }
                                },
                                "command": {
                                    "command": "demo-ext.command1",
                                    "title": "Parameter Accepted",
                                    "arguments": [current_param_prefix, insert_completion_text]
                                }
                            })
                            # print(f"DEBUG: Added parameter completion: {display_label}")
                return completions # Only suggest parameters if inside parens

    # State: After a dot (object members)
    # Check if the last significant token before the cursor is a '.'
    # and it's not part of a function call (handled above)
    elif last_dot_idx != -1 and (last_open_paren_idx == -1 or last_dot_idx > last_open_paren_idx):
        # print(f"DEBUG: Entering OBJECT.MEMBER state.")
        obj_path_prefix = current_text_stripped[:last_dot_idx].strip()
        member_prefix = current_text_stripped[last_dot_idx + 1:]

        # print(f"DEBUG: obj_path_prefix='{obj_path_prefix}'")
        # print(f"DEBUG: member_prefix='{member_prefix}'")

        # Navigate the structured_data to find the object
        data_pointer = structured_data
        obj_parts = obj_path_prefix.split('.')
        found_obj = True
        for part in obj_parts:
            if part in data_pointer and isinstance(data_pointer[part], dict) and data_pointer[part].get("type") == "object":
                data_pointer = data_pointer[part]["members"]
            else:
                found_obj = False
                break
        
        # print(f"DEBUG: Object found: {found_obj}")
        if found_obj:
            # print(f"DEBUG: data_pointer keys: {list(data_pointer.keys())}")
            for member_name, member_info in data_pointer.items():
                if member_name.lower().startswith(member_prefix.lower()):
                    insert_text_suffix = ""
                    # If the member is a function (represented as a list of definitions)
                    if isinstance(member_info, list) and member_info and member_info[0]["type"] == "function":
                        insert_text_suffix = "(" # Add '(' for function completions
                    
                    completions.append({
                        "label": member_name + insert_text_suffix,
                        "insertText": member_name + insert_text_suffix,
                        "range": {
                            "start": {
                                "line": position['line'],
                                "character": position['character'] - len(member_prefix)
                            },
                            "end": {
                                "line": position['line'],
                                "character": position['character']
                            }
                        },
                        "command": {
                            "command": "demo-ext.command1",
                            "title": "Member Accepted",
                            "arguments": [member_prefix, member_name + insert_text_suffix]
                        }
                    })
                    # print(f"DEBUG: Added member completion: {member_name + insert_text_suffix}")
            return completions # Only suggest members if after a dot

    # State: Root level (top-level objects/functions)
    else: # This 'else' covers cases where no dot or open paren context is found
        # print(f"DEBUG: Entering ROOT state.")
        root_prefix_match = re.search(r'([a-zA-Z0-9_]+)$', current_text_stripped)
        root_prefix = root_prefix_match.group(1) if root_prefix_match else ''
        
        # print(f"DEBUG: root_prefix='{root_prefix}'")

        for name, item_info in structured_data.items():
            if name.lower().startswith(root_prefix.lower()):
                insert_text_suffix = ""
                
                # Check if it's an object (which is a dict with "type": "object")
                if isinstance(item_info, dict) and item_info.get("type") == "object":
                    insert_text_suffix = "." # Add '.' for object completions
                # Check if it's a function (which is a list of definitions)
                elif isinstance(item_info, list) and item_info and item_info[0]["type"] == "function": 
                    insert_text_suffix = "(" # Add '(' for function completions
                
                completions.append({
                    "label": name + insert_text_suffix,
                    "insertText": name + insert_text_suffix,
                    "range": {
                        "start": {
                            "line": position['line'],
                            "character": position['character'] - len(root_prefix)
                        },
                        "end": {
                            "line": position['line'],
                            "character": position['character']
                        }
                    },
                    "command": {
                        "command": "demo-ext.command1",
                        "title": "Root Accepted",
                        "arguments": [root_prefix, name + insert_text_suffix]
                    }
                })
                # print(f"DEBUG: Added root completion: {name + insert_text_suffix}")

    # print(f"DEBUG: Final completions count: {len(completions)}")
    return completions

# --- Main Completion Function ---

def generate_completions(request: Dict[str, Any]) -> Dict[str, Any]:
    """Main function to generate completions based on file content and cursor position."""
    document = request['document']
    position = request['position']
    text = document['text']
    lines = text.split('\n')
    completions = []

    # print(f"DEBUG: generate_completions called for line {position['line']}, char {position['character']}")

    # Suggest skeleton if file is empty
    if text.strip() == '':
        skeleton_path = "skeleton.txt"
        if os.path.exists(skeleton_path):
            with open(skeleton_path, 'r', encoding='utf-8') as f:
                skeleton_content = f.read()
            completions.append({
                "insertText": skeleton_content,
                "insertTextFormat": 2, # Snippet format
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 0}
                },
                "command": {
                    "command": "demo-ext.command1",
                    "title": "Insert Skeleton",
                    "arguments": [12, 35] 
                }
            })
        # print(f"DEBUG: Returning skeleton suggestions.")
        return {"items": completions}

    # Detect block and validate context
    block = detect_block(position['line'], position['character'], lines)
    # print(f"DEBUG: Detected block: {block}")

    if block and block_context_valid(position, lines, block):
        current_line_content_before_cursor = lines[position['line']][:position['character']]

        if block == 'STATE':
            # Use contextual completions for STATE block
            completions = get_contextual_completions(current_line_content_before_cursor, structured_functions, position)
        elif block == 'PARAMETER':
            # Use simple completions for PARAMETER block
            current_word = ''
            for char in reversed(current_line_content_before_cursor):
                if char.isalnum() or char == '_':
                    current_word = char + current_word
                else:
                    break
            # print(f"DEBUG: PARAMETER block, current_word='{current_word}'")
            completions = get_simple_completions(current_word, position, parameter_list)
        elif block == 'VARIABLE':
            # Use simple completions for VARIABLE block
            current_word = ''
            for char in reversed(current_line_content_before_cursor):
                if char.isalnum() or char == '_':
                    current_word = char + current_word
                else:
                    break
            # print(f"DEBUG: VARIABLE block, current_word='{current_word}'")
            completions = get_simple_completions(current_word, position, variable_list)
    # else:
        # print(f"DEBUG: No valid block context or block detected.")

    return {"items": completions}