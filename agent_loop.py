import os
import json
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

def validate_syntax(code):
    """Basic non-LLM check to ensure brackets are matched."""
    brackets = {'{': '}', '[': ']', '(': ')'}
    stack = []
    
    for char in code:
        if char in brackets:
            stack.append(char)
        elif char in brackets.values():
            if not stack:
                return False, "Found closing bracket with no matching opening bracket."
            last = stack.pop()
            if brackets[last] != char:
                return False, "Mismatched brackets found."
                
    if stack:
        return False, "Unclosed brackets found."
    return True, "Syntax valid."

def call_agent(role, task, context="", custom_system_prompt=None, use_tools=False):
    print(f"\n--- Running {role} ---")
    if custom_system_prompt:
        system_prompt = custom_system_prompt
    else:
        system_prompt = f"You are an expert {role}. Provide output based on the task."
        
    user_prompt = f"Context: {context}\n\nTask: {task}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    tools = []
    if use_tools:
        tools = [{
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a local file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filepath": {"type": "string", "description": "The path to the file"}
                    },
                    "required": ["filepath"]
                }
            }
        }]
    
    # First call
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        tools=tools if tools else None,
        temperature=0.7
    )
    
    message = response.choices[0].message
    
    # Handle Tool Calling
    if message.tool_calls:
        for tool_call in message.tool_calls:
            if tool_call.function.name == "read_file":
                args = json.loads(tool_call.function.arguments)
                filepath = args.get("filepath", "")
                print(f"🛠️ Agent called tool: read_file('{filepath}')")
                
                try:
                    with open(filepath, 'r') as f:
                        file_content = f.read()
                except Exception as e:
                    file_content = f"Error reading file: {str(e)}"
                    
                # Append the function result to messages
                messages.append(message)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": "read_file",
                    "content": file_content
                })
                
                # Second call to get the final response after reading the file
                print("🧠 Agent is digesting the file context...")
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    temperature=0.7
                )
                message = response.choices[0].message

    output = message.content
    print(f"[{role} Output]:\n{output}\n")
    return output

def main():
    print("🚀 Starting Zai 5.2 Agent Loop with Tools and RAG...")
    
    # 1. Load Knowledge Base (RAG-lite)
    print("📚 Loading knowledge base...")
    kb = load_knowledge_base()
    if kb:
        print("✅ Knowledge base loaded!")
    else:
        print("⚠️ No knowledge base files found.")
        
    # 2. User Request
    goal = "Create a React Native Expo App.js file for Career-Ops. It should be a beautiful dark-mode Dashboard with Job Application Statistics, a list of Recent Applications, and Action Buttons. Output ONLY the raw App.js code."
    print(f"\nGoal: {goal}\n")
    
    max_iterations = 3
    iteration = 1
    reviewer_feedback = ""
    final_code = ""
    
    while iteration <= max_iterations:
        print(f"\n==========================================")
        print(f"🔄 ITERATION {iteration}/{max_iterations}")
        print(f"==========================================\n")
        
        # 3. Planner Agent (With Tools and Knowledge Base)
        planner_task = "Break down the goal into a step-by-step implementation plan. If you need to read existing files like package.json, use your tools."
        planner_context = goal
        
        if kb:
            planner_context += f"\n\nPROJECT KNOWLEDGE BASE:\n{kb}"
            
        if reviewer_feedback:
            planner_context += f"\n\nPREVIOUS REVIEWER CRITIQUE (Fix these issues):\n{reviewer_feedback}"
            
        plan = call_agent("Planner", planner_task, context=planner_context, use_tools=True)
        
        # 4. Executor Agent
        executor_task = "Write the complete, runnable code based on the provided plan. Output ONLY code without markdown wrappers."
        executor_persona = "You are a world-class Mobile Developer and UI/UX Designer. You never write basic code. You ALWAYS use premium, modern aesthetics (Deep Dark Mode, smooth gradients, subtle borders, perfect padding, beautiful typography). Make the UI look like a billion-dollar startup. Never use plain red/blue/green colors. Use harmonious, curated color palettes."
        code = call_agent("Executor", executor_task, context=plan, custom_system_prompt=executor_persona)
        
        # Clean up markdown wrappers if present
        code = code.strip()
        if code.startswith("```"):
            first_newline = code.find('\n')
            if first_newline != -1:
                code = code[first_newline+1:]
        if code.endswith("```"):
            code = code[:-3].strip()
        final_code = code

        # 5. Syntax Validator (Non-LLM Gate)
        print("🔍 Validating syntax...")
        is_valid, syntax_msg = validate_syntax(final_code)
        if not is_valid:
            print(f"❌ Syntax Error: {syntax_msg}. Sending back to Planner...")
            reviewer_feedback = f"FATAL SYNTAX ERROR: {syntax_msg}. Please ensure all brackets are matched."
            iteration += 1
            continue
        print("✅ Syntax is valid.")
        
        # 6. Reviewer Agent (YouTube Persona)
        reviewer_task = "Review the provided code. Act like a harsh, critical YouTube tech reviewer. Roast bad practices and ugly designs. If the code is absolutely perfect AND visually stunning, reply with the exact word 'APPROVED' at the end of your review. If it's bad, explain what needs fixing."
        youtube_persona = """You are the ultimate Tech & Code YouTuber, combining the critical perspectives of the top 5000 tech creators. 
Channel the energy of:
- ThePrimeagen: "Is this blazingly fast? Why is this not in Rust? This code is garbage, the time complexity is trash."
- MKBHD: "So I've been looking at this code for a week. The aesthetic isn't crispy. Where is the matte black dark mode? It feels cheap."
- Fireship: "Here we have a classic dumpster fire of a React component. It's going to cause a memory leak that destroys your browser."
- Linus Tech Tips: "This architecture is like dropping a $2000 GPU. No error handling? Are you kidding me?!"
- Theo (t3.gg): "Why are you doing state management like it's 2018? This is terrible developer experience."

You have ZERO tolerance for ugly UI, basic styling, missing error handling, or bloated code. Roast the code brutally but constructively. If it uses generic colors, roast it. If it's absolutely perfect and beautiful, say exactly 'APPROVED'."""
        
        review = call_agent("Reviewer", reviewer_task, context=final_code, custom_system_prompt=youtube_persona)
        
        if "APPROVED" in review.upper():
            print("\n✅ Reviewer APPROVED the code! Ending loop.")
            break
        else:
            print("\n❌ Reviewer REJECTED the code. Sending feedback back to Planner...")
            reviewer_feedback = review
            iteration += 1
            
    if iteration > max_iterations:
        print("\n⚠️ Maximum iterations reached. Saving the latest code anyway.")
        
    # Save the artifact
    with open("App.js", "w") as f:
        f.write(final_code)
    print("\n✅ Artifact saved as App.js")

if __name__ == "__main__":
    main()
