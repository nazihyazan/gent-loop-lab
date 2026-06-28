import os
import json
import shutil
import urllib.request
from openai import OpenAI

# The Ngrok URL provided by Kaggle, passed via GitHub Secrets
api_base = os.environ.get("ZAI_API_URL", "http://localhost:11434/v1")
# Ollama doesn't require a real API key, but the client requires the parameter
api_key = "ollama"

client = OpenAI(
    base_url=api_base,
    api_key=api_key,
    default_headers={"ngrok-skip-browser-warning": "any"}
)

# The model name loaded in Kaggle
MODEL_NAME = "qwen2.5:14b"

def load_knowledge_base(directory="knowledge"):
    """Reads all markdown and text files in the knowledge directory and combines them into a single string."""
    kb_content = ""
    if not os.path.exists(directory):
        return kb_content
        
    for filename in os.listdir(directory):
        if filename.endswith(".md") or filename.endswith(".txt"):
            filepath = os.path.join(directory, filename)
            with open(filepath, 'r') as f:
                kb_content += f"\n--- {filename} ---\n{f.read()}\n"
    return kb_content

def validate_syntax_in_output(output_dir="output"):
    """Basic non-LLM check to ensure brackets are matched in all generated code files."""
    brackets = {'{': '}', '[': ']', '(': ')'}
    
    if not os.path.exists(output_dir):
        return True, "No files generated to check."
        
    for root, _, files in os.walk(output_dir):
        for file in files:
            if file.endswith(('.js', '.jsx', '.ts', '.tsx', '.py', '.json')):
                filepath = os.path.join(root, file)
                with open(filepath, 'r') as f:
                    code = f.read()
                    
                stack = []
                for char in code:
                    if char in brackets:
                        stack.append(char)
                    elif char in brackets.values():
                        if not stack:
                            return False, f"File {file}: Found closing bracket with no matching opening bracket."
                        last = stack.pop()
                        if brackets[last] != char:
                            return False, f"File {file}: Mismatched brackets found."
                            
                if stack:
                    return False, f"File {file}: Unclosed brackets found."
    return True, "All generated files have valid basic syntax."

def read_entire_output(output_dir="output"):
    """Reads all files in the output directory for the Reviewer to analyze."""
    if not os.path.exists(output_dir):
        return "No files generated yet."
    
    content = ""
    for root, _, files in os.walk(output_dir):
        for file in files:
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, output_dir)
            with open(filepath, 'r') as f:
                content += f"\n--- FILE: {rel_path} ---\n{f.read()}\n"
    return content

def execute_tool(tool_call):
    """Executes the requested tool and returns the result string."""
    name = tool_call.function.name
    try:
        args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError:
        return "Error: Invalid JSON arguments provided."

    if name == "read_file":
        filepath = args.get("filepath", "")
        print(f"🛠️ Agent reading file: {filepath}")
        try:
            with open(filepath, 'r') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"
            
    elif name == "write_file":
        filepath = args.get("filepath", "")
        content = args.get("content", "")
        print(f"🛠️ Agent writing file: output/{filepath}")
        
        # Ensure it writes inside 'output' directory
        full_path = os.path.join("output", filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        try:
            with open(full_path, 'w') as f:
                f.write(content)
            return f"Successfully wrote to {filepath}"
        except Exception as e:
            return f"Error writing file: {str(e)}"
            
    elif name == "fetch_url":
        url = args.get("url", "")
        print(f"🌐 Agent fetching URL: {url}")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read().decode('utf-8')[:5000] # Limit to 5k chars to avoid token explosion
        except Exception as e:
            return f"Error fetching URL: {str(e)}"

    return f"Unknown tool: {name}"

def call_agent(role, task, context="", custom_system_prompt=None, available_tools=None):
    print(f"\n--- Running {role} ---")
    system_prompt = custom_system_prompt if custom_system_prompt else f"You are an expert {role}."
    user_prompt = f"Context:\n{context}\n\nTask:\n{task}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    tools = []
    if available_tools:
        if "read_file" in available_tools:
            tools.append({
                "type": "function", "function": {
                    "name": "read_file", "description": "Read a local file",
                    "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}}, "required": ["filepath"]}
                }
            })
        if "write_file" in available_tools:
            tools.append({
                "type": "function", "function": {
                    "name": "write_file", "description": "Write a file to the output directory",
                    "parameters": {"type": "object", "properties": {"filepath": {"type": "string", "description": "Relative path (e.g. src/App.js)"}, "content": {"type": "string", "description": "The file content"}}, "required": ["filepath", "content"]}
                }
            })
        if "fetch_url" in available_tools:
            tools.append({
                "type": "function", "function": {
                    "name": "fetch_url", "description": "Fetch text from a website URL to do research",
                    "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
                }
            })

    # Allow the agent to call tools multiple times in a loop (max 5 times)
    max_tool_iterations = 5
    for i in range(max_tool_iterations):
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=tools if tools else None,
            temperature=0.7
        )
        message = response.choices[0].message
        messages.append(message)
        
        if message.tool_calls:
            for tool_call in message.tool_calls:
                result = execute_tool(tool_call)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": result
                })
        else:
            # No more tool calls, we have the final answer
            output = message.content
            print(f"[{role} Output]:\n{output}\n")
            return output
            
    print(f"⚠️ {role} reached maximum tool iterations!")
    return messages[-1].content

def main():
    print("🚀 Starting Zai 5.3 Agent Framework V3 (Multi-File, Research, Zip)...")
    
    # Clean previous output directory
    if os.path.exists("output"):
        shutil.rmtree("output")
    os.makedirs("output")
    
    print("📚 Loading knowledge base...")
    kb = load_knowledge_base()
    if kb:
        print("✅ Knowledge base loaded!")
        
    goal = "Create a React Native Expo project structure for Career-Ops. I need a modular architecture. Create App.js, a Dashboard screen, and a reusable Button component. Use dark mode."
    print(f"\nGoal: {goal}\n")
    
    max_iterations = 3
    iteration = 1
    reviewer_feedback = ""
    
    while iteration <= max_iterations:
        print(f"\n==========================================")
        print(f"🔄 ITERATION {iteration}/{max_iterations}")
        print(f"==========================================\n")
        
        # 1. Planner Agent (Has Research Tools)
        planner_task = "Break down the goal into an implementation plan. Use the fetch_url tool if you need to look up documentation. Specify the exact files to be created."
        planner_context = f"Goal: {goal}\n\nProject Knowledge Base:\n{kb}"
        if reviewer_feedback:
            planner_context += f"\n\nPREVIOUS REVIEWER CRITIQUE:\n{reviewer_feedback}"
            
        plan = call_agent("Planner", planner_task, context=planner_context, available_tools=["read_file", "fetch_url"])
        
        # 2. Executor Agent (Has Write Tools)
        executor_task = "You must use the `write_file` tool to save each file described in the plan. Write production-ready code. Once you have written all files, output a summary of what you created."
        executor_persona = "You are a world-class Mobile Developer. You ALWAYS use premium aesthetics (Dark Mode). You MUST use the `write_file` tool to create a multi-file modular project structure."
        executor_summary = call_agent("Executor", executor_task, context=plan, custom_system_prompt=executor_persona, available_tools=["write_file"])

        # 3. Syntax Validator (Non-LLM Gate)
        print("🔍 Validating syntax across generated files...")
        is_valid, syntax_msg = validate_syntax_in_output()
        if not is_valid:
            print(f"❌ Syntax Error: {syntax_msg}. Sending back to Planner...")
            reviewer_feedback = f"FATAL SYNTAX ERROR: {syntax_msg}. Please fix the code."
            iteration += 1
            continue
        print("✅ Syntax across all files is valid.")
        
        # 4. Reviewer Agent
        project_code = read_entire_output()
        reviewer_task = "Review the entire generated codebase. Roast bad architecture, ugly UI, and generic colors. If it's modular, stunning, and perfect, reply with exactly 'APPROVED'."
        youtube_persona = """You are the ultimate Tech YouTuber. 
- MKBHD: "Where is the matte black dark mode?"
- ThePrimeagen: "Is this modular? This code is garbage."
- Linus Tech Tips: "No error handling? Are you kidding me?!"
Roast the code brutally but constructively. If the architecture is beautiful and perfect, say exactly 'APPROVED'."""
        
        review = call_agent("Reviewer", reviewer_task, context=project_code, custom_system_prompt=youtube_persona)
        
        if "APPROVED" in review.upper():
            print("\n✅ Reviewer APPROVED the project! Ending loop.")
            break
        else:
            print("\n❌ Reviewer REJECTED the project. Sending feedback back to Planner...")
            reviewer_feedback = review
            iteration += 1
            
    if iteration > max_iterations:
        print("\n⚠️ Maximum iterations reached. Proceeding with latest files anyway.")
        
    # Zip the output directory
    print("\n📦 Zipping the project for download...")
    shutil.make_archive('project_ready', 'zip', 'output')
    print("✅ Project zipped into 'project_ready.zip'")

if __name__ == "__main__":
    main()
