import os
import json
import shutil
import urllib.request
import subprocess
from openai import OpenAI

# The Ngrok URL provided by Kaggle, passed via GitHub Secrets
api_base = os.environ.get("ZAI_API_URL", "http://localhost:11434/v1")
api_key = "ollama"

client = OpenAI(
    base_url=api_base,
    api_key=api_key,
    default_headers={"ngrok-skip-browser-warning": "any"}
)

# The model name loaded in Kaggle
MODEL_NAME = "qwen2.5:14b"

def load_knowledge_base(directory="knowledge"):
    """Reads all markdown and text files in the knowledge directory."""
    kb_content = ""
    if not os.path.exists(directory):
        return kb_content
        
    for filename in os.listdir(directory):
        if filename.endswith(".md") or filename.endswith(".txt"):
            filepath = os.path.join(directory, filename)
            with open(filepath, 'r') as f:
                kb_content += f"\n--- {filename} ---\n{f.read()}\n"
    return kb_content

def load_episodic_memory(memory_file="reflection.jsonl"):
    """Loads past failures and reflections so the agent doesn't repeat mistakes."""
    if not os.path.exists(memory_file):
        return "No past memories."
    try:
        memories = []
        with open(memory_file, 'r') as f:
            for line in f.readlines()[-5:]: # Get last 5 memories
                memories.append(json.loads(line))
        
        memory_str = "PAST MISTAKES TO AVOID:\n"
        for m in memories:
            memory_str += f"- Failed at: {m['error'][:100]}... | Lesson: {m['reflection']}\n"
        return memory_str
    except Exception:
        return "Memory corrupted."

def save_episodic_memory(error, reflection, memory_file="reflection.jsonl"):
    """Saves a learned lesson to episodic memory."""
    memory = {
        "error": error,
        "reflection": reflection
    }
    with open(memory_file, 'a') as f:
        f.write(json.dumps(memory) + "\n")

def run_sandbox_tests(output_dir="output"):
    """Executes a real syntax check via subprocess to capture actual error logs (Reflexion)."""
    if not os.path.exists(output_dir):
        return True, "No files to check."
        
    for root, _, files in os.walk(output_dir):
        for file in files:
            filepath = os.path.join(root, file)
            # Try to run node syntax check if it's JS
            if file.endswith(('.js', '.jsx')):
                try:
                    result = subprocess.run(["node", "--check", filepath], capture_output=True, text=True, timeout=10)
                    if result.returncode != 0:
                        return False, f"Node Syntax Error in {file}:\n{result.stderr}"
                except FileNotFoundError:
                    pass # Node not installed, fallback to basic
                    
            # Try python compile check if it's Python
            elif file.endswith('.py'):
                try:
                    result = subprocess.run(["python3", "-m", "py_compile", filepath], capture_output=True, text=True, timeout=10)
                    if result.returncode != 0:
                        return False, f"Python Syntax Error in {file}:\n{result.stderr}"
                except FileNotFoundError:
                    pass

    return True, "All files passed sandbox execution checks."

def read_entire_output(output_dir="output"):
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
                return response.read().decode('utf-8')[:5000]
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
            tools.append({"type": "function", "function": {"name": "read_file", "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}}, "required": ["filepath"]}}})
        if "write_file" in available_tools:
            tools.append({"type": "function", "function": {"name": "write_file", "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}, "content": {"type": "string"}}, "required": ["filepath", "content"]}}})
        if "fetch_url" in available_tools:
            tools.append({"type": "function", "function": {"name": "fetch_url", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}})

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
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "name": tool_call.function.name, "content": result})
        else:
            output = message.content
            print(f"[{role} Output]:\n{output[:500]}...\n")
            return output
            
    return messages[-1].content

def main():
    print("🚀 Starting Zai 5.3 Agent Framework V4 (Reflexion, Episodic Memory)...")
    
    if os.path.exists("output"):
        shutil.rmtree("output")
    os.makedirs("output")
    
    kb = load_knowledge_base()
    memory = load_episodic_memory()
    
    goal = "Create a React Native Expo project structure for Career-Ops. Create App.js, a Dashboard screen, and a reusable Button component. Use dark mode."
    print(f"\nGoal: {goal}\n")
    
    max_iterations = 3
    iteration = 1
    reflection_context = ""
    
    while iteration <= max_iterations:
        print(f"\n==========================================")
        print(f"🔄 ITERATION {iteration}/{max_iterations}")
        print(f"==========================================\n")
        
        # 1. Planner Agent
        planner_task = "Break down the goal into an implementation plan. Specify the exact files to be created."
        planner_context = f"Goal: {goal}\n\nKnowledge Base:\n{kb}\n\nEpisodic Memory:\n{memory}"
        if reflection_context:
            planner_context += f"\n\nREFLEXION FEEDBACK FROM LAST ATTEMPT:\n{reflection_context}"
            
        plan = call_agent("Planner", planner_task, context=planner_context, available_tools=["read_file", "fetch_url"])
        
        # 2. Executor Agent
        executor_task = "Use the `write_file` tool to save each file described in the plan. Write production-ready code."
        executor_persona = "You are a world-class Developer. You ALWAYS use `write_file` to structure projects."
        executor_summary = call_agent("Executor", executor_task, context=plan, custom_system_prompt=executor_persona, available_tools=["write_file"])

        # 3. Sandbox Runner (Execution)
        print("🔍 Running Sandbox Execution Verification...")
        is_valid, sandbox_error = run_sandbox_tests()
        
        if not is_valid:
            print(f"❌ Sandbox Execution Failed: {sandbox_error}")
            # 4a. Reflection Agent
            print("🧠 Initiating Reflexion Loop...")
            reflection_task = f"The sandbox execution crashed with this real terminal error:\n{sandbox_error}\nAnalyze why this failed, and give explicit instructions on how to fix it."
            reflection = call_agent("Reflector", reflection_task, context=read_entire_output(), custom_system_prompt="You are a brilliant debugging AI.")
            
            save_episodic_memory(sandbox_error, reflection)
            reflection_context = reflection
            iteration += 1
            continue
            
        print("✅ Sandbox execution passed!")
        
        # 4b. Reviewer Agent (Architecture Check)
        project_code = read_entire_output()
        reviewer_task = "Review the entire generated codebase. If the architecture is beautiful and perfect, say exactly 'APPROVED'."
        youtube_persona = "You are MKBHD and ThePrimeagen. Roast bad code. Only say 'APPROVED' if it is flawless."
        review = call_agent("Reviewer", reviewer_task, context=project_code, custom_system_prompt=youtube_persona)
        
        if "APPROVED" in review.upper():
            print("\n✅ Reviewer APPROVED the project! Ending loop.")
            break
        else:
            print("\n❌ Reviewer REJECTED the project.")
            reflection_context = f"Reviewer Feedback: {review}"
            iteration += 1
            
    if iteration > max_iterations:
        print("\n⚠️ Maximum iterations reached. Proceeding with latest files.")
        
    print("\n📦 Zipping the project for download...")
    shutil.make_archive('project_ready', 'zip', 'output')
    print("✅ Project zipped into 'project_ready.zip'")

if __name__ == "__main__":
    main()
