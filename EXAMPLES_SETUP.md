# Setup Guide for Running Example Notebooks: LangChain Looker SQL Agent

This guide provides detailed instructions for setting up your environment to run the example Jupyter Notebooks included in this repository. These notebooks demonstrate the functionality of the `langchain-looker-agent`.

## Prerequisites

Before you begin, ensure your system or development environment (e.g., local machine, cloud VM like Google Vertex AI Workbench) meets the following prerequisites:

1.  **Python:** Version 3.8 or newer.
2.  **Java Runtime Environment (JRE) or Development Kit (JDK):**
    *   **Version 11 or newer is strongly recommended.** This is essential for the `JayDeBeApi` library to interact with the Looker JDBC driver.
    *   **Installation & `JAVA_HOME`:**
        *   You must have Java installed.
        *   The `JAVA_HOME` environment variable **must be correctly set** to point to the root directory of your JDK/JRE installation (e.g., `/usr/lib/jvm/java-11-openjdk-amd64` on Linux, or the appropriate path on macOS/Windows). This is critical for `JPype1` (used by `JayDeBeApi`) to find the JVM.
        *   **Verification:**
            ```bash
            java -version
            echo $JAVA_HOME # Linux/macOS
            # echo %JAVA_HOME% # Windows
            ```
    *   **Installation Examples:**
        *   **Debian/Ubuntu:** `sudo apt-get update && sudo apt-get install -y openjdk-11-jdk --no-install-recommends`
        *   **macOS (Homebrew):** `brew install openjdk@11` (followed by setting `JAVA_HOME` appropriately).
        *   **Windows:** Download an OpenJDK 11+ installer (e.g., from Adoptium/Eclipse Temurin) and follow its instructions, then set `JAVA_HOME` in your system environment variables.
3.  **Looker Instance & Credentials:**
    *   Access to a Looker instance with the **SQL Interface (JDBC)** enabled.
    *   Your **Looker Instance URL** (e.g., `https://yourcompany.cloud.looker.com`).
    *   **API3 Client ID** and **Client Secret** for a Looker user. This user must have permissions to query the desired LookML model(s) via the SQL Interface.
4.  **LookML Model Name:** The name of the LookML model the agent will target (e.g., `analytics`).
5.  **Looker Avatica JDBC Driver (`.jar` file):**
    *   You must download this driver JAR file (e.g., `avatica-<version>-looker.jar`).
    *   **Source:** [Looker Open Source Calcite-Avatica Releases on GitHub](https://github.com/looker-open-source/calcite-avatica/releases)
6.  **LLM API Key:**
    *   An API key for your chosen Large Language Model provider (e.g., OpenAI, Anthropic). The example notebooks use OpenAI.

## Setup Steps

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/your-username/looker-langchain-sql-agent.git # Replace with your repo URL
    cd looker-langchain-sql-agent
    ```

2.  **Create and Activate a Python Virtual Environment (Highly Recommended):**
    ```bash
    python3 -m venv venv_looker_agent
    source venv_looker_agent/bin/activate  # On Linux/macOS
    # venv_looker_agent\Scripts\activate    # On Windows
    ```

3.  **Verify Java and `JAVA_HOME`:**
    *   Before proceeding, re-confirm in your **activated terminal session** that Java is installed and `JAVA_HOME` is correctly set (see Prerequisites above). The Python environment needs to be able to find the JVM.

4.  **Install Python Dependencies:**
    This command installs the `langchain-looker-agent` package in editable mode (`-e .`) along with all other dependencies needed for development and running the examples.
    ```bash
    pip install -r requirements.txt
    ```

5.  **Place the Looker JDBC Driver:**
    *   If you haven't already, create a `drivers/` directory in the project root:
        ```bash
        mkdir drivers
        ```
    *   Move/copy your downloaded `avatica-<version>-looker.jar` file into this `drivers/` directory. For example, if you downloaded `avatica-1.26.0-looker.jar`, you would have `drivers/avatica-1.26.0-looker.jar`.

6.  **Configure Environment Variables (.env file):**
    *   Copy the example environment file to create your own:
        ```bash
        cp .env.example .env
        ```
    *   **Edit the `.env` file** (now at the project root) with your actual credentials and paths:
        ```env
        # LangChain / LLM Configuration
        OPENAI_API_KEY="sk-YOUR_OPENAI_API_KEY_HERE"

        # Looker Configuration for Avatica JDBC Driver
        LOOKER_INSTANCE_URL="https://yourcompany.cloud.looker.com" # Full HTTPS URL
        LOOKML_MODEL_NAME="your_lookml_model_name"                 # e.g., analytics
        LOOKER_CLIENT_ID="YOUR_LOOKER_API3_CLIENT_ID"
        LOOKER_CLIENT_SECRET="YOUR_LOOKER_API3_CLIENT_SECRET"
        # Path to your JDBC driver JAR, relative to the project root
        LOOKER_JDBC_DRIVER_PATH="./drivers/avatica-1.26.0-looker.jar" # ADJUST VERSION AND NAME AS NEEDED
        ```
    *   **Important:** `LOOKER_JDBC_DRIVER_PATH` should be the path to the JAR file *relative to the project root* (where the `.env` file is) or an absolute path. The example notebooks resolve this relative path.

## Running the Example Notebooks

1.  **Start JupyterLab or Jupyter Notebook:**
    From your project's root directory, with your virtual environment activated:
    ```bash
    jupyter lab  # or jupyter notebook
    ```

2.  **Navigate and Open Notebooks:**
    *   In the Jupyter interface, go into the `examples/` directory.
    *   **`looker_langchain_sql_agent_tests.ipynb`:** It's highly recommended to run this notebook first. It contains detailed setup cells (including Java/package checks that you can uncomment if needed for the notebook's specific kernel environment) and performs thorough manual tests of the `LookerSQLDatabase` component before creating and testing the full agent. This helps isolate any connection or basic setup issues.
    *   **`looker_langchain_sql_agent_tests_no_envs.ipynb`:** A simpler version of the above notebook that doesn't try to read environment variable values from the .env file but instead sets them in the notebook code.

3.  **Execute Cells:**
    *   Run the notebook cells sequentially.
    *   **Restart Kernel:** If any initial setup cells (especially those installing Java or significantly changing Python packages *within the notebook*) prompt you to restart the kernel, please do so for the changes to take effect.

## Troubleshooting Common Setup Issues

*   **`ModuleNotFoundError: No module named 'langchain_looker_agent'` (in notebook):**
    *   Ensure you have run `pip install -r requirements.txt` (which includes `-e .`) from the project root in the virtual environment that your Jupyter kernel is using.
    *   Verify the `sys.path` manipulation in the notebook's initial setup cell is correctly pointing to the `src/` directory of your project.
    *   Make sure the package directory is `src/langchain_looker_agent/` and it contains `__init__.py` and `agent.py`.
*   **`ModuleNotFoundError: No module named 'jaydebeapi'` or `'jpype'`:**
    *   Run `pip install -r requirements.txt`.
*   **`ImportError: ... JVMNotFoundException ...` or `TypeError: Class org.apache.calcite.avatica.remote.looker.LookerDriver is not found` during `LookerSQLDatabase` initialization:**
    *   **Java Not Installed or `JAVA_HOME` Incorrect:** This is the most common cause. Verify Java 11+ is installed AND the `JAVA_HOME` environment variable is correctly set in the environment where Python/Jupyter is running, pointing to the JDK/JRE root directory (not the `bin/java` executable).
    *   **`LOOKER_JDBC_DRIVER_PATH` Incorrect:** Double-check the path in your `.env` file. Ensure the JAR file exists at that location (the notebook attempts to resolve it relative to the project root).
    *   **JDBC JAR Corrupted:** Try re-downloading the Avatica Looker JDBC driver.
*   **`ConnectionError` from `LookerSQLDatabase` (e.g., timeout, authentication failure):**
    *   Verify `LOOKER_INSTANCE_URL` (full `https://...` URL).
    *   Confirm `LOOKER_CLIENT_ID` and `LOOKER_CLIENT_SECRET` are correct and the associated Looker user has API3 access and necessary permissions for the SQL Interface and the specified `LOOKML_MODEL_NAME`.
    *   Check network connectivity from your execution environment (e.g., Vertex AI VM) to your Looker instance. Firewalls might block access.
*   **SQL Errors from Looker (e.g., "Object not found", syntax errors) during agent queries:**
    *   Review the `verbose=True` agent output to see the exact SQL generated.
    *   This usually indicates the LLM needs further prompting refinement or has made a mistake with Looker's specific SQL syntax (backticks, `AGGREGATE()`, `model.explore` format). The current agent prompt is heavily customized to mitigate this.
    *   Ensure the `LOOKML_MODEL_NAME` in your `.env` is correct and matches the model containing the Explores you expect to query.
*   **SLF4J Warnings (`Failed to load class "org.slf4j.impl.StaticLoggerBinder"`):**
    *   These are Java logging messages from the JDBC driver or its dependencies. They are generally harmless for functionality and indicate that a specific SLF4J logging backend wasn't found. You can usually ignore them.
