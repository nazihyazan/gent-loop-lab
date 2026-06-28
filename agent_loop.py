import os
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

def call_agent(role, task, context=""):
    print(f"\n--- Running {role} ---")
    system_prompt = f"You are an expert {role}. Provide output based on the task."
    user_prompt = f"Context: {context}\n\nTask: {task}"
    
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7
    )
    
    output = response.choices[0].message.content
    print(f"[{role} Output]:\n{output}")
    return output

def main():
    print("🚀 Starting Zai 5.2 Agent Loop...")
    
    # 1. User Request
    goal = "Create a beautiful Web Application using Python and the Streamlit library. The app should be a 'Personal Task Manager' (To-Do List) where users can add tasks, mark them as done, and delete them. Make the UI look professional."
    print(f"Goal: {goal}\n")
    
    # 2. Planner Agent
    planner_task = "Break down the goal into a step-by-step implementation plan."
    plan = call_agent("Planner", planner_task, context=goal)
    
    # 3. Executor Agent
    executor_task = "Write the complete, runnable Python code based on the provided plan. Output ONLY code without markdown wrappers like ```python if possible, or just standard code."
    code = call_agent("Executor", executor_task, context=plan)
    
    # Clean up the output if the model wrapped it in markdown
    if code.startswith("```python"):
        code = code[9:]
    if code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    
    # 4. Reviewer Agent (Optional)
    reviewer_task = "Review the provided code for any bugs or improvements. Give a short summary."
    review = call_agent("Reviewer", reviewer_task, context=code)
    
    # Save the artifact
    with open("final_code.py", "w") as f:
        f.write(code.strip())
    print("\n✅ Loop completed. Artifact saved as final_code.py")

if __name__ == "__main__":
    main()
