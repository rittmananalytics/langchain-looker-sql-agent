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
    *   **To install on other systems:** Follow the appropriate installation instructions for OpenJDK 11 for your operating system.
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
        Ensure this JAR file is accessible in your environment, typically by placing it in a `drivers/` subdirectory within your project or another location included in your Java classpath. The agent will expect to find this driver.

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
    *   `langchain-openai`: This package provides integration with OpenAI's language models (e.g., GPT-3.5, GPT-4). It's included by default as a common choice for the LLM powering the agent. If you plan to use a different LLM provider, you can replace `langchain-openai` with the relevant LangChain integration package (e.g., `langchain-anthropic` for Anthropic's Claude models, or `langchain-google-genai` for Google's Gemini models).
    *   `python-dotenv`: This utility helps manage environment variables, which is useful for securely storing API keys and configuration settings.

2.  **Development Installation (from repository clone):**
    If you are working directly from a cloned copy of the `rittmananalytics/langchain-looker-sql-agent` GitHub repository, you might prefer an editable installation. After cloning the repository and navigating to its root directory:
    ```bash
    # It's recommended to set up a virtual environment first
    # python3 -m venv .venv
    # source .venv/bin/activate

    pip install -e .
    ```
    This command installs the package in "editable" mode, meaning changes you make to the source code will be reflected immediately in your environment. Ensure you also install any other dependencies as listed in the project's `pyproject.toml` or `requirements.txt`, and follow any specific setup instructions in files like `EXAMPLES_SETUP.md` if present in the repository.

# Configuration and Authentication

The `langchain-looker-agent` is configured primarily through environment variables. This approach is common for managing sensitive information like API keys and connection details securely.

**Using a `.env` File:**

It's highly recommended to use a `.env` file in the root of your project to store these environment variables. The `python-dotenv` package (installed as a dependency if you used `pip install langchain-looker-agent langchain-openai python-dotenv`) will automatically load variables from this file when your application starts.

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
LOOKER_JDBC_DRIVER_PATH="/app/drivers/avatica-1.26.0-looker.jar" # Example: Replace with the actual path to your driver

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
        Common paths include `/usr/lib/jvm/java-11-openjdk-amd64` (common on Linux) or `/opt/homebrew/opt/openjdk@11/libexec/openjdk.jdk/Contents/Home` (macOS with Homebrew).
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
        # agent_executor_kwargs={"handle_parsing_errors": True} # Optional: For more robust error handling
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
    Run the agent with your question. The `invoke` method is standard for LangChain Expression Language (LCEL) runnables. `chat_history` should be provided if you are managing conversation history manually, though it's better handled by a memory object (see next section).

    ```python
    # For a single, non-conversational query:
    response = agent_executor.invoke({
        "input": question,
        "chat_history": [] # Provide an empty list if no prior conversation history
    })
    ```

9.  **Extract and Print the Answer:**
    The agent's response is typically a dictionary containing the output.

    ```python
    answer = response.get('output')
    print(f"\nQuestion: {question}")
    print(f"Answer: {answer}")
    ```

10. **Properly Close the Database Connection:**
    It's crucial to close the Looker JDBC connection when you're done to free up resources. A `try...finally` block ensures this happens even if errors occur.

    ```python
    # Full example structure:
    # (Imports and initializations from steps 1-6 would be here)
    # db = None # Ensure db is defined in the outer scope for the finally block
    # try:
    #     (Steps 1-6: Imports, load_dotenv, LLM, LookerSQLDatabase, LookerSQLToolkit, create_looker_sql_agent)
    #     db = LookerSQLDatabase(...) # Assign to db here
    #     toolkit = LookerSQLToolkit(db=db, llm=llm)
    #     agent_executor = create_looker_sql_agent(...)
    #
    #     question = "How many orders were placed by users in California last quarter?"
    #     response = agent_executor.invoke({"input": question, "chat_history": []})
    #     answer = response.get('output')
    #     print(f"\nQuestion: {question}")
    #     print(f"Answer: {answer}")
    #
    # finally:
    #     if db: # Check if db was successfully initialized
    #         print("\nClosing Looker JDBC connection...")
    #         db.close()
    #         print("Connection closed.")
    ```
    Place your complete script logic within the `try` block and the `db.close()` call in the `finally` block to ensure resources are managed correctly.

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
# finally:
#     # Remember to close the connection when all operations are done.
#     # If 'db' was initialized in this specific block, you would close it here.
#     # However, if 'db' is managed by a larger script structure (like the try/finally in the previous section),
#     # avoid closing it prematurely here.
#     # if 'db' in locals() and db:
#     #     db.close()
```
**Important Note on `db.close()`:** The `db.close()` call should typically be managed at the end of your entire script or application lifecycle, as shown in the `try...finally` block in the "Using the Looker SQL Agent for Natural Language Queries" section. Avoid closing it after each `db.run()` if you intend to reuse the connection.

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

# Understanding Agent's Operational Details

For users interested in the mechanics behind the `langchain-looker-agent`, this section provides a summary of its key operational aspects, drawing from the technical details typically found in a `TECHNICAL_DETAILS.md` document for such a project.

1.  **Core `LookerSQLDatabase` Class:**
    *   This class is the heart of the Looker integration. It acts as a specialized wrapper around Looker's Open SQL Interface.
    *   The connection is established using JDBC, facilitated by the `jaydebeapi` Python library, which in turn uses the downloaded Looker Avatica JDBC driver (`avatica-*-looker.jar`).
    *   All operations are scoped to the specific LookML model name (`lookml_model_name`) you provide during its initialization. This means the agent will only "see" Explores and fields defined within that LookML model.

2.  **Metadata Discovery for LLM Context:**
    To enable the LLM to generate accurate Looker SQL, the agent first needs to understand the schema of your LookML model.
    *   **Listing Explores (Tables):** It retrieves a list of available Explores within the specified `lookml_model_name` by calling `DatabaseMetaData.getTables()`. In this context, Looker Explores are treated conceptually as tables. The LookML model name is used as a schema pattern to filter these Explores.
    *   **Fetching Field Information (Columns):** For each relevant Explore, it fetches detailed information about its dimensions and measures using `DatabaseMetaData.getColumns()`.
    *   **Enriching Schema with Looker Metadata:** Crucially, the agent extracts Looker-specific metadata for each field. This includes:
        *   `FIELD_LABEL`: The user-friendly label of the field from LookML.
        *   `FIELD_DESCRIPTION`: The description of the field from LookML.
        *   `FIELD_CATEGORY`: Indicates if the field is a `DIMENSION` or a `MEASURE`.
        *   `HIDDEN`: A flag to determine if the field is hidden in Looker's UI.
        This metadata is then formatted and appended to the standard column information, providing richer context to the LLM. For example, a field might be presented to the LLM like this:
        ```sql
        `order_items.total_sale_price` DECIMAL -- label: 'Total Sale Price'; category: MEASURE; description: 'The total sale price of the order item, calculated as quantity * sale_price.'
        ```
    *   **Filtering Hidden Fields:** Fields marked as `HIDDEN` in LookML are typically filtered out and not presented to the LLM, respecting your LookML design choices for field visibility.

3.  **Prompt Engineering for Looker SQL Generation:**
    The accuracy of the LLM's generated SQL heavily relies on carefully engineered prompts, especially the system prompt.
    *   **System Instructions Template:** A specialized system prompt (often derived from a template like `LOOKER_SQL_SYSTEM_INSTRUCTIONS_TEMPLATE`) provides comprehensive instructions to the LLM.
    *   **Key Instructions in the Prompt:**
        *   **SQL Dialect:** Explicitly states that the SQL must adhere to the Apache Calcite dialect used by Looker's Open SQL Interface.
        *   **Looker Data Structure:** Explains how Looker's structure maps to SQL concepts (LookML Model as a schema, Explore as a table, and `view_name.field_name` as the column identifier).
        *   **Backtick Syntax:** Mandates the use of backticks (`` ` ``) for *all* identifiers (model names, Explore names, view names, field names). Examples: `` `your_model_name`.`your_explore_name` ``, `` `view_name.field_name` ``.
        *   **Measure Aggregation:** Instructs the LLM to use `AGGREGATE(\`view_name.measure_name\`)` when referring to LookML measures, as direct aggregation functions (like `SUM()`, `AVG()`) on measures are not allowed.
        *   **Restrictions:** Lists specific SQL features that are **not** allowed or are problematic with the Open SQL Interface, such as:
            *   No explicit `JOIN` clauses (Looker handles joins based on LookML).
            *   No subqueries or Common Table Expressions (CTEs).
            *   No window functions.
            *   No Data Manipulation Language (DML) statements (e.g., `INSERT`, `UPDATE`, `DELETE`).
            *   No `SELECT *`.
        *   **Query Termination:** Advises that generated SQL queries should not end with a semicolon.

4.  **Query Execution Pre-processing:**
    *   Before the `LookerSQLDatabase` class executes a SQL query received from the LLM, it typically performs some pre-processing. This might include stripping any trailing semicolons or removing markdown code fences (e.g., ```sql ... ```) that LLMs sometimes add around the generated SQL.

5.  **Toolkit and Agent Assembly:**
    *   The `LookerSQLToolkit` class bundles the `LookerSQLDatabase` interaction methods (like getting table/Explore descriptions, running SQL queries) into a set of "tools" that the LangChain agent can use.
    *   The `create_looker_sql_agent` function then assembles these tools, the chosen LLM (e.g., `ChatOpenAI`), and the carefully crafted Looker-specific prompt into a ReAct (Reasoning and Acting) agent. This agent can then intelligently decide which tool to use (e.g., list Explores, get schema of an Explore, execute a query) based on the natural language input to fulfill the user's request.

Understanding these operational details can help in troubleshooting, refining prompts (if customizing the agent), and appreciating the nuances of querying Looker's semantic layer through a natural language interface.

# Conversational Usage with Memory

The `langchain-looker-agent` can be used not just for single, standalone questions, but also for engaging in conversations about your data. This is achieved by incorporating memory, allowing the agent to remember previous turns in the conversation and use that context to answer follow-up questions more accurately.

1.  **Introduction to Conversational Memory:**
    When you ask a follow-up question like "And how many of those were for existing customers?", the agent needs to remember what "those" refers to from the previous interaction. Conversational memory enables this by storing and recalling the history of questions and answers.

2.  **Importing `ConversationBufferMemory`:**
    LangChain provides various memory types. A common one for this purpose is `ConversationBufferMemory`.

    ```python
    from langchain.memory import ConversationBufferMemory
    ```

3.  **Initializing `ConversationBufferMemory`:**
    Create an instance of the memory.

    ```python
    memory = ConversationBufferMemory(
        memory_key="chat_history", # This key must match the input variable used in the agent's prompt
        return_messages=True       # Ensures the memory returns `HumanMessage` and `AIMessage` objects
    )
    ```
    *   `memory_key="chat_history"`: The agent created by `create_looker_sql_agent` is typically configured to expect the conversation history under this specific key.
    *   `return_messages=True`: This makes the memory store and return messages as LangChain message objects (e.g., `HumanMessage`, `AIMessage`), which is the expected format for conversational agents.

4.  **Passing Memory to the Agent:**
    When creating the agent executor, you pass the initialized `memory` object via the `agent_executor_kwargs` parameter.

    ```python
    # Assuming 'llm' and 'toolkit' (LookerSQLToolkit instance) are already initialized as per previous sections
    # llm = ChatOpenAI(model="gpt-4o", temperature=0)
    # # db = LookerSQLDatabase(...) # db would be part of the toolkit
    # toolkit = LookerSQLToolkit(db=db, llm=llm) # 'db' needs to be defined before this line

    agent_executor = create_looker_sql_agent(
        llm=llm,
        toolkit=toolkit, # Ensure 'toolkit' is defined, incorporating 'db' and 'llm'
        verbose=True,  # Recommended for observing memory effects during conversation
        top_k=10,      # As discussed previously
        agent_executor_kwargs={
            "memory": memory,
            "handle_parsing_errors": True, # Good practice to handle LLM output parsing issues
            "max_iterations": 7            # Example: limit the number of steps the agent can take
        }
    )
    ```
    Setting `handle_parsing_errors=True` can make the agent more robust if the LLM occasionally produces output that's hard to parse.

5.  **Example of a Multi-Turn Conversation:**
    Now, you can interact with the `agent_executor` over multiple turns. The memory object will automatically manage the `chat_history`.

    ```python
    # Ensure 'agent_executor' is initialized with memory as shown above.
    # The 'db' (LookerSQLDatabase instance) should be initialized and part of the toolkit passed to the agent.

    # Full setup for this example (assuming it's a standalone script):
    # import os
    # from dotenv import load_dotenv
    # from langchain_openai import ChatOpenAI
    # from langchain_looker import LookerSQLDatabase, LookerSQLToolkit, create_looker_sql_agent
    # from langchain.memory import ConversationBufferMemory
    #
    # load_dotenv()
    #
    # llm = ChatOpenAI(model="gpt-4o",temperature=0)
    # db = LookerSQLDatabase(
    #     looker_instance_url=os.environ["LOOKER_INSTANCE_URL"],
    #     lookml_model_name=os.environ["LOOKML_MODEL_NAME"],
    #     client_id=os.environ["LOOKER_CLIENT_ID"],
    #     client_secret=os.environ["LOOKER_CLIENT_SECRET"],
    #     jdbc_driver_path=os.environ["LOOKER_JDBC_DRIVER_PATH"],
    #     sample_rows_in_table_info=0 # Set to 0 for this example to reduce noise
    # )
    # toolkit = LookerSQLToolkit(db=db, llm=llm)
    # memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    # agent_executor = create_looker_sql_agent(
    #     llm=llm, toolkit=toolkit, verbose=True, top_k=10,
    #     agent_executor_kwargs={"memory": memory, "handle_parsing_errors": True, "max_iterations": 7}
    # )
    # # End of full setup example for context

    # db_connection_managed_globally = db # Assuming 'db' is the globally managed connection from prior setup.
    try:
        # Initial question
        # IMPORTANT: Replace 'your_actual_explore_name' with a valid Explore from your LookML model.
        # The fields used (orders, customer status, order value) are illustrative. Adapt to your model.
        question1 = "How many total orders were there last month in the `your_actual_explore_name` Explore?"
        print(f"Q1: {question1}")
        response1 = agent_executor.invoke({"input": question1}) # chat_history is implicitly handled by memory
        print(f"A1: {response1.get('output')}\n")

        # Follow-up question
        question2 = "And how many of those were from new customers?" # Assumes your model has a way to identify 'new customers'
        print(f"Q2: {question2}")
        response2 = agent_executor.invoke({"input": question2})
        print(f"A2: {response2.get('output')}\n")

        # Another follow-up
        question3 = "What was the average order value for them?" # 'them' refers to new customers from Q2
        print(f"Q3: {question3}")
        response3 = agent_executor.invoke({"input": question3})
        print(f"A3: {response3.get('output')}\n")

        # Optionally, inspect the memory content (for debugging or understanding)
        # This shows how the conversation is stored.
        # print("--- Memory content ---")
        # print(memory.load_memory_variables({})) # Example of how to inspect memory
        # print("----------------------")

    except Exception as e:
        print(f"An error occurred during the conversation: {e}")
    # finally:
    #     # The 'db.close()' should be handled at the very end of the application's lifecycle,
    #     # not necessarily after each conversational block if the agent/db is intended to be reused.
    #     # Refer to the main try/finally structure in the "Using the Looker SQL Agent" section.
    #     if 'db_connection_managed_globally' in locals() and db_connection_managed_globally:
    #         print("\nClosing Looker JDBC connection (if this is the end of all operations)...")
    #         db_connection_managed_globally.close()
    #         print("Connection closed.")
    ```
    **Important Note on Example Questions:** The questions above (`"How many total orders..."`, `"And how many of those were from new customers?"`, `"What was the average order value for them?"`) and the Explore name `` `your_actual_explore_name` `` are illustrative. You **must** adapt these to use valid Explore names, dimensions, and measures from *your specific LookML model* for the queries to work. The example demonstrates the conversational flow, not the universal applicability of these exact English phrases to every LookML model.

6.  **Implicit `chat_history` Handling:**
    When you initialize the agent with a memory object, you no longer need to manually pass the `chat_history` in the `invoke` call's dictionary (unless you want to override or inject specific history for a single call, which is an advanced use case). The `ConversationBufferMemory` automatically captures the user's input and the agent's output, and provides this history to the agent for subsequent calls.

By using memory, you can create much more natural and powerful interactions with your Looker data, allowing users to drill down, ask clarifying questions, and explore data contextually.

# Best Practices and Troubleshooting

This section provides tips for getting the most out of the `langchain-looker-agent` and guidance on how to address common issues.

## Best Practices

1.  **Understand Your LookML Model:**
    *   The agent's effectiveness is tied to the clarity and structure of the LookML model.
    *   Knowing available Explores, dimensions (and their types: `time`, `string`, `number`, etc.), and measures is key for phrasing effective questions. Use exact names, including view names (e.g., `orders.created_date`, `users.city`).

2.  **Craft Clear and Specific Questions:**
    *   Be explicit about entities (Explores/views), metrics (measures or aggregatable dimensions), timeframes, and filters.
    *   Avoid ambiguity. Instead of "Show sales," try "What were the total sales amount from the `order_items` Explore for the last completed quarter, broken down by product category?"
    *   Using terms that align with your LookML field labels or descriptions can improve accuracy.

3.  **Iterate on Queries:**
    *   If the first answer isn't perfect, refine the question or ask follow-up questions, especially when using conversational memory.
    *   Break down complex requests into smaller, sequential questions.

4.  **Leverage `top_k` for Context Management:**
    *   The `top_k` parameter in `create_looker_sql_agent` (e.g., `top_k=10`) limits the number of Explores (tables) considered by the LLM.
    *   Adjust based on your model's complexity. A smaller `top_k` might focus the LLM but could miss relevant Explores if they aren't highly ranked by the retriever.

5.  **Use `verbose=True` for Debugging:**
    *   Setting `verbose=True` when calling `create_looker_sql_agent` (or for the toolkit/database) provides detailed output of the agent's thoughts, the generated SQL, and intermediate steps. This is invaluable for debugging.

6.  **Specify `lookml_model_name` Correctly:**
    *   Ensure the `lookml_model_name` environment variable (and thus passed to `LookerSQLDatabase`) exactly matches a model name in your Looker instance that the API user has access to. This scopes the agent's view of available Explores.

## Troubleshooting

1.  **Java and JDBC Driver Issues:**
    *   **`JAVA_HOME` Not Set or Incorrect:**
        *   **Symptom:** Errors related to finding Java, `jaydebeapi` connection failures.
        *   **Solution:** Verify `JAVA_HOME` is set correctly and points to the OpenJDK 11 root, not its `bin` directory.
    *   **`LOOKER_JDBC_DRIVER_PATH` Incorrect:**
        *   **Symptom:** "Class not found: com.looker.lookerjdbc.LookerDriver" or similar `jaydebeapi` errors.
        *   **Solution:** Ensure `LOOKER_JDBC_DRIVER_PATH` is an absolute or correctly resolved relative path to the `avatica-*-looker.jar` file.
    *   **Driver/JDK Version Mismatch:**
        *   **Symptom:** Unexpected connection errors.
        *   **Solution:** Ensure you are using OpenJDK 11.

2.  **Authentication and Permissions:**
    *   **Invalid Looker API Client ID/Secret:**
        *   **Symptom:** Authentication failed, 401/403 errors during connection (check Looker logs or `jaydebeapi` errors).
        *   **Solution:** Double-check `LOOKER_CLIENT_ID` and `LOOKER_CLIENT_SECRET`.
    *   **Insufficient API User Permissions:**
        *   **Symptom:** Agent connects but sees no Explores, or queries fail with permission errors.
        *   **Solution:** The Looker API user must have access to the specified `LOOKML_MODEL_NAME`, permissions for the Open SQL Interface (JDBC), access to underlying database connections, and `see_lookml` or `explore` permissions for relevant models/Explores.

3.  **Looker SQL Syntax Errors (from LLM or Manual Query):**
    *   **Missing Backticks:**
        *   **Symptom:** SQL errors like "Table not found," "Column not found."
        *   **Solution:** All Looker SQL identifiers (model, explore, `view.field`) require backticks: `` `model_name`.`explore_name` ``, `` `orders.order_id` ``.
    *   **Incorrect Measure Aggregation:**
        *   **Symptom:** Errors like "Cannot aggregate a non-measure field."
        *   **Solution:** LookML measures must be wrapped with `AGGREGATE(\`view_name.measure_name\`)`. Dimensions should not be. Standard SQL aggregates (`SUM`, `AVG`) apply to dimensions for custom aggregations.
    *   **Using Unsupported SQL Features:**
        *   **Symptom:** SQL validation errors from Looker.
        *   **Solution:** Looker's Open SQL Interface (Calcite) doesn't support explicit `JOIN`s, most complex subqueries, or window functions.

4.  **Mandatory LookML Filters (`always_filter`, `conditionally_filter`):**
    *   **Symptom:** Queries fail (possibly with missing filter errors) or return no data.
    *   **Solution:** If an Explore has mandatory filters, the LLM must be guided to include these in `WHERE` or `HAVING` clauses. This may require more specific questions (e.g., "Show sales for `orders` Explore *for last month*") or using Explores without such strict filters.

5.  **Agent Errors and LLM Issues:**
    *   **Iteration/Time Limits:**
        *   **Symptom:** "Agent stopped due to iteration limit or time limit."
        *   **Solution:** Increase `max_iterations` in `agent_executor_kwargs` for complex queries.
    *   **Parsing Errors / Invalid Format:**
        *   **Symptom:** "Invalid Format: Missing 'Action:' after 'Thought:'".
        *   **Solution:** LLM confusion. Rephrase the question, be more specific, or ensure `handle_parsing_errors=True` in `agent_executor_kwargs`. Consider different LLM/temperature.
    *   **LLM API Key Issues:**
        *   **Symptom:** LLM provider authentication errors (e.g., OpenAI API key invalid, quota exceeded).
        *   **Solution:** Check your LLM API key and account status.

6.  **No Explores Found / Empty Schema:**
    *   **Symptom:** Agent reports no tables/Explores, or schema fetching is empty.
    *   **Solution:** Verify `LOOKML_MODEL_NAME` is exact. Ensure API user access to this model and its Explores. Check Looker project deployment and model configuration.

7.  **Query Performance:**
    *   **Symptom:** Queries are very slow.
    *   **Solution:** Performance depends on Looker, the database, query complexity, and data volume. Optimize LookML, check database performance, or simplify queries. The agent is best for interactive exploration.

[end of langchain_looker_sql_agent_guide.md]
