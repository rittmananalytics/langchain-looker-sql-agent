# LangChain Looker SQL Agent

**Connect LangChain to your Looker instance for conversational data querying using Looker's Open SQL Interface and its governed semantic layer.**

This project provides a Python package, `langchain-looker-agent`, that allows you to build LangChain agents capable of interacting with your Looker data via its Avatica JDBC driver. Ask questions in natural language, and the agent will translate them into Looker-specific SQL, execute them, and provide answers based on your curated LookML models.

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## Key Features

*   **Leverage Looker's Semantic Layer:** Queries use your existing LookML models, ensuring consistent metrics and business logic.
*   **Data Governance:** Respects Looker's permission model through JDBC authentication.
*   **Looker SQL Syntax Aware:** The agent is prompted to use backticked identifiers (`` `model_name`.`explore_name` ``, `` `view_name.field_name` ``), `AGGREGATE()` for measures, and other Calcite/Looker SQL nuances.
*   **Conversational Interaction:** Supports multi-turn conversations (when used with memory).
*   **Metadata Richness:** Informs the LLM with Looker-specific field metadata (labels, descriptions, categories) and filters hidden fields.
*   **Standard LangChain Integration:** Built with core LangChain components for easy use.

## Quickstart (Using the Library)

This example shows how to use the `langchain-looker-agent` library in your own Python project after installing it.

1.  **Install Prerequisites**

    ```bash
    sudo apt-get update
    sudo apt-get install -y openjdk-11-jdk --no-install-recommends
    java -version # Verify installation
    export JAVA_HOME=$(java -XshowSettings:properties -version 2>&1 > /dev/null | grep 'java.home' | awk '{print $3}')
    echo $JAVA_HOME
    mkdir drivers
    cd drivers
    wget https://github.com/looker-open-source/calcite-avatica/releases/download/avatica-1.26.0-looker/avatica-1.26.0-looker.jar
    pip install langchain-looker-agent langchain-openai python-dotenv

    ```

3.  **Install the package:**
    ```bash
    pip install langchain-looker-agent
    
    ```
    
4.  **Set Environment Variables:**
    Ensure the following are set in your environment or a `.env` file (see `.env.example`):
    *   `OPENAI_API_KEY` (or your chosen LLM's API key)
    *   `LOOKER_INSTANCE_URL` (e.g., `https://yourcompany.cloud.looker.com`)
    *   `LOOKML_MODEL_NAME` (e.g., `analytics`)
    *   `LOOKER_CLIENT_ID`
    *   `LOOKER_CLIENT_SECRET`
    *   `LOOKER_JDBC_DRIVER_PATH` (absolute path to your `avatica-...-looker.jar`)
    *   `JAVA_HOME` (pointing to your JRE/JDK root)

5.  **Example Python Script:**
    ```python
    import os
    from dotenv import load_dotenv
    from langchain_looker_agent import LookerSQLDatabase, LookerSQLToolkit, create_looker_sql_agent
    from langchain_openai import ChatOpenAI # Or your preferred LLM

    load_dotenv() # Loads .env file from current directory or parent

    # Initialize components
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    db = LookerSQLDatabase(
        looker_instance_url=os.environ["LOOKER_INSTANCE_URL"],
        lookml_model_name=os.environ["LOOKML_MODEL_NAME"],
        client_id=os.environ["LOOKER_CLIENT_ID"],
        client_secret=os.environ["LOOKER_CLIENT_SECRET"],
        jdbc_driver_path=os.environ["LOOKER_JDBC_DRIVER_PATH"],
        sample_rows_in_table_info=0 # Keep it minimal for quickstart
    )
    toolkit = LookerSQLToolkit(db=db)
    agent_executor = create_looker_sql_agent(llm=llm, toolkit=toolkit, verbose=False)

    # Ask a question
    question = "How many explores are available in the model?"
    response = agent_executor.invoke({"input": question, "chat_history": []})
    print(f"Question: {question}")
    print(f"Answer: {response.get('output')}")
    
    db.close()
    ```

## Running the Example Notebooks

This repository includes a Jupyter Notebook to demonstrate setup, testing, and conversational use.

*   **For detailed setup instructions for running the example notebooks (including Java, Python environment, and JDBC driver placement), please see: [EXAMPLES_SETUP.md](https://github.com/rittmananalytics/langchain-looker-sql-agent/blob/main/EXAMPLES_SETUP.md)**
*   **Notebooks available:**
    *   `examples/looker_langchain_sql_agent_tests.ipynb`: Thorough tests of all components.

## Technical Details

For a deeper dive into the implementation, JDBC interaction, specific Looker SQL syntax handled, and design choices (like why a custom `LookerSQLDatabase` wrapper was used over a new SQLAlchemy dialect), please refer to:
*   **[TECHNICAL_DETAILS.md](https://github.com/rittmananalytics/langchain-looker-sql-agent/blob/main/TECHNICAL_DETAILS.md)**

## Core Python Module

The main logic is encapsulated in the `langchain_looker_agent` package, primarily in `src/langchain_looker_agent/agent.py`. This includes:
*   `LookerSQLDatabase`: Manages JDBC connection and Looker-specific metadata/querying.
*   `LookerSQLToolkit`: Bundles LangChain tools.
*   `create_looker_sql_agent`: Factory for the ReAct agent.

## Troubleshooting

Common issues and solutions are discussed in the [EXAMPLES_SETUP.md](https://github.com/rittmananalytics/langchain-looker-sql-agent/blob/main/EXAMPLES_SETUP.md) and [TECHNICAL_DETAILS.md](https://github.com/rittmananalytics/langchain-looker-sql-agent/blob/main/TECHNICAL_DETAILS.md). Key areas include:
*   `JAVA_HOME` configuration.
*   Correct path to the Looker JDBC driver JAR.
*   Looker credentials and permissions for the SQL Interface.
*   Python package import errors (ensure `pip install -e .` or package installation).

## License
This project is licensed under the Apache 2.0 License. See the [LICENSE](https://github.com/rittmananalytics/langchain-looker-sql-agent/blob/main/LICENSE) file for details.
