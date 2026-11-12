
import os
import json
import sqlite3
import platform
import socket
import sys

from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI


# =====================================================
# 1. CONFIGURATION
# =====================================================

load_dotenv()

client = OpenAI()

MODEL = "gpt-4.1-mini"
DATABASE = "agent_memory.db"


# =====================================================
# 2. SQLITE LONG-TERM MEMORY
# =====================================================

def initialize_memory():

    with sqlite3.connect(DATABASE) as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_key TEXT UNIQUE NOT NULL,
                memory_value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def save_memory(key, value):

    key = key.strip().lower()

    with sqlite3.connect(DATABASE) as conn:

        conn.execute("""
            INSERT INTO memories (memory_key, memory_value)
            VALUES (?, ?)

            ON CONFLICT(memory_key)
            DO UPDATE SET
                memory_value = excluded.memory_value
        """, (key, str(value)))

    return f"Successfully saved {key} in memory."


def get_memory(key):

    key = key.strip().lower()

    with sqlite3.connect(DATABASE) as conn:

        cursor = conn.execute(
            "SELECT memory_value FROM memories WHERE memory_key = ?",
            (key,)
        )

        result = cursor.fetchone()

    if result:
        return result[0]

    return f"No saved memory found for '{key}'."


def get_all_memories():

    with sqlite3.connect(DATABASE) as conn:

        cursor = conn.execute("""
            SELECT memory_key, memory_value, created_at
            FROM memories
            ORDER BY id
        """)

        records = cursor.fetchall()

    return [
        {
            "key": row[0],
            "value": row[1],
            "created_at": row[2]
        }
        for row in records
    ]


initialize_memory()


# =====================================================
# 3. PYTHON TOOLS
# =====================================================

def calculator(a, b, operation):

    if operation == "add":
        return a + b

    elif operation == "subtract":
        return a - b

    elif operation == "multiply":
        return a * b

    elif operation == "divide":

        if b == 0:
            raise ZeroDivisionError("Cannot divide by zero.")

        return a / b

    else:
        raise ValueError(f"Unsupported operation: {operation}")


def get_system_datetime():

    return datetime.now().strftime(
        "%d-%m-%Y %I:%M:%S %p"
    )


def get_system_information():

    return {
        "operating_system": platform.system(),
        "os_version": platform.version(),
        "computer_name": socket.gethostname(),
        "python_version": sys.version,
        "current_directory": os.getcwd()
    }


# =====================================================
# 4. TOOL REGISTRY
# =====================================================

available_functions = {

    "calculator": calculator,

    "get_system_datetime": get_system_datetime,

    "get_system_information": get_system_information,

    "save_memory": save_memory,

    "get_memory": get_memory
}


# =====================================================
# 5. STRUCTURED PLANNING SCHEMA
# =====================================================

nullable_number = {
    "anyOf": [
        {"type": "number"},
        {"type": "null"}
    ]
}

nullable_integer = {
    "anyOf": [
        {"type": "integer"},
        {"type": "null"}
    ]
}


plan_schema = {

    "type": "object",

    "properties": {

        "goal": {
            "type": "string"
        },

        "tasks": {

            "type": "array",

            "items": {

                "type": "object",

                "properties": {

                    "id": {
                        "type": "integer"
                    },

                    "description": {
                        "type": "string"
                    },

                    "tool": {
                        "type": "string",
                        "enum": [
                            "calculator",
                            "get_system_datetime",
                            "get_system_information",
                            "save_memory",
                            "get_memory",
                            "generate_response"
                        ]
                    },

                    "arguments": {

                        "type": "object",

                        "properties": {

                            "a": nullable_number,

                            "b": nullable_number,

                            "operation": {
                                "type": "string",
                                "enum": [
                                    "add",
                                    "subtract",
                                    "multiply",
                                    "divide",
                                    "none"
                                ]
                            },

                            "key": {
                                "type": "string"
                            },

                            "value": {
                                "type": "string"
                            },

                            "a_from_task": nullable_integer,

                            "b_from_task": nullable_integer

                        },

                        "required": [
                            "a",
                            "b",
                            "operation",
                            "key",
                            "value",
                            "a_from_task",
                            "b_from_task"
                        ],

                        "additionalProperties": False
                    },

                    "depends_on": {

                        "type": "array",

                        "items": {
                            "type": "integer"
                        }
                    },

                    "status": {

                        "type": "string",

                        "enum": [
                            "pending",
                            "running",
                            "completed",
                            "failed"
                        ]
                    }
                },

                "required": [
                    "id",
                    "description",
                    "tool",
                    "arguments",
                    "depends_on",
                    "status"
                ],

                "additionalProperties": False
            }
        }
    },

    "required": [
        "goal",
        "tasks"
    ],

    "additionalProperties": False
}


# =====================================================
# 6. AI PLANNING ENGINE
# =====================================================

def create_structured_plan(user_goal):

    planning_prompt = f"""
You are an AI Agent Planning Engine.

Convert the user's request into an executable JSON plan.

AVAILABLE TOOLS:

1. calculator
   Arguments: a, b, operation

2. get_system_datetime
   No arguments.

3. get_system_information
   No arguments.

4. save_memory
   Arguments: key, value

5. get_memory
   Arguments: key

6. generate_response
   Generates the final natural-language response from task results.

PLANNING RULES:

1. Break the user's goal into small executable tasks.

2. Assign a unique sequential integer ID to every task.

3. Select the correct tool for every task.

4. Put all tool parameters inside the arguments object.

5. Use null for unused numeric arguments and task references.

6. Use an empty string for unused key and value fields.

7. Use "none" for operation when the task is not a calculation.

8. If a task requires another task's result, add that task ID
   to depends_on.

9. For dynamic calculator inputs, use a_from_task or b_from_task.
   The referenced task must be included in depends_on.

10. For example:

    If Task 1 retrieves age from memory and Task 2 adds 5:

    Task 1:
        tool = get_memory
        key = age

    Task 2:
        tool = calculator
        a = null
        b = 5
        operation = add
        a_from_task = 1
        depends_on = [1]

11. Use direct numbers in calculator arguments when available.

12. Never invent missing personal information.

13. Add a final generate_response task to provide the user
    with a natural-language answer.

14. The final response task must depend on all preceding
    tasks whose results are needed.

15. Tasks must be arranged in dependency order.

16. Initial status of every task must be pending.

17. Do not execute any task. Only create the plan.

USER REQUEST:

{user_goal}
"""

    response = client.responses.create(

        model=MODEL,

        input=planning_prompt,

        text={

            "format": {

                "type": "json_schema",

                "name": "execution_plan",

                "strict": True,

                "schema": plan_schema
            }
        }
    )

    if not response.output_text:
        raise ValueError("Planner returned an empty response.")

    return json.loads(response.output_text)


# =====================================================
# 7. HELPER: CONVERT NUMERIC RESULTS
# =====================================================

def convert_to_number(value):

    if isinstance(value, bool):
        raise ValueError("Boolean cannot be used as a number.")

    if isinstance(value, (int, float)):
        return value

    try:

        number = float(value)

        if number.is_integer():
            return int(number)

        return number

    except (ValueError, TypeError):

        raise ValueError(
            f"Task result '{value}' is not numeric."
        )


# =====================================================
# 8. AI RESPONSE GENERATOR
# =====================================================

def generate_response(user_goal, task_results):

    prompt = f"""
You are an intelligent AI Agent.

USER REQUEST:
{user_goal}

EXECUTION RESULTS:
{json.dumps(task_results, indent=4, default=str)}

INSTRUCTIONS:

1. Answer the user's original request.
2. Use the actual execution results.
3. Explain calculations clearly.
4. Distinguish current values from calculated values.
5. Never invent information.
6. If a requested operation was not completed, explain that.
7. Keep the response clear and useful.
"""

    response = client.responses.create(

        model=MODEL,

        input=prompt
    )

    return response.output_text


# =====================================================
# 9. TASK EXECUTION ENGINE
# =====================================================

def execute_task(task, task_results, user_goal):

    tool_name = task["tool"]

    arguments = task["arguments"]

    # -------------------------------------------------
    # Check dependencies
    # -------------------------------------------------

    for dependency_id in task["depends_on"]:

        if dependency_id not in task_results:

            raise Exception(
                f"Dependency Task {dependency_id} is not completed."
            )

    # -------------------------------------------------
    # Calculator
    # -------------------------------------------------

    if tool_name == "calculator":

        a = arguments["a"]
        b = arguments["b"]

        # Resolve first input dynamically
        if arguments["a_from_task"] is not None:

            source_id = arguments["a_from_task"]

            if source_id not in task["depends_on"]:
                raise ValueError(
                    "First input source must be a declared dependency."
                )

            a = task_results[source_id]

        # Resolve second input dynamically
        if arguments["b_from_task"] is not None:

            source_id = arguments["b_from_task"]

            if source_id not in task["depends_on"]:
                raise ValueError(
                    "Second input source must be a declared dependency."
                )

            b = task_results[source_id]

        if a is None or b is None:
            raise ValueError("Calculator inputs are missing.")

        a = convert_to_number(a)
        b = convert_to_number(b)

        result = calculator(
            a,
            b,
            arguments["operation"]
        )

    # -------------------------------------------------
    # System date and time
    # -------------------------------------------------

    elif tool_name == "get_system_datetime":

        result = get_system_datetime()

    # -------------------------------------------------
    # System information
    # -------------------------------------------------

    elif tool_name == "get_system_information":

        result = get_system_information()

    # -------------------------------------------------
    # Save memory
    # -------------------------------------------------

    elif tool_name == "save_memory":

        if not arguments["key"] or not arguments["value"]:
            raise ValueError("Memory key and value are required.")

        result = save_memory(
            arguments["key"],
            arguments["value"]
        )

    # -------------------------------------------------
    # Retrieve memory
    # -------------------------------------------------

    elif tool_name == "get_memory":

        if not arguments["key"]:
            raise ValueError("Memory key is required.")

        result = get_memory(
            arguments["key"]
        )

        if result.startswith("No saved memory found"):
            raise ValueError(result)

    # -------------------------------------------------
    # Generate final AI response
    # -------------------------------------------------

    elif tool_name == "generate_response":

        result = generate_response(
            user_goal,
            task_results
        )

    else:

        raise ValueError(
            f"Unsupported tool: {tool_name}"
        )

    return {
        "status": "completed",
        "result": result
    }


# =====================================================
# 10. COMPLETE WORKFLOW EXECUTOR
# =====================================================

def execute_plan(plan):

    task_results = {}

    completed_ids = set()

    task_ids = [
        task["id"]
        for task in plan["tasks"]
    ]

    if len(task_ids) != len(set(task_ids)):
        raise ValueError("Duplicate task IDs found.")

    valid_ids = set(task_ids)

    for task in plan["tasks"]:

        task_id = task["id"]

        print(
            f"\nExecuting Task {task_id}: "
            f"{task['description']}"
        )

        # Check that dependencies exist
        for dependency_id in task["depends_on"]:

            if dependency_id not in valid_ids:
                raise ValueError(
                    f"Unknown dependency: {dependency_id}"
                )

        # Do not execute tasks whose dependencies failed
        if not set(task["depends_on"]).issubset(completed_ids):

            task["status"] = "failed"

            print("Status: failed")
            print("Reason: A dependency was not completed.")

            continue

        task["status"] = "running"

        try:

            execution = execute_task(
                task,
                task_results,
                plan["goal"]
            )

            task["status"] = execution["status"]

            if task["status"] == "completed":

                task_results[task_id] = execution["result"]

                completed_ids.add(task_id)

                print("Status: completed")
                print("Result:", execution["result"])

            else:

                print("Status: failed")

        except Exception as error:

            task["status"] = "failed"

            print("Status: failed")
            print("Error:", str(error))

    return {

        "plan": plan,

        "results": task_results,

        "completed_tasks": len(completed_ids),

        "failed_tasks": sum(
            1 for task in plan["tasks"]
            if task["status"] == "failed"
        )
    }


# =====================================================
# 11. INTERACTIVE RUNTIME AGENT
# =====================================================

def run_interactive_agent():

    print("\n======================================")
    print("       AI AGENT STARTED")
    print("======================================")

    print("Available tools:")
    print("- Calculator")
    print("- System Information")
    print("- Date and Time")
    print("- SQLite Long-term Memory")
    print("- AI Planning and Execution")

    print("\nType 'exit' or 'quit' to stop.")

    while True:

        user_input = input("\nYou: ").strip()

        if user_input.lower() in ["exit", "quit"]:

            print("\nAI Agent stopped.")
            break

        if not user_input:
            continue

        try:

            # Step 1: Generate execution plan
            print("\n[1] Generating execution plan...")

            plan = create_structured_plan(user_input)

            print("\nExecution Plan:")

            print(
                json.dumps(
                    plan,
                    indent=4
                )
            )

            # Step 2: Execute plan
            print("\n[2] Executing tasks...")

            result = execute_plan(plan)

            # Step 3: Display final answer
            print("\n======================================")
            print("             AI RESPONSE")
            print("======================================")

            response_tasks = [
                task for task in result["plan"]["tasks"]
                if task["tool"] == "generate_response"
            ]

            final_response = None

            if response_tasks:

                response_id = response_tasks[-1]["id"]

                final_response = result["results"].get(
                    response_id
                )

            if final_response:

                print(final_response)

            else:

                print(
                    "The agent could not generate a final response."
                )

                print(
                    json.dumps(
                        result["results"],
                        indent=4,
                        default=str
                    )
                )

            print("\nExecution Summary:")

            print("Completed:", result["completed_tasks"])
            print("Failed:", result["failed_tasks"])

        except Exception as error:

            print("\nAgent Error:", str(error))


# =====================================================
# 12. APPLICATION ENTRY POINT
# =====================================================

if __name__ == "__main__":

    run_interactive_agent()
