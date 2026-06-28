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

def call_agent(role, task, context="", custom_system_prompt=None):
    print(f"\n--- Running {role} ---")
    if custom_system_prompt:
        system_prompt = custom_system_prompt
    else:
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
    print(f"[{role} Output]:\n{output}\n")
    return output

def main():
    print("🚀 Starting Zai 5.2 Agent Loop with YouTube Reviewer...")
    
    # 1. User Request
    goal = "Create a React Native Expo App.js file for Career-Ops. It should be a beautiful dark-mode Dashboard with Job Application Statistics, a list of Recent Applications, and Action Buttons. Output ONLY the raw App.js code."
    print(f"Goal: {goal}\n")
    
    max_iterations = 3
    iteration = 1
    reviewer_feedback = ""
    final_code = ""
    
    while iteration <= max_iterations:
        print(f"\n==========================================")
        print(f"🔄 ITERATION {iteration}/{max_iterations}")
        print(f"==========================================\n")
        
        # 2. Planner Agent
        planner_task = "Break down the goal into a step-by-step implementation plan."
        planner_context = goal
        if reviewer_feedback:
            planner_context += f"\n\nPREVIOUS REVIEWER CRITIQUE (Fix these issues):\n{reviewer_feedback}"
            
        plan = call_agent("Planner", planner_task, context=planner_context)
        
        # 3. Executor Agent
        executor_task = "Write the complete, runnable code based on the provided plan. Output ONLY code without markdown wrappers."
        code = call_agent("Executor", executor_task, context=plan)
        
        # Clean up markdown wrappers if present
        code = code.strip()
        if code.startswith("```"):
            # Find the first newline to skip the ```language part
            first_newline = code.find('\n')
            if first_newline != -1:
                code = code[first_newline+1:]
        if code.endswith("```"):
            code = code[:-3].strip()
        final_code = code

        
        # 4. Reviewer Agent (YouTube Persona)
        reviewer_task = "Review the provided code. Act like a harsh, critical YouTube tech reviewer. Roast bad practices. If the code is absolutely perfect, reply with the exact word 'APPROVED' at the end of your review. If it's bad, explain what needs fixing."
        youtube_persona = "You are a harsh, critical, and highly technical YouTube tech reviewer (like Marques Brownlee or Linus Tech Tips, but for code). You have zero tolerance for bad code, missing error handling, or poor structure. Roast the code if it's bad, but be constructive about what to fix."
        
        review = call_agent("Reviewer", reviewer_task, context=code, custom_system_prompt=youtube_persona)
        
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
