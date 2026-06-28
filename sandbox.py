import subprocess
import os

class GitActionSandbox:
    def __init__(self, workspace_dir: str = "output"):
        self.workspace_dir = os.path.abspath(workspace_dir)
        os.makedirs(self.workspace_dir, exist_ok=True)

    def run_tests(self) -> dict:
        """
        Runs code inside an isolated Docker container natively supported by GH Actions runner.
        Mounts the local workspace into the container.
        Returns stdout and stderr for the Reflexion loop.
        """
        abs_path = self.workspace_dir
        
        # Check if Node is required or Python
        # In a real dynamic agent, we would detect the file types.
        # For our use case, we test python syntax or node syntax generic checks.
        
        # Example of a generic Python + Node tester container
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{abs_path}:/sandbox",
            "-w", "/sandbox",
            "python:3.11-slim",
            "sh", "-c", "python3 -m compileall . 2>&1"
        ]
        
        try:
            result = subprocess.run(
                docker_cmd, 
                capture_output=True, 
                text=True, 
                timeout=120
            )
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout[-3000:], 
                "stderr": result.stderr[-3000:]
            }
        except subprocess.TimeoutExpired:
            return {"exit_code": -1, "stdout": "", "stderr": "Test execution timed out after 120s."}
        except Exception as e:
            return {"exit_code": -1, "stdout": "", "stderr": str(e)}
