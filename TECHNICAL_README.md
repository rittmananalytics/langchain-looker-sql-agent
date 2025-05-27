# Technical Approach: Interfacing LangChain with Looker's JDBC-based Open SQL Interface

1.  **Looker's Open SQL Interface (OSQI):**
    *   This is a JDBC endpoint (typically using Apache Calcite Avatica) that allows SQL-style queries against the data models defined in your Looker instance.
    *   **Authentication:** It uses Looker API3 Client ID and Client Secret passed as `user` and `password` JDBC properties.
    *   **JDBC Driver:** Requires the specific Looker Avatica JDBC driver (e.g., `avatica-<version>-looker.jar`). The driver class is typically `org.apache.calcite.avatica.remote.looker.LookerDriver`.
    *   **JDBC URL:** `jdbc:looker:url=https://your_looker_instance_url`
    *   **SQL Syntax:** The OSQI uses a Calcite SQL dialect. A crucial aspect is that all LookML identifiers (models, explores, view.fields) must be enclosed in **backticks (`` ` ``)** in SQL queries, e.g., ``SELECT `my_view.my_field` FROM `my_model`.`my_explore` ``. Also, trailing semicolons (`;`) should be omitted for programmatic execution.
    *   **Metadata Mapping:** The standard JDBC `DatabaseMetaData` interface is supported to a degree:
        *   `DatabaseMetaData.getSchemas()`: `TABLE_SCHEM` column returns the LookML model name.
        *   `DatabaseMetaData.getTables()`: `TABLE_SCHEM` is the model name, and `TABLE_NAME` is the LookML Explore name.
        *   `DatabaseMetaData.getColumns()`: `TABLE_SCHEM` (model), `TABLE_NAME` (explore), and `COLUMN_NAME` (`view_name.field_name` format). It also returns useful Looker-specific metadata like `FIELD_LABEL`, `FIELD_DESCRIPTION`, `FIELD_CATEGORY`, and `HIDDEN`.

2.  **LangChain's SQL Agent Framework:**
    *   Typically uses a `SQLDatabase` wrapper class (from `langchain_community.utilities`).
    *   A `SQLDatabaseToolkit` provides tools like `sql_db_query`, `sql_db_schema`, `sql_db_list_tables`.
    *   An agent (e.g., a ReAct agent) uses an LLM to decide which tool to use based on the user's question.

3.  **The Bridge: JayDeBeApi and a Custom Wrapper**
    *   Since standard LangChain SQL tools often assume SQLAlchemy or Python DB-API drivers, and Looker OSQI uses JDBC, we need a bridge.
    *   `JayDeBeApi` along with `JPype1` enables Python code to interact with JDBC drivers.
    *   We developed a custom Python class, `LookerSQLDatabase`, that mimics the interface expected by LangChain's SQL tools but uses `JayDeBeApi` internally to connect to Looker.

## LookerSQLDatabase Wrapper

*   **`__init__(self, looker_instance_url, lookml_model_name, ...)`:**
    *   Takes the Looker instance URL (full HTTPS URL), the target LookML model name (which will act as our SQL schema), API3 credentials, and the path to the Looker Avatica JDBC JAR.
    *   Stores the `lookml_model_name` to be used as the `schemaPattern` in metadata calls.

*   **`_connect(self)`:**
    *   Uses `jaydebeapi.connect()` with the driver class `org.apache.calcite.avatica.remote.looker.LookerDriver` and the URL `jdbc:looker:url=https://...`.
    *   Passes the Client ID as `user` and Client Secret as `password` in the connection properties.

*   **`dialect` (property):**
    *   Returns `"calcite"` to inform the LLM about the expected SQL variant.

*   **`get_usable_table_names(self)`:** (Returns Explore names)
    *   Obtains a `java.sql.DatabaseMetaData` object from the active JDBC connection (`self._connection.jconn.getMetaData()`).
    *   Calls `db_meta_data.getTables(None, self._lookml_model_name_for_schema, "%", ["TABLE", "VIEW"])`.
    *   Iterates the Java `ResultSet` to extract the `TABLE_NAME` for each Explore within the specified LookML model.

*   **`get_table_info(self, table_names: Optional[List[str]] = None)`:** (Describes an Explore and its fields)
    *   For each requested Explore name:
        *   Calls `db_meta_data.getColumns(None, self._lookml_model_name_for_schema, explore_name, "%")`.
        *   Iterates the Java `ResultSet` to extract:
            *   Standard JDBC info: `COLUMN_NAME` (which is `view_name.field_name`) and `TYPE_NAME`.
            *   Looker-specific metadata: `HIDDEN`, `FIELD_LABEL`, `FIELD_ALIAS`, `FIELD_DESCRIPTION`, `FIELD_CATEGORY`.
        *   Filters out any fields where `HIDDEN` is true.
        *   Formats the schema string as a `CREATE TABLE` statement, incorporating the Looker-specific metadata as SQL comments for the LLM's context:
            ```sql
            CREATE TABLE `your_model_name`.`your_explore_name` (
                `view_a.field_one` VARCHAR -- label: 'User Friendly Field 1'; category: DIMENSION; description: 'Details about field one...'
                `view_b.field_two` INTEGER -- label: 'Field Two'; category: MEASURE; description: 'Other details...'
            );
            ```
        *   Fetches a few sample rows by querying for a subset of the visible columns (e.g., the first 5) with a `LIMIT` clause. This avoids issues with `SELECT *` on complex Explores and ensures no trailing semicolon.

*   **`run(self, command: str, ...)`:**
    *   Takes a SQL string (expected to be generated by the LLM).
    *   Proactively removes any trailing semicolon from the command.
    *   Executes the command using a `jaydebeapi` cursor.
    *   Formats and returns the results as a string.

## LangChain Toolkit and Agent

1.  **`LookerSQLToolkit(BaseToolkit)`:**
    *   This toolkit takes an instance of our `LookerSQLDatabase`.
    *   It uses `Tool.from_function` to wrap the methods of our `LookerSQLDatabase` instance (`get_usable_table_names`, `get_table_info`, `run`) into LangChain `Tool` objects. This approach provides flexibility and avoids potential Pydantic type validation issues that might arise if trying to force our custom class into tools expecting `langchain_community.utilities.SQLDatabase`.
    *   The tool descriptions are crafted to guide the LLM, for example, reminding it about backtick usage and no semicolons for `sql_db_query`.

2.  **`create_looker_sql_agent(...)`:**
    *   This factory function assembles the agent.
    *   It takes an LLM instance and our `LookerSQLToolkit`.
    *   **Prompt Engineering is Key:** It constructs a detailed system prompt for a ReAct-style agent. This prompt:
        *   Instructs the LLM about the Calcite SQL dialect used by Looker's OSQI.
        *   Emphasizes the **critical SQL syntax rules:**
            *   All identifiers (model, explore, `view.field`) MUST use backticks.
            *   The `FROM` clause MUST be `` `model_name`.`explore_name` ``.
            *   How to use the information from the `sql_db_schema` tool to find the correct `model_name` and `explore_name`.
            *   **No trailing semicolons.**
        *   Guides the LLM on how to use the tools and the ReAct framework's Thought/Action/Observation loop.
    *   It then uses `langchain.agents.create_react_agent` to create the agent runnable and wraps it in an `AgentExecutor`.
    *   The `AgentExecutor` can also be configured with `ConversationBufferMemory` for multi-turn conversations.

## Demonstration: Conversational Querying**

We provide an example Jupyter Notebook (`notebooks/looker_agent_conversational_test.ipynb`) that enables interactive querying. A typical flow looks like this:

1.  **User:** "How many website pageviews did we get this month?"
2.  **Agent (Thought/Action):**
    *   Thought: "I need to find pageview data. First, I'll list available Explores."
    *   Action: `sql_db_list_tables`
    *   Action Input: `""`
    *   Observation: (List of Explores including `web_sessions_fact`)
    *   Thought: "`web_sessions_fact` seems relevant. I need its schema."
    *   Action: `sql_db_schema`
    *   Action Input: `web_sessions_fact`
    *   Observation: (Schema of `web_sessions_fact`, including column `` `web_events_fact.total_page_views` `` and date dimensions like `` `web_sessions_fact.session_start_ts_month` ``)
    *   Thought: "I have the fields. I'll construct a query to sum pageviews for the current month."
    *   Action: `sql_db_query`
    *   Action Input: `SELECT SUM(\`web_events_fact.total_page_views\`) AS total_pageviews FROM \`analytics\`.\`web_sessions_fact\` WHERE EXTRACT(YEAR FROM \`web_sessions_fact.session_start_ts_month\`) = EXTRACT(YEAR FROM CURRENT_DATE) AND EXTRACT(MONTH FROM \`web_sessions_fact.session_start_ts_month\`) = EXTRACT(MONTH FROM CURRENT_DATE)`
    *   Observation: (Result, e.g., `Columns: ['\`total_pageviews\`'] Results: ('6209',)` )
    *   Thought: "I have the answer."
    *   Final Answer: "The total number of website pageviews for this month is 6,209."

This iterative process, including the LLM's ability to self-correct if its initial SQL is flawed (e.g., by forgetting the model name qualifier, as observed in testing), is a powerful feature of the ReAct agent framework.

**Challenges and Learnings**

*   **JDBC Metadata via JayDeBeApi/JPype:** Directly calling `java.sql.DatabaseMetaData` methods like `getTables` and `getColumns` on the raw Java connection object (`_connection.jconn.getMetaData()`) and iterating the Java `ResultSet` was necessary, as these methods weren't directly exposed on the `JayDeBeApi` cursor.
*   **Looker OSQI SQL Specifics:** Strict adherence to backticked identifiers (`` `model`.`explore` ``, `` `view.field` ``) and the omission of trailing semicolons are critical for successful query execution.
*   **Robust Prompting:** Detailed instructions in the agent's system prompt are vital to guide the LLM on these SQL syntax nuances and the structure of Looker data (model as schema, explore as table).
*   **Sample Row Fetching:** Initial attempts with `SELECT *` for sample rows led to `JsonParseException` from the Avatica driver, likely due to Looker returning non-JSON error responses for certain complex Explores or those with implicit filter requirements. Switching to selecting a limited number of specific, simple columns for samples proved more reliable.
*   **SLF4J Warnings:** These Java logging messages are common and generally harmless if a specific SLF4J binder isn't on the classpath.
