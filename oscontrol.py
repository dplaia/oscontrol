import pexpect
import sys
from typing import Optional
from pydantic_ai.models.gemini import GeminiModel
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from dataclasses import dataclass
import asyncio

class LLMAgent:
    def __init__(self, llm_callback: callable):
        self.child = None
        self.llm = llm_callback  # Your LLM function (local or API)
        self.output_buffer = ""
        
    def _analyze_output(self, output: str) -> dict:
        """
        Use LLM to analyze terminal output and return:
        {
            "action": "prompt_user|send_input|wait|error",
            "message": "Password required...",  # LLM's context-aware message
            "input_type": "password|yesno|text",  # If action=prompt_user
            "suggested_input": "mypassword"  # Optional LLM suggestion
        }
        """
        # Example LLM prompt (customize for your model):
        llm_prompt = f"""Analyze this terminal output:
        {output}
        
        Should the user be prompted for input? Respond with JSON only:
        - "action": "prompt_user" if input is needed
        - "input_type": "password/text/yesno"
        - "message": Clear instruction for the user
        - "suggested_input": Optional default value"""
        
        return self.llm(llm_prompt)  # Implement your LLM call

    def _handle_output(self):
        """Process terminal output using LLM guidance"""
        analysis = self._analyze_output(self.output_buffer)
        
        if analysis["action"] == "prompt_user":
            prompt_msg = f"\n[AGENT] {analysis['message']}"
            
            if analysis.get("input_type") == "password":
                import getpass
                user_input = getpass.getpass(prompt_msg + ": ")
            else:
                user_input = input(prompt_msg + ": ")
                
            self.child.sendline(user_input.strip())
            self.output_buffer = ""  # Reset buffer after interaction
            
        elif analysis["action"] == "send_input":
            self.child.sendline(analysis["suggested_input"])
            self.output_buffer = ""
            
        elif analysis["action"] == "error":
            print(f"\n[AGENT] Error detected: {analysis['message']}")
            # Add error recovery logic here

    def run_command(self, command: str):
        """Execute command with dynamic LLM-guided interaction"""
        self.child = pexpect.spawn(command, encoding='utf-8', timeout=10)
        
        while True:
            try:
                # Read output incrementally
                self.child.expect([r'.+', pexpect.EOF, pexpect.TIMEOUT], timeout=1)
                self.output_buffer += self.child.before
                
                # Process output through LLM when buffer has content
                if self.output_buffer.strip():
                    self._handle_output()
                    
            except pexpect.EOF:
                print("\n[AGENT] Command execution completed")
                break
            except pexpect.TIMEOUT:
                # Handle timeouts as normal pauses
                continue

flash_thinking_model = "gemini-2.0-flash-thinking-exp-01-21"
flash2_model = "gemini-2.0-flash-exp"
flash1_model = "gemini-1.5-flash"
model = GeminiModel(flash2_model)

class AgentResult(BaseModel):
    llm_response: str = Field(description="The LLM's response to the user's input.")

@dataclass
class AgentDeps:
    command: str = Field(description="The command to execute.")

agent = Agent(
    model,
    deps_type=AgentDeps,  
    result_type=AgentResult,
    system_prompt="""
    You are an agent that analyzes the output of a Linux terminal session.
    Your goal is to analyze the output of a Linux terminal session and provide guidance to the user based on the output.
    """
)

async def run_agent():
    result = await agent.run('ssh user@example.com', deps=AgentDeps(command='ssh user@example.com'))
    return result

if __name__ == "__main__":
    result = asyncio.run(run_agent())
