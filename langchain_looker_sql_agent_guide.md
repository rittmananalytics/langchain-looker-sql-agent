# Introduction

Welcome to the guide for the `langchain-looker-agent`, a Python package found in the `rittmananalytics/langchain-looker-sql-agent` repository. This agent serves as a powerful bridge, connecting the flexible natural language processing capabilities of LangChain with Looker's robust Open SQL Interface.

**Core Purpose:**

The primary goal of the `langchain-looker-agent` is to empower users to query your organization's Looker semantic layer using natural language. It allows you to ask questions in plain English about your data, which the agent then translates into Looker-specific SQL queries. These queries are subsequently executed against your Looker instance via its JDBC interface, returning data that has been processed through your curated LookML models.

**Key Benefits:**

Utilizing this agent offers several significant advantages:

*   **Leverage Existing LookML Models:** Directly tap into the well-defined dimensions, measures, and relationships already built into your Looker Explores. This ensures that natural language queries are grounded in your existing business logic.
*   **Ensure Data Governance:** By querying through Looker, all data access is subject to the permissions and governance rules defined within your Looker instance, maintaining data security and control.
*   **Consistency in Metrics:** Queries are resolved against your Looker semantic layer, guaranteeing that metrics and calculations are consistent with how they are defined and used across your organization in Looker dashboards and reports.
*   **Enable Conversational Business Intelligence:** Move beyond traditional dashboards by allowing users to interact with data in a conversational manner, making data exploration more intuitive and accessible to a wider audience.

**How it Works (Brief Overview):**

The agent functions by taking a user's natural language question, interpreting its intent, and then constructing a SQL query that is compatible with Looker's Open SQL Interface. This generated SQL is specifically tailored to query the underlying database through Looker's semantic layer. The agent then facilitates the execution of this SQL query via a JDBC connection to your Looker instance, retrieving the results for presentation or further use within a LangChain workflow.

This guide will walk you through the installation, configuration, and usage of the `langchain-looker-agent`, enabling you to integrate natural language querying capabilities with your Looker data platform.

# Prerequisites and Installation

Before you can use the `langchain-looker-agent`, you'll need to ensure your environment is set up correctly with the necessary prerequisites.

## Prerequisites

1.  **Java Development Kit (JDK):**
    *   The agent requires OpenJDK 11 to run the Looker JDBC driver.
    *   **To install on Debian/Ubuntu:**
        ```bash
        sudo apt-get update && sudo apt-get install -y openjdk-11-jdk --no-install-recommends
        ```
    *   **To install on other systems:** Follow the appropriate installation instructions for OpenJDK 11.
    *   **Verify installation:** After installation, run `java -version` in your terminal. You should see output indicating OpenJDK version 11.x.x.

2.  **Looker Avatica JDBC Driver:**
    *   You need the Looker-specific Avatica JDBC driver JAR file (`avatica-*-looker.jar`) to enable communication with the Looker Open SQL Interface.
    *   **Download:** You can find the latest releases on the Calcite-Avatica GitHub releases page: [https://github.com/looker-open-source/calcite-avatica/releases/](https://github.com/looker-open-source/calcite-avatica/releases/)
    *   Alternatively, as mentioned in the `rittmananalytics/langchain-looker-sql-agent` repository's README, you can download a specific version directly. For example, to get version 1.26.0-looker:
        ```bash
        # Create a directory for drivers if you don't have one
        mkdir -p drivers
        # Download the JAR file into the drivers directory
        wget https://github.com/looker-open-source/calcite-avatica/releases/download/avatica-1.26.0-looker/avatica-1.26.0-looker.jar -P drivers/
        ```
        Ensure this JAR file is accessible in your environment, typically by placing it in a `drivers/` subdirectory within your project or a location included in your Java classpath. The agent will expect to find this driver.

3.  **Python:**
    *   Python 3.8 or higher is recommended. You can check your Python version by running `python --version` or `python3 --version`.

## Installation

Once the prerequisites are in place, you can install the `langchain-looker-agent` package and its core dependencies.

1.  **Using pip:**
    The primary way to install the agent is via pip:
    ```bash
    pip install langchain-looker-agent langchain-openai python-dotenv
    ```
    *   `langchain-looker-agent`: This is the agent package itself.
    *   `langchain-openai`: This package provides integration with OpenAI's language models (e.g., GPT-3.5, GPT-4). It's included by default as a common choice for the LLM powering the agent. If you plan to use a different LLM provider, you can replace `langchain-openai` with the relevant LangChain integration package (e.g., `langchain-anthropic` for Anthropic's Claude models, `langchain-google-genai` for Google's Gemini models).
    *   `python-dotenv`: This utility helps manage environment variables, which is useful for securely storing API keys and configuration settings.

2.  **Development Installation (from repository clone):**
    If you are working directly from a cloned copy of the `rittmananalytics/langchain-looker-sql-agent` GitHub repository, you might prefer an editable installation. After cloning the repository and navigating to its root directory:
    ```bash
    # It's recommended to set up a virtual environment first
    # python -m venv .venv
    # source .venv/bin/activate

    pip install -e .
    ```
    This command installs the package in "editable" mode, meaning changes you make to the source code will be reflected immediately in your environment. Ensure you also install any other dependencies as listed in the project's `pyproject.toml` or `requirements.txt`, and follow any specific setup instructions in files like `EXAMPLES_SETUP.md` if present in the repository.

# Configuration and Authentication

The `langchain-looker-agent` is configured primarily through environment variables. This approach is common for managing sensitive information like API keys and connection details securely.

**Using a `.env` File:**

It's highly recommended to use a `.env` file in the root of your project to store these environment variables. The `python-dotenv` package (installed as a dependency) will automatically load variables from this file when your application starts.

Create a file named `.env` in your project's root directory and add the following variables:

```env
# LLM Provider API Key (OpenAI example)
OPENAI_API_KEY="sk-your_openai_api_key_here"

# Looker Instance Configuration
LOOKER_INSTANCE_URL="https://yourcompany.cloud.looker.com" # Replace with your actual Looker instance URL
LOOKML_MODEL_NAME="your_lookml_model_name" # Replace with the LookML model you want to query

# Looker JDBC API Credentials for Authentication
LOOKER_CLIENT_ID="your_looker_api_client_id"
LOOKER_CLIENT_SECRET="your_looker_api_client_secret"

# Path to Looker JDBC Driver
LOOKER_JDBC_DRIVER_PATH="/path/to/your/drivers/avatica-1.26.0-looker.jar" # Replace with the actual path

# Java Home (JDK/JRE path)
JAVA_HOME="/usr/lib/jvm/java-11-openjdk-amd64" # Example for Debian/Ubuntu, verify for your system
```

**Environment Variables Explained:**

*   `OPENAI_API_KEY`:
    *   Your API key for accessing OpenAI's language models.
    *   If you are using a different LLM provider (e.g., Anthropic, Google Gemini), you will need to set the appropriate API key variable for that provider (e.g., `ANTHROPIC_API_KEY`). Refer to the specific LangChain documentation for that provider.

*   `LOOKER_INSTANCE_URL`:
    *   The full base URL of your Looker instance.
    *   Example: `https://yourcompany.cloud.looker.com` or `https://looker.yourdomain.com`. Do not include `/api/` or other paths here.

*   `LOOKML_MODEL_NAME`:
    *   The name of the specific LookML model that the agent should target for its queries. This model contains the Explores, dimensions, and measures that the agent will use to translate natural language to SQL.

*   `LOOKER_CLIENT_ID`:
    *   The Client ID for a Looker API3 user. This is used for authenticating the JDBC connection.

*   `LOOKER_CLIENT_SECRET`:
    *   The Client Secret for the Looker API3 user specified by `LOOKER_CLIENT_ID`.

*   `LOOKER_JDBC_DRIVER_PATH`:
    *   The absolute path to the `avatica-*-looker.jar` file you downloaded in the prerequisites step.
    *   Ensure this path is correct and the file is readable by the application.
    *   Example: `/home/user/myproject/drivers/avatica-1.26.0-looker.jar` or `C:\Users\user\myproject\drivers\avatica-1.26.0-looker.jar`.

*   `JAVA_HOME`:
    *   The root directory of your Java Development Kit (JDK) or Java Runtime Environment (JRE) installation (OpenJDK 11 is required).
    *   **To find `JAVA_HOME` on Linux/macOS:**
        You can often find it using:
        ```bash
        java -XshowSettings:properties -version 2>&1 > /dev/null | grep 'java.home' | awk '{print $3}'
        ```
        Common paths include `/usr/lib/jvm/java-11-openjdk-amd64`, `/opt/homebrew/opt/openjdk@11/libexec/openjdk.jdk/Contents/Home` (macOS with Homebrew), or similar.
    *   **On Windows:** This path is typically like `C:\Program Files\Java\jdk-11.x.x` or `C:\Program Files\AdoptOpenJDK\jdk-11.x.x-hotspot`.
    *   Ensure this variable points to the root of the JDK/JRE, not the `bin` subdirectory.

**Authentication Mechanism:**

The `LOOKER_CLIENT_ID` and `LOOKER_CLIENT_SECRET` are crucial for authentication. The agent uses these credentials to connect to the Looker instance via the JDBC driver. The permissions granted to the agent (i.e., what data it can access and which Explores it can query) are determined by the permissions assigned to this API user within the Looker platform. Ensure this user has the necessary access rights to the specified `LOOKML_MODEL_NAME` and its underlying data.

# Using the Looker SQL Agent for Natural Language Queries

Once you have completed the prerequisites, installation, and configuration, you can start using the `langchain-looker-agent` to query your Looker instance with natural language. This section provides a step-by-step guide with code examples, largely based on the `quickstart.py` example found in the `rittmananalytics/langchain-looker-sql-agent` repository.

Here's how to set up and run the agent:

1.  **Import Necessary Modules:**
    Start by importing all the required classes and functions.

    ```python
    import os
    from dotenv import load_dotenv
    from langchain_openai import ChatOpenAI # Or your preferred LLM provider
    from langchain_looker import (
        LookerSQLDatabase,
        LookerSQLToolkit,
        create_looker_sql_agent,
    )
    ```

2.  **Load Environment Variables:**
    If you're using a `.env` file, load it to make the variables accessible.

    ```python
    load_dotenv()
    ```

3.  **Initialize the LLM:**
    Set up the Language Model you intend to use. The example uses `ChatOpenAI` with `gpt-4o`, but you can substitute this with other compatible models or providers (e.g., `ChatAnthropic`).

    ```python
    llm = ChatOpenAI(
        model="gpt-4o",  # Or "gpt-3.5-turbo", etc. Can be changed to other models.
        temperature=0   # Set to 0 for more deterministic and factual responses
    )
    ```
    Adjust the `model` and `temperature` parameters as needed. A lower temperature is generally better for factual SQL generation.

4.  **Initialize `LookerSQLDatabase`:**
    Create an instance of `LookerSQLDatabase`. This object handles the connection to your Looker instance via JDBC and fetches schema information about your LookML model.

    ```python
    # Retrieve configuration from environment variables
    looker_instance_url = os.environ["LOOKER_INSTANCE_URL"]
    lookml_model_name = os.environ["LOOKML_MODEL_NAME"]
    looker_client_id = os.environ["LOOKER_CLIENT_ID"]
    looker_client_secret = os.environ["LOOKER_CLIENT_SECRET"]
    looker_jdbc_driver_path = os.environ["LOOKER_JDBC_DRIVER_PATH"]
    # Ensure JAVA_HOME is also set in your environment as per the Configuration section

    db = LookerSQLDatabase(
        looker_instance_url=looker_instance_url,
        lookml_model_name=lookml_model_name,
        client_id=looker_client_id,
        client_secret=looker_client_secret,
        jdbc_driver_path=looker_jdbc_driver_path,
        sample_rows_in_table_info=2,  # Number of sample rows to include in table/Explore info. Set to 0 to disable.
        # load_only_relevant_explores=True # Optional: If True, attempts to load only explores relevant to the query
    )
    ```
    The `sample_rows_in_table_info` parameter (e.g., 0, 2, or 3) controls how many sample rows are fetched for each table/Explore description provided to the LLM. This can help the LLM understand the data better but increases the initial schema loading time and token count.

5.  **Initialize `LookerSQLToolkit`:**
    The toolkit bundles the database connection with various tools the agent can use (e.g., a tool to list tables/Explores, a tool to query, a tool to get schema).

    ```python
    toolkit = LookerSQLToolkit(db=db, llm=llm)
    ```

6.  **Create the Agent Executor:**
    Use the `create_looker_sql_agent` function to assemble the LLM, toolkit, and agent logic into an executable agent.

    ```python
    agent_executor = create_looker_sql_agent(
        llm=llm,
        toolkit=toolkit,
        verbose=True,       # Set to True to see the agent's thought process and generated SQL.
        top_k=10,           # Limits how many tables/Explores are considered for context. Adjust based on your model's complexity.
        # max_iterations=10 # Optional: Maximum number of steps the agent can take.
        # return_intermediate_steps=True # Optional: To get intermediate outputs
    )
    ```
    *   `verbose=True`: Highly recommended during development and troubleshooting as it shows the agent's reasoning, the SQL it generates, and the results it gets back from Looker.
    *   `top_k`: This parameter helps the agent focus by limiting the number of Looker Explores (treated as "tables" by the SQLDatabaseChain) considered when generating the SQL query.

7.  **Formulate a Natural Language Question:**
    Define the question you want to ask your data.

    ```python
    question = "How many orders were placed last month?"
    # Example from quickstart.py:
    # question = "how many different products have the word 'Shirt' in their name in the 'Products' explore?"
    ```
    Choose a question relevant to your `lookml_model_name` and the Explores it contains.

8.  **Invoke the Agent:**
    Run the agent with your question. The `invoke` method is standard for LangChain Expression Language (LCEL) runnables. `chat_history` can be used to maintain conversational context, which will be discussed later. For a single query, an empty list is fine.

    ```python
    # For agents that support chat history (like this one is designed to):
    response = agent_executor.invoke({
        "input": question,
        "chat_history": [] # Pass an empty list for no prior history, or a list of HumanMessage/AIMessage objects
    })

    # If the agent does not explicitly use chat_history in its prompt or structure,
    # a simpler invoke might look like:
    # response = agent_executor.invoke({"input": question})
    ```

9.  **Extract and Print the Answer:**
    The agent's response is typically a dictionary containing the output.

    ```python
    answer = response.get('output')
    print("\nQuestion:", question)
    print("Answer:", answer)
    ```

10. **Properly Close the Database Connection:**
    It's crucial to close the Looker JDBC connection when you're done to free up resources. A `try...finally` block ensures this happens even if errors occur.

    ```python
    try:
        # ... (all the steps from 1 to 9 above)
        # Example:
        # load_dotenv()
        # llm = ChatOpenAI(model="gpt-4o", temperature=0)
        # db = LookerSQLDatabase(...) # Initialize as shown in step 4
        # toolkit = LookerSQLToolkit(db=db, llm=llm)
        # agent_executor = create_looker_sql_agent(llm=llm, toolkit=toolkit, verbose=True, top_k=10)
        # question = "How many orders were placed by users in California last quarter?"
        # response = agent_executor.invoke({"input": question, "chat_history": []})
        # answer = response.get('output')
        # print("\nQuestion:", question)
        # print("Answer:", answer)
        pass # Your agent execution code would be here

    finally:
        if 'db' in locals() and db:
            print("\nClosing Looker JDBC connection...")
            db.close()
            print("Connection closed.")
    ```
    This full example structure (from imports to closing the connection) should be placed in your Python script.

This detailed walkthrough should help you get started with running natural language queries against your Looker instance using the `langchain-looker-agent`. Remember to replace placeholder values in your `.env` file and in the code with your actual configuration.

# Direct Execution of Looker SQL (Advanced)

While the primary purpose of the `create_looker_sql_agent` is to translate natural language questions into Looker SQL queries for execution, there are scenarios where you might want to execute a Looker SQL query directly. This can be useful for testing, debugging, or when you already have a valid Looker SQL query that you need to run programmatically.

The `LookerSQLDatabase` object (often aliased as `db` in examples) provides a method for this direct execution.

**Using `db.run()` for Direct SQL Execution:**

You can use the `db.run(your_sql_query_string)` method to send a SQL query directly to the Looker Open SQL Interface.

**Code Example:**

Assuming you have already initialized the `LookerSQLDatabase` instance as `db` (shown in the "Using the Looker SQL Agent for Natural Language Queries" section):

```python
# Ensure 'db' is an initialized LookerSQLDatabase instance from the previous section.
# For example:
# from dotenv import load_dotenv
# import os
# from langchain_looker import LookerSQLDatabase
# load_dotenv()
# db = LookerSQLDatabase(
#     looker_instance_url=os.environ["LOOKER_INSTANCE_URL"],
#     lookml_model_name=os.environ["LOOKML_MODEL_NAME"],
#     client_id=os.environ["LOOKER_CLIENT_ID"],
#     client_secret=os.environ["LOOKER_CLIENT_SECRET"],
#     jdbc_driver_path=os.environ["LOOKER_JDBC_DRIVER_PATH"]
# )

# Example of a Looker SQL query string
# Replace with your actual model, explore, dimension, and measure names
sql_query = "SELECT `your_explore_name.dimension_name`, AGGREGATE(`your_explore_name.measure_name`) FROM `your_model_name`.`your_explore_name` GROUP BY 1 ORDER BY 2 DESC LIMIT 10"

try:
    print(f"\nExecuting direct SQL query: {sql_query}")
    results = db.run(sql_query) # db is your LookerSQLDatabase instance
    print("Query Results:")
    # The format of 'results' will depend on the underlying jaydebeapi and database driver.
    # It's often a list of tuples or a string representation. You might need to parse it.
    print(results)
except Exception as e:
    print(f"Error executing direct SQL: {e}")
finally:
    # Remember to close the connection when all operations are done,
    # typically at the end of your script or application lifecycle.
    if 'db' in locals() and db: # Check if db was initialized
        # db.close() # Uncomment if this is the end of your script
        pass # In a larger script, you'd close it at the very end.
```
**Important Note on `db.close()`:** In this specific example, `db.close()` is commented out because you might perform other operations with `db` or the agent. The connection should be closed when your application or script finishes all Looker-related tasks, typically within a main `try...finally` block as shown in the previous section.

**Looker Open SQL Interface Syntax:**

Any SQL query submitted directly using `db.run()` **must** conform to the Looker Open SQL Interface syntax, which is based on the Apache Calcite SQL dialect. Key syntax rules include:

*   **Backticks for Identifiers:** All identifiers (model names, Explore names, view names, field names) must be enclosed in backticks (`` ` ``).
    *   Example: `` `your_model_name`.`your_explore_name` ``
    *   Example: `` `your_view_name.your_dimension_name` ``

*   **`AGGREGATE()` for Measures:** LookML measures must be wrapped in the `AGGREGATE()` function.
    *   Example: `AGGREGATE(\`your_view_name.your_measure_name\`)`

*   **Limitations:** The Looker Open SQL Interface has certain limitations compared to standard database SQL:
    *   **No Explicit JOINs:** Joins are defined in your LookML model and are automatically handled by Looker. You cannot write explicit `JOIN` clauses in your SQL.
    *   **No Subqueries (Generally):** Complex subqueries or CTEs might not be supported or may behave unexpectedly.
    *   **No Window Functions (Generally):** Advanced window functions are typically not supported.
    *   Refer to the official Looker documentation for the most up-to-date list of supported SQL functions and syntax for the Open SQL Interface.

This direct execution capability is a powerful tool for advanced use cases but should be used with a clear understanding of Looker's SQL dialect and its semantic layer. For most end-user query needs, leveraging the natural language to SQL capabilities of the agent is recommended.
