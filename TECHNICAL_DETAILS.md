# LangChain Looker SQL Agent: Technical Details & Design

This document provides a deeper dive into the technical implementation, Looker-specific SQL considerations, and design choices for the `langchain-looker-agent`.

## Core Components

1.  **`LookerSQLDatabase` Class (`src/langchain_looker_agent/agent.py`):**
    *   **Purpose:** Acts as a Pythonic wrapper around the Looker Open SQL Interface (OSQI) using its Avatica-based JDBC driver. It mimics the interface of `langchain_community.utilities.SQLDatabase` to be compatible with LangChain's SQL agent tooling.
    *   **Connectivity (`_connect`):**
        *   Uses `jaydebeapi` and `JPype1` to establish a JDBC connection.
        *   Requires the Looker Avatica JDBC driver JAR (e.g., `avatica-<version>-looker.jar`).
        *   Driver Class: `org.apache.calcite.avatica.remote.looker.LookerDriver`.
        *   JDBC URL Format: `jdbc:looker:url=https://<your_looker_instance_url>`.
        *   Authentication: Uses Looker API3 Client ID (as JDBC `user`) and Client Secret (as JDBC `password`).
    *   **Dialect (`dialect` property):** Returns `"calcite"` to inform the LLM, as Looker's OSQI uses a Calcite SQL parser.
    *   **Metadata Retrieval:**
        *   Relies on the standard `java.sql.DatabaseMetaData` interface, accessed via `connection.jconn.getMetaData()`.
        *   `get_usable_table_names()`: Calls `DatabaseMetaData.getTables()` using the `lookml_model_name` (provided at initialization) as the `schemaPattern` to list available Looker Explores (which are treated as queryable "tables").
        *   `get_table_info()`:
            *   For each Explore, calls `DatabaseMetaData.getColumns()` (again, using `lookml_model_name` as `schemaPattern` and Explore name as `tableNamePattern`) to fetch field details.
            *   Extracts standard JDBC column info (`COLUMN_NAME`, `TYPE_NAME`).
            *   **Crucially, it also extracts Looker-specific metadata columns** returned by this driver, such as `HIDDEN`, `FIELD_LABEL`, `FIELD_ALIAS`, `FIELD_DESCRIPTION`, and `FIELD_CATEGORY`.
            *   Filters out fields where `HIDDEN` is true.
            *   Formats the schema as a `CREATE TABLE` string using Looker's required backtick notation: ``CREATE TABLE `model_name`.`explore_name` ( ... )``.
            *   Enriches column definitions with Looker metadata as SQL comments: `` `view_name.field_name` VARCHAR -- label: 'User-Friendly Label'; category: DIMENSION; description: '...' ``.
            *   Optionally fetches sample rows by executing a `SELECT` query for the first few *visible* columns with a `LIMIT` clause (avoids problematic `SELECT *`).
    *   **Query Execution (`run` and `_run_query_internal`):**
        *   Takes a SQL command string.
        *   **Pre-processing:** Automatically strips trailing semicolons (`;`) and common markdown code fences (```sql ... ```) from the input command before execution, as the Looker JDBC driver expects single statements without these.
        *   Executes the cleaned SQL using a `jaydebeapi` cursor.
        *   Formats results (column names and rows) into a string for the LLM.

2.  **`LookerSQLToolkit(BaseToolkit)`:**
    *   Takes an instance of `LookerSQLDatabase`.
    *   Uses `Tool.from_function` to create LangChain `Tool` objects for:
        *   `sql_db_list_tables` (wraps `db.get_usable_table_names`, joins list into a string).
        *   `sql_db_schema` (wraps `db.get_table_info` via a helper `_get_table_info_wrapper` to handle string parsing of table names).
        *   `sql_db_query` (wraps `db.run`).
    *   Tool descriptions are carefully crafted to guide the LLM on input format and Looker specifics (e.g., Explores, backticks, no semicolons).

3.  **`create_looker_sql_agent(llm, toolkit, ...)`:**
    *   A factory function to create a LangChain ReAct agent.
    *   **Prompt Engineering:** This is critical. It combines:
        *   `LOOKER_SQL_SYSTEM_INSTRUCTIONS_TEMPLATE`: Detailed instructions to the LLM about the Calcite SQL dialect, Looker's data structure (Model as schema, Explore as table, `view.field` as column), mandatory backtick syntax for all identifiers, use of `AGGREGATE()` for LookML measures, restrictions (no `JOIN`s, subqueries, window functions, DML), and the "no semicolon" rule. It also guides the LLM on how to use the schema information provided by the `sql_db_schema` tool to construct valid queries.
        *   `REACT_CORE_PROMPT_STRUCTURE`: A standard template for the ReAct agent's operational loop (Thought, Action, Action Input, Observation).
    *   Uses `langchain.agents.create_react_agent` with the combined prompt and the tools from `LookerSQLToolkit`.
    *   Returns an `AgentExecutor`, which can be configured with memory (e.g., `ConversationBufferMemory`).

## Looker Open SQL Interface: Key SQL Syntax and Limitations

The LangChain agent (and the LLM it uses) must generate SQL that adheres to the following specifics of Looker's OSQI (Avatica/Calcite):

*   **Query Type:** Only `SELECT` statements are supported.
*   **Identifiers (Backticks ` `` `):**
    *   LookML Model Name (Schema): `` `your_model_name` ``
    *   LookML Explore Name (Table): `` `your_explore_name` ``
    *   LookML Field Name (Column): `` `view_name.field_name` ``
    *   **All these identifiers MUST be enclosed in backticks in SQL queries.**
    *   **FROM Clause:** `FROM \`model_name\`.\`explore_name\``
*   **LookML Measures:**
    *   Must be queried using the `AGGREGATE(\`view_name.measure_name\`)` function.
    *   The `view_name` within `AGGREGATE()` must be the view where the measure is defined.
    *   Measures (fields wrapped in `AGGREGATE()`) **cannot** be used in a `GROUP BY` clause. Only dimensions can.
*   **Standard SQL Aggregates:** Functions like `COUNT(*)`, `SUM(\`dimension_name\`)`, `AVG(\`dimension_name\`)` can be used on dimension fields. Do not wrap dimensions in `AGGREGATE()`.
*   **Joins:** No explicit `JOIN` operators (e.g., `LEFT JOIN`, `INNER JOIN`). Joins between views are pre-defined within the LookML Explores. Query fields from all joined views as if they are part of one large table for the given Explore.
*   **Unsupported SQL Features:**
    *   Subqueries (nested `SELECT` statements).
    *   SQL window functions (e.g., `ROW_NUMBER() OVER (...)`, `RANK()`, `LAG()`).
    *   DML (`INSERT`, `UPDATE`, `DELETE`) and DDL (`CREATE TABLE`, etc.).
*   **Semicolons (`;`):** SQL statements sent programmatically via JDBC should NOT end with a semicolon. The `LookerSQLDatabase` class attempts to strip these.
*   **Filters (`always_filter`, `conditionally_filter`, Filter-Only Fields):** The Looker documentation details how Explores with these LookML parameters require corresponding `WHERE`/`HAVING` clauses or special JSON syntax for filter-only fields. While this agent prototype doesn't explicitly build logic to *automatically satisfy* these, the LLM *might* be able to construct valid queries if given enough context or if it learns from errors. Queries failing due to unsatisfied mandatory filters are a known limitation if not handled by LLM prompting or by querying Explores without such strict requirements.

## Design Choice: Custom `LookerSQLDatabase` vs. New SQLAlchemy Dialect

A key design decision for this prototype was to implement a custom `LookerSQLDatabase` class that mimics the interface of LangChain's `SQLDatabase` utility, rather than attempting to create a new SQLAlchemy dialect for Looker's Open SQL Interface. The primary reasons for this approach are:

1.  **Nature of Looker's SQL Interface:** It's an abstraction layer accessed via a specific JDBC driver, not a standard relational database directly supported by Python DB-API v2.0 drivers that SQLAlchemy typically uses. We use `JayDeBeApi` to bridge Python to Java's JDBC.
2.  **Complexity of Full SQLAlchemy Dialect:** Creating a SQLAlchemy dialect is a significant undertaking, requiring deep knowledge of SQLAlchemy internals and complex mapping for SQL compilation, type handling, and introspection. This complexity is largely unnecessary for an agent primarily executing LLM-generated SQL strings.
3.  **LangChain's `SQLDatabase` Utility:** This provides a simpler, targeted interface (methods for dialect, listing tables, getting schema, running queries) sufficient for LangChain SQL agents. Our custom class implements this interface.
4.  **Focus and Reusability:** This approach allows us to leverage existing LangChain agent infrastructure (`create_react_agent`, `AgentExecutor`) and tools (by wrapping our methods with `Tool.from_function`) with minimal friction.
5.  **Minimal Dependencies:** Avoids making SQLAlchemy a hard dependency for this specific Looker integration.