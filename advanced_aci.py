import os
import autopep8

def zero_token_syntax_fix(file_path: str) -> bool:
    """
    Attempts to fix trivial syntax errors (indentation, missing colons, whitespace)
    without calling the LLM. Returns True if file was modified.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original = f.read()
        
        # autopep8 aggressive level 2 fixes many PEP8 and simple syntax issues
        fixed = autopep8.fix_code(original, options={'aggressive': 2, 'pep8_passes': 3})
        
        if fixed != original:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fixed)
            return True
    except Exception:
        pass
    return False

def auto_fix_all_python_files(directory: str = "output"):
    """
    Runs the zero-token syntax fixer on all Python files in the given directory.
    """
    fixes_applied = 0
    if not os.path.exists(directory):
        return fixes_applied
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                if zero_token_syntax_fix(filepath):
                    fixes_applied += 1
    return fixes_applied
