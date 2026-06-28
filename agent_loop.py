import os
import sys
import json
import shutil
import urllib.request
import ast
import re
import math
import time
import threading
import subprocess
import concurrent.futures
from collections import deque
from difflib import SequenceMatcher
from openai import OpenAI
from sandbox import GitActionSandbox
from advanced_aci import auto_fix_all_python_files

# Configurations
api_base = os.environ.get("ZAI_API_URL", "").strip()
if not api_base:
    print("❌ ERROR: ZAI_API_URL (or OLLAMA_NGROK_URL secret) is empty. Please set your Ngrok URL in GitHub Secrets!")
    sys.exit(1)
api_key = "ollama"
MODEL_NAME = "qwen-coder-agent"
MAX_JOB_SECONDS = 19800 # 5.5 hours

client = OpenAI(
    base_url=api_base,
    api_key=api_key,
    default_headers={"ngrok-skip-browser-warning": "any"}
)

# --- V6 Component: Hierarchical Memory Condenser ---
class HierarchicalMemory:
    def __init__(self, max_short_term=3):
        self.short_term = deque(maxlen=max_short_term)
        self.long_term_lessons = []

    def add_reflection(self, reflection: str, reward: float):
        self.short_term.append({"text": reflection, "reward": reward})
        if len(self.short_term) == self.short_term.maxlen:
            self._consolidate()

    def _consolidate(self):
        print("🧠 Memory Condenser: Compressing recent reflections...")
        history = "\n".join([f"- {r['text']} (Reward: {r['reward']})" for r in self.short_term])
        prompt = f"""Condense these debugging reflections into a single, imperative rule.
        History:
        {history}
        Output only the rule (e.g., 'Always close file handles before returning.')."""
        try:
            resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            rule = resp.choices[0].message.content.strip()
            self.long_term_lessons.append(rule)
            self.short_term.clear()
        except Exception as e:
            print(f"Failed to condense memory: {str(e)}")

    def get_context_string(self) -> str:
        context = ""
        if self.long_term_lessons:
            context += "### Long-Term Lessons Learned:\n"
            context += "\n".join(f"- {rule}" for rule in self.long_term_lessons[-5:])
            context += "\n\n"
        if self.short_term:
            context += "### Recent Reflections (Verbatim):\n"
            context += "\n".join(f"- {r['text']}" for r in self.short_term)
        return context if context else "No prior memory."
        
    def to_dict(self):
        return {
            "short_term": list(self.short_term),
            "long_term_lessons": self.long_term_lessons
        }
        
    @classmethod
    def from_dict(cls, data):
        mem = cls()
        mem.short_term = deque(data.get("short_term", []), maxlen=3)
        mem.long_term_lessons = data.get("long_term_lessons", [])
        return mem

# --- Context Compaction via AST Repo Map ---
def generate_repo_map(root_dir='output', max_chars=3000):
    if not os.path.exists(root_dir): return "No code generated yet."
    lines = []
    current_chars = 0
    for dirpath, _, filenames in os.walk(root_dir):
        if any(part.startswith('.') or part in ('__pycache__', 'venv', 'node_modules') for part in dirpath.split(os.sep)):
            continue
        for fname in sorted(filenames):
            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, root_dir)
            file_block = [f"\n📄 {rel_path}:"]
            if fname.endswith('.py'):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f: tree = ast.parse(f.read(), filename=fname)
                    for node in ast.iter_child_nodes(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names: file_block.append(f"    import {alias.name}")
                        elif isinstance(node, ast.ImportFrom):
                            file_block.append(f"    from {node.module} import ...")
                    for node in ast.iter_child_nodes(tree):
                        if isinstance(node, ast.ClassDef):
                            file_block.append(f"    class {node.name}:")
                            for item in node.body:
                                if isinstance(item, ast.FunctionDef): file_block.append(f"        def {item.name}(...)")
                        elif isinstance(node, ast.FunctionDef): file_block.append(f"    def {node.name}(...)")
                except Exception: file_block.append("    [Parse Error]")
            addition = '\n'.join(file_block)
            if current_chars + len(addition) > max_chars:
                lines.append("\n... (repo map truncated to save tokens) ...")
                break
            lines.append(addition)
            current_chars += len(addition)
    return '\n'.join(lines) if lines else "No files found."

# --- ACI SEARCH/REPLACE ---
def apply_search_replace(file_path: str, diff_block: str) -> dict:
    pattern = r'<<<<<<<\s*SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>>\s*REPLACE'
    matches = list(re.finditer(pattern, diff_block, re.DOTALL))
    if not matches: return {"success": False, "error": "No valid SEARCH/REPLACE blocks found."}
    try:
        with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
    except FileNotFoundError: return {"success": False, "error": f"File not found: {file_path}"}
    blocks_applied = 0
    errors = []
    for match in matches:
        search_text = match.group(1)
        replace_text = match.group(2)
        if search_text in content:
            content = content.replace(search_text, replace_text, 1)
            blocks_applied += 1
            continue
        search_lines = search_text.splitlines(keepends=True)
        content_lines = content.splitlines(keepends=True)
        n = len(search_lines)
        if n == 0 or len(content_lines) < n:
            errors.append("Block skipped: search text empty or file too small.")
            continue
        best_ratio, best_start = 0.0, -1
        for i in range(len(content_lines) - n + 1):
            norm_search = '\n'.join(line.strip() for line in search_lines)
            norm_window = '\n'.join(line.strip() for line in content_lines[i:i+n])
            ratio = SequenceMatcher(None, norm_search, norm_window).ratio()
            if ratio > best_ratio: best_ratio, best_start = ratio, i
        if best_ratio >= 0.75:
            new_lines = content_lines[:best_start] + replace_text.splitlines(keepends=True) + content_lines[best_start + n:]
            if new_lines and not new_lines[-1].endswith('\n') and best_start + n < len(content_lines): new_lines[-1] += '\n'
            content = ''.join(new_lines)
            blocks_applied += 1
        else: errors.append(f"Failed to match block (best ratio: {best_ratio:.2f}).")
    if blocks_applied > 0:
        with open(file_path, 'w', encoding='utf-8') as f: f.write(content)
    return {"success": blocks_applied == len(matches), "applied": blocks_applied, "total": len(matches), "errors": errors}

def run_sandbox_tests():
    # V6 Zero-Token Fixer
    auto_fix_all_python_files("output")
    sandbox = GitActionSandbox(workspace_dir="./output")
    result = sandbox.run_tests()
    if result["exit_code"] == 0: return True, "Success"
    else: return False, result["stderr"]

def read_entire_output(output_dir="output"):
    if not os.path.exists(output_dir): return "No files generated yet."
    content = ""
    for root, _, files in os.walk(output_dir):
        for file in files:
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, output_dir)
            with open(filepath, 'r') as f: content += f"\n--- FILE: {rel_path} ---\n{f.read()}\n"
    return content

def execute_tool(tool_call):
    name = tool_call.function.name
    try: args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError: return "Error: Invalid JSON arguments provided."

    if name == "read_file":
        filepath = args.get("filepath", "")
        try:
            with open(filepath, 'r') as f: return f.read()
        except Exception as e: return f"Error reading file: {str(e)}"
    elif name == "write_file":
        filepath = args.get("filepath", "")
        content = args.get("content", "")
        full_path = os.path.join("output", filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        try:
            with open(full_path, 'w') as f: f.write(content)
            return f"Successfully wrote to {filepath}"
        except Exception as e: return f"Error writing file: {str(e)}"
    elif name == "edit_file":
        filepath = args.get("filepath", "")
        diff_block = args.get("diff_block", "")
        full_path = os.path.join("output", filepath)
        result = apply_search_replace(full_path, diff_block)
        if result["success"]: return f"Successfully applied {result['applied']} SEARCH/REPLACE blocks to {filepath}."
        else: return f"Failed to edit file. Errors: {result.get('errors', result.get('error'))}"
    elif name == "fetch_url":
        url = args.get("url", "")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response: return response.read().decode('utf-8')[:5000]
        except Exception as e: return f"Error fetching URL: {str(e)}"
    return f"Unknown tool: {name}"

def call_agent(role, task, context="", custom_system_prompt=None, available_tools=None, temperature=0.7):
    system_prompt = custom_system_prompt if custom_system_prompt else f"You are an expert {role}."
    user_prompt = f"Context:\n{context}\n\nTask:\n{task}"
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    tools = []
    if available_tools:
        if "read_file" in available_tools: tools.append({"type": "function", "function": {"name": "read_file", "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}}, "required": ["filepath"]}}})
        if "write_file" in available_tools: tools.append({"type": "function", "function": {"name": "write_file", "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}, "content": {"type": "string"}}, "required": ["filepath", "content"]}}})
        if "edit_file" in available_tools: tools.append({"type": "function", "function": {"name": "edit_file", "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}, "diff_block": {"type": "string"}}, "required": ["filepath", "diff_block"]}}})
        if "fetch_url" in available_tools: tools.append({"type": "function", "function": {"name": "fetch_url", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}})

    for _ in range(5):
        response = client.chat.completions.create(model=MODEL_NAME, messages=messages, tools=tools if tools else None, temperature=temperature)
        message = response.choices[0].message
        messages.append(message)
        
        # --- ADDED LOGGING ---
        print(f"\n[{role}] Agent thought:")
        if message.content:
            print(message.content)
            
        tool_calls_to_process = message.tool_calls or []
        
        # Fallback for raw JSON tool calls in content
        if not tool_calls_to_process and message.content:
            try:
                import json, uuid
                start = message.content.find('{')
                end = message.content.rfind('}')
                if start != -1 and end != -1:
                    json_str = message.content[start:end+1]
                    data = json.loads(json_str)
                    if "name" in data and "arguments" in data:
                        class FakeFunction:
                            def __init__(self, name, arguments):
                                self.name = name
                                self.arguments = json.dumps(arguments) if isinstance(arguments, dict) else arguments
                        class FakeToolCall:
                            def __init__(self, function):
                                self.id = f"call_{uuid.uuid4().hex[:8]}"
                                self.function = function
                        tool_calls_to_process = [FakeToolCall(FakeFunction(data["name"], data["arguments"]))]
            except Exception:
                pass
            
        if tool_calls_to_process:
            for tool_call in tool_calls_to_process:
                print(f"[{role}] 🛠️ Tool Call: {tool_call.function.name}(...)")
                result = execute_tool(tool_call)
                print(f"[{role}] ⬅️ Tool Result: {result[:200]}...")
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "name": tool_call.function.name, "content": result})
        else:
            return message.content
    return messages[-1].content

# --- LATS ---
class Node:
    def __init__(self, state, parent=None, reflection=""):
        self.state = state; self.parent = parent; self.children = []; self.unexpanded = []; self.visits = 0; self.value = 0.0; self.reflection = reflection

    def to_dict(self):
        return {
            "state": self.state,
            "visits": self.visits,
            "value": self.value,
            "reflection": self.reflection,
            "unexpanded": self.unexpanded,
            "children": [c.to_dict() for c in self.children]
        }

    @classmethod
    def from_dict(cls, data, parent=None):
        node = cls(state=data["state"], parent=parent, reflection=data["reflection"])
        node.visits = data["visits"]
        node.value = data["value"]
        node.unexpanded = data["unexpanded"]
        for child_data in data["children"]:
            node.children.append(cls.from_dict(child_data, parent=node))
        return node

def ucb1(node: Node, c: float = 1.41) -> float:
    if node.visits == 0: return float('inf')
    p_visits = node.parent.visits if node.parent and node.parent.visits > 0 else 1
    return (node.value / node.visits) + c * math.sqrt(math.log(p_visits) / node.visits)

def save_state():
    state = {}
    for root, _, files in os.walk("output"):
        for f in files:
            filepath = os.path.join(root, f)
            with open(filepath, 'r') as fp: state[filepath] = fp.read()
    return state

def restore_state(state):
    if os.path.exists("output"): shutil.rmtree("output")
    os.makedirs("output")
    for filepath, content in state.items():
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f: f.write(content)

# V6 Component: Async Candidate Generation
def generate_candidate_async(state_dict, plan_context, reflection):
    restore_state(state_dict) 
    prompt = f"Plan: {plan_context}\n"
    if reflection: prompt += f"\nPrevious attempt failed. Reflection: {reflection}\nFix the code."
    else: prompt += "\nWrite the initial implementation."
    # We call the agent natively
    call_agent("Executor", prompt, custom_system_prompt="You are a Developer. Use write_file/edit_file.", available_tools=["write_file", "edit_file"], temperature=0.9)
    return save_state()

def generate_candidates_parallel(state_dict, plan_context, reflection, branch_factor=2):
    print(f"🚀 Launching Async LATS Expansion ({branch_factor} branches)...")
    candidates = []
    # Note: Requires Ollama OLLAMA_NUM_PARALLEL set to > 1
    with concurrent.futures.ThreadPoolExecutor(max_workers=branch_factor) as executor:
        futures = [executor.submit(generate_candidate_async, state_dict, plan_context, reflection) for _ in range(branch_factor)]
        for future in concurrent.futures.as_completed(futures):
            try: candidates.append(future.result())
            except Exception as e: print(f"Branch failed: {str(e)}")
    return candidates

def lats_executor(memory: HierarchicalMemory, plan: str, max_iter: int = 3, branch_factor: int = 2, start_root=None):
    print(f"\n🌳 Starting LATS Execution Search (max_iter={max_iter}, branches={branch_factor})")
    os.makedirs("output", exist_ok=True)
                
    if start_root:
        root = start_root
    else:
        initial_state = save_state()
        root = Node(state=initial_state)
        root.unexpanded = generate_candidates_parallel(initial_state, plan, "", branch_factor)
        
    best_state, best_score = root.state, root.value 
    
    for iteration in range(max_iter):
        node = root
        while not node.unexpanded and node.children: node = max(node.children, key=ucb1)
        if node.unexpanded:
            child = Node(state=node.unexpanded.pop(), parent=node)
            node.children.append(child)
            node = child
            
        restore_state(node.state)
        is_valid, sandbox_error = run_sandbox_tests()
        reward = 1.0 if is_valid else 0.0
        node.visits, node.value = 1, reward
        
        if reward > best_score: best_score, best_state = reward, node.state
        print(f"📊 LATS Iteration {iteration+1}: reward={reward}")
        
        if reward < 1.0:
            print("🧠 Reflexion on failed branch...")
            reflection_task = f"Sandbox failed:\n{sandbox_error}\nAnalyze why and how to fix it."
            context = f"Current Code:\n{read_entire_output()}\n\nMemory:\n{memory.get_context_string()}"
            node.reflection = call_agent("Reflector", reflection_task, context=context, custom_system_prompt="You are a debugging AI.")
            memory.add_reflection(node.reflection, reward)
            node.unexpanded = generate_candidates_parallel(node.state, plan, node.reflection, branch_factor)
            
        back_node = node.parent
        while back_node:
            back_node.visits += 1; back_node.value += reward; back_node = back_node.parent
        if best_score >= 1.0: break 

    restore_state(best_state)
    return best_state, best_score, root

# --- V6 Component: Watchdog Daemon ---
class AgentWatchdog:
    def __init__(self, task, plan, memory, get_root_func, timeout_seconds=MAX_JOB_SECONDS):
        self.task = task
        self.plan = plan
        self.memory = memory
        self.get_root_func = get_root_func
        self.timeout = timeout_seconds
        self.start_time = time.time()

    def start(self):
        def monitor():
            while True:
                if time.time() - self.start_time > self.timeout:
                    self._checkpoint_and_resurrect()
                time.sleep(60)
        daemon = threading.Thread(target=monitor, daemon=True)
        daemon.start()

    def _checkpoint_and_resurrect(self):
        print("⏰ WATCHDOG: Approaching GitHub Timeout. Initiating resurrection...")
        root_node = self.get_root_func()
        state = {
            "task": self.task,
            "plan": self.plan,
            "memory": self.memory.to_dict(),
            "tree": root_node.to_dict() if root_node else None
        }
        with open("checkpoint.json", "w") as f: json.dump(state, f)
        
        # Commit to Git on a checkpoint branch
        subprocess.run(["git", "config", "user.name", "Agent Watchdog"])
        subprocess.run(["git", "config", "user.email", "bot@users.noreply.github.com"])
        subprocess.run(["git", "checkout", "-b", "auto-checkpoint"])
        subprocess.run(["git", "add", "checkpoint.json"])
        subprocess.run(["git", "commit", "-m", "Auto-checkpoint before timeout"])
        subprocess.run(["git", "push", "--force", "origin", "auto-checkpoint"])
        
        # Trigger new workflow run via GitHub CLI
        subprocess.run([
            "gh", "workflow", "run", "agent.yml", 
            "-f", "task=RESUME", 
            "-r", "auto-checkpoint"
        ])
        print("✅ Resurrection triggered. Killing current process.")
        os._exit(0)

# --- Entrypoint ---
def main():
    print("🚀 Starting Zai 5.3 Agent Framework V6 Elite (GitHub Actions)...")
    
    task = sys.argv[1] if len(sys.argv) > 1 else "Create a React Native project structure"
    memory = HierarchicalMemory()
    root_node = None
    plan = ""
    
    if task == "RESUME":
        print("🔄 RESUMING FROM CHECKPOINT...")
        subprocess.run(["git", "pull", "origin", "auto-checkpoint"])
        with open("checkpoint.json", "r") as f: state = json.load(f)
        memory = HierarchicalMemory.from_dict(state["memory"])
        task = state["task"]
        plan = state["plan"]
        if state["tree"]:
            root_node = Node.from_dict(state["tree"])
            restore_state(root_node.state)
    else:
        if os.path.exists("output"): shutil.rmtree("output")
        os.makedirs("output")
        repo_map = generate_repo_map("output")
        planner_context = f"Goal: {task}\n\nRepository Map:\n{repo_map}"
        plan = call_agent("Planner", "Break down the goal into an implementation plan. Specify the exact files to be created.", context=planner_context, available_tools=["read_file", "fetch_url"])

    # Define a closure so the watchdog can fetch the latest root_node
    def get_current_root(): return root_node

    # Start Watchdog
    watchdog = AgentWatchdog(task, plan, memory, get_current_root)
    watchdog.start()

    # Run LATS Search
    best_state, score, root_node = lats_executor(memory, plan, max_iter=4, branch_factor=2, start_root=root_node)
    
    project_code = read_entire_output()
    review = call_agent("Reviewer", "Review the entire generated codebase. If the architecture is beautiful and perfect, say exactly 'APPROVED'.", context=project_code, custom_system_prompt="You are MKBHD and ThePrimeagen. Roast bad code. Only say 'APPROVED' if it is flawless.")
    
    if "APPROVED" in review.upper(): print("\n✅ Reviewer APPROVED the project!")
    else: print("\n❌ Reviewer REJECTED the project.")
        
if __name__ == "__main__":
    main()
