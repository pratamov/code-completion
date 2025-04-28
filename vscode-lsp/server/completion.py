from typing import Dict, Any

def generate_completions(request: Dict[str, Any]) -> Dict[str, Any]:
    """Generate completion items based on the full document and position."""
    document = request['document']
    position = request['position']
    text = document['text']
    lines = text.split('\n')
    
    # Get current line up to cursor position
    current_line = lines[position['line']][:position['character']]
    current_word = ''
    
    # Simple word extraction (improve as needed)
    for char in reversed(current_line):
        if char.isalnum() or char == '_':
            current_word = char + current_word
        else:
            break
    
    # COMPLETION LOGIC
    completed_word = f"{current_word}_completed..."
    
    # RESPONSE
    completions = []
    if current_word:
        completions.append({
            "insertText": completed_word,
            "range": {
                "start": {
                    "line": position['line'],
                    "character": position['character'] - len(current_word)
                },
                "end": {
                    "line": position['line'],
                    "character": position['character']
                }
            },
            "command": {
                "command": "demo-ext.command1",
                "title": "Completion Accepted",
                "arguments": [current_word, completed_word]
            }
        })
    
    # Add another example completion
    completions.append({
        "insertText": "example_snippet(${1:arg})",
        "range": {
            "start": {"line": position['line'], "character": position['character']},
            "end": {"line": position['line'], "character": position['character']}
        }
    })
    
    return {"items": completions}