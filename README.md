# AI Agent Personal

An interactive Python AI agent that turns natural-language requests into structured, executable plans. It can calculate, retrieve and save personal memories, report system information and the current date and time, and summarize task results in a natural-language response.

## Features

- Mathematical operations: addition, subtraction, multiplication, and division
- Persistent personal memory stored locally in SQLite
- Operating-system, computer-name, and Python-version diagnostics
- Current date and time
- Multi-step plans with task dependencies and result passing
- Task status tracking, including failed tasks
- Natural-language summaries of execution results

## Requirements

- Python 3.10 or later
- An OpenAI API key

## Setup

1. Clone this repository and change into its directory.
2. Install the dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Create a `.env` file in the project directory and add your API key:

   ```dotenv
   OPENAI_API_KEY=your_api_key_here
   ```

4. Start the agent:

   ```bash
   python main.py
   ```

Enter a request when prompted. Type `exit` or `quit` to stop the agent.

## Local data and secrets

The `.env` file and `agent_memory.db` are local-only and excluded from Git. The database is created automatically and stores memories on the computer where the agent runs.
