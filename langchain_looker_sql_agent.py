import re
import logging
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple, Callable

try:
    import jaydebeapi  
    import jpype  
except ImportError:  
    jaydebeapi = None
    jpype = None

# LangChain imports
from langchain_core.language_models import BaseLanguageModel
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain_core.tools import BaseTool, Tool 
from langchain.agents import create_react_agent, AgentExecutor
from langchain.agents.agent_toolkits.base import BaseToolkit

logger = logging.getLogger(__name__)

class LookerSQLDatabase:
    def __init__(
        self,
        looker_instance_url: str, 
        lookml_model_name: str, 
        client_id: str,
        client_secret: str,
        jdbc_driver_path: str, 
        jdbc_driver_class: str = "org.apache.calcite.avatica.remote.looker.LookerDriver",
        include_tables: Optional[List[str]] = None, 
        sample_rows_in_table_info: int = 3,
        connect_args: Optional[Dict[str, Any]] = None, 
    ):
        if not looker_instance_url.startswith(("http://", "https://")):
            self._looker_instance_url = f"https://{looker_instance_url}"
        else:
            self._looker_instance_url = looker_instance_url
            
        self._lookml_model_name_for_schema = lookml_model_name 
        self._client_id = client_id
        self._client_secret = client_secret
        self._jdbc_driver_path = jdbc_driver_path
        self._jdbc_driver_class = jdbc_driver_class
        self._include_tables = set(include_tables) if include_tables else None
        self._sample_rows_in_table_info = sample_rows_in_table_info
        self._connect_args = connect_args or {}
        self._connection: Optional[Any] = None
        
        try:
            self._connect()
            logger.info(f"Successfully connected to Looker SQL Interface (Avatica) for: {self._looker_instance_url} using model '{self._lookml_model_name_for_schema}'.")
        except Exception as e:
            logger.error(f"Failed to connect to Looker SQL Interface (Avatica) during initialization: {e}", exc_info=True)
            raise ConnectionError(f"Failed to connect to Looker SQL Interface (Avatica): {e}")

    def _connect(self) -> None:
        if self._connection:
            try:
                with self._connection.cursor() as cursor: cursor.execute("SELECT 1") 
                logger.debug("Existing Looker (Avatica) connection is alive.")
                return 
            except Exception as e:
                logger.warning(f"Existing Looker (Avatica) connection test failed: {e}. Attempting to reconnect.")
                try: self._connection.close()
                except Exception: pass 
                self._connection = None
        if jaydebeapi is None or jpype is None:
            raise ImportError(
                "jaydebeapi or jpype is not installed. Please install with `pip install JayDeBeApi JPype1`."
            )
        
        if not jpype.isJVMStarted(): 
            logger.info("JVM not started by JPype explicitly. JayDeBeApi will attempt to start it.")

        jdbc_url = f"jdbc:looker:url={self._looker_instance_url}"
        props = { "user": self._client_id, "password": self._client_secret }; props.update(self._connect_args) 
        logger.info(f"Attempting to connect to Looker (Avatica): {jdbc_url} with driver {self._jdbc_driver_class}")
        try:
            self._connection = jaydebeapi.connect(self._jdbc_driver_class, jdbc_url, props, jars=[self._jdbc_driver_path])
            logger.info("JayDeBeApi connection (Avatica) successful.")
        except Exception as e:
            err_msg = f"JayDeBeApi conn error (Avatica): {e.__class__.__name__}: {e}"
            if hasattr(e, 'jexception'): 
                try:
                    err_msg += f"\n   Java Exception: {e.jexception.getClass().getName()}"
                    err_msg += f"\n   Java Message: {e.jexception.getMessage()}"
                    if hasattr(e.jexception, 'getErrorCode'): err_msg += f"\n   JDBC Error Code: {e.jexception.getErrorCode()}"
                    if hasattr(e.jexception, 'getSQLState'): err_msg += f"\n   SQLState: {e.jexception.getSQLState()}"
                except Exception as je: logger.error(f"Error while trying to get details from Java exception: {je}")
            logger.error(err_msg, exc_info=True)
            raise ConnectionError(err_msg)

    @property
    def dialect(self) -> str: return "calcite" 

    def get_usable_table_names(self) -> Iterable[str]: 
        self._connect() 
        explore_names_found = set()
        try: db_meta_data = self._connection.jconn.getMetaData() 
        except Exception as e_meta:
            logger.error(f"Could not get DatabaseMetaData object: {e_meta}", exc_info=True); return []
        schema_to_try = self._lookml_model_name_for_schema
        logger.debug(f"Attempting to get tables (Explores) with schemaPattern (Model)='{schema_to_try}' via DatabaseMetaData")
        java_result_set = None
        try:
            java_result_set = db_meta_data.getTables(None, schema_to_try, "%", ["TABLE", "VIEW"])
            while java_result_set.next():
                explore_name = java_result_set.getString("TABLE_NAME") 
                if explore_name: explore_names_found.add(explore_name)
            if explore_names_found: logger.info(f"Found {len(explore_names_found)} Explores under model '{schema_to_try}'.")
            else: logger.warning(f"No Explores found under model '{schema_to_try}'. Check model name and permissions.")
        except Exception as e: logger.warning(f"Failed to get Explores for model '{schema_to_try}' (Avatica). Error: {e}", exc_info=True)
        finally:
            if java_result_set:
                try: java_result_set.close()
                except Exception as e_close: logger.error(f"Error closing ResultSet for tables: {e_close}")
        if not explore_names_found: logger.warning(f"No usable Explores found for model '{self._lookml_model_name_for_schema}'.")
        if self._include_tables: return sorted(list(self._include_tables.intersection(explore_names_found)))
        return sorted(list(explore_names_found))

    def get_table_info(self, table_names: Optional[List[str]] = None) -> str: 
        self._connect()
        try: 
            db_meta_data = self._connection.jconn.getMetaData()
        except Exception as e_meta: 
            logger.error(f"Could not get DatabaseMetaData object: {e_meta}", exc_info=True)
            return "Error: Could not access database metadata."
            
        all_usable_explores = self.get_usable_table_names()
        if table_names is None: 
            target_explores = all_usable_explores
        else:
            target_explores = [t for t in table_names if t in all_usable_explores]
            if len(target_explores) != len(table_names): 
                logger.warning(f"Requested Explores not found or not usable: {set(table_names)-set(target_explores)}")
        
        if not target_explores: 
            return "No Explores found or specified Explores are not accessible."

        table_info_strings = []
        for explore_name in target_explores:
            logger.debug(f"Getting enhanced schema for Explore: `{self._lookml_model_name_for_schema}`.`{explore_name}`")
            columns_details = [] # Store dictionaries of column details
            java_result_set_cols = None
            
            try:
                java_result_set_cols = db_meta_data.getColumns(None, self._lookml_model_name_for_schema, explore_name, "%")
                got_columns_metadata = False
                
                # Get column names from ResultSetMetaData to map Looker-specific fields by name
                # This is more robust than relying on fixed indices if they change.
                rs_meta = java_result_set_cols.getMetaData()
                col_count = rs_meta.getColumnCount()
                col_names_in_rs = [rs_meta.getColumnName(i + 1) for i in range(col_count)]
                # logger.debug(f"Metadata columns from getColumns for {explore_name}: {col_names_in_rs}")

                while java_result_set_cols.next():
                    got_columns_metadata = True
                    # Standard JDBC fields
                    column_name = java_result_set_cols.getString("COLUMN_NAME") # view.field
                    type_name = java_result_set_cols.getString("TYPE_NAME")    # SQL Type Name
                    
                    # Looker-specific fields - fetch them if available
                    # Use a helper to safely get string, defaulting to None or empty
                    def safe_get_string(rs, col_label):
                        try:
                            if col_label in col_names_in_rs:
                                val = rs.getString(col_label)
                                return val if val is not None else None # Return None, not "None" string
                        except Exception: # Catch if column doesn't exist or other error
                            pass
                        return None

                    def safe_get_boolean(rs, col_label):
                        try:
                            if col_label in col_names_in_rs:
                                return rs.getBoolean(col_label)
                        except Exception:
                            pass
                        return None # Or False by default if more appropriate

                    is_hidden = safe_get_boolean(java_result_set_cols, "HIDDEN")
                    
                    if is_hidden is True: # Explicitly check for True, as None means not found/applicable
                        logger.debug(f"Skipping hidden field: `{column_name}` in Explore `{explore_name}`")
                        continue # Skip hidden fields

                    field_label = safe_get_string(java_result_set_cols, "FIELD_LABEL")
                    field_alias = safe_get_string(java_result_set_cols, "FIELD_ALIAS") 
                    field_description = safe_get_string(java_result_set_cols, "FIELD_DESCRIPTION")
                    field_category = safe_get_string(java_result_set_cols, "FIELD_CATEGORY") # DIMENSION or MEASURE

                    if column_name and type_name:
                        columns_details.append({
                            "name": column_name,
                            "type": type_name,
                            "label": field_label,
                            "alias": field_alias,
                            "description": field_description,
                            "category": field_category
                        })

                if got_columns_metadata:
                    logger.info(f"Retrieved {len(columns_details)} visible columns for Explore `{explore_name}`.")
                else:
                    logger.warning(f"No column metadata found for Explore `{explore_name}`.")

            except Exception as e: 
                logger.error(f"Error retrieving columns metadata for Explore `{explore_name}`: {e}", exc_info=True)
                columns_details.append({"error": f"Error fetching columns: {e}"}) # Add error marker
            finally:
                if java_result_set_cols:
                    try: java_result_set_cols.close()
                    except Exception as e_close: logger.error(f"Error closing ResultSet for columns: {e_close}")
            
            # Construct the CREATE TABLE string with enhanced info
            create_table_header = f"CREATE TABLE `{self._lookml_model_name_for_schema}`.`{explore_name}` ("
            table_info_strings.append(create_table_header)

            if columns_details and not any("error" in cd for cd in columns_details):
                col_def_strings = []
                for col_detail in columns_details:
                    col_str = f"    `{col_detail['name']}` {col_detail['type']}"
                    comments = []
                    if col_detail.get('label') and col_detail['label'] != col_detail['name']: # Add label if different from name
                        comments.append(f"label: '{col_detail['label']}'")
                    if col_detail.get('alias'): 
                        comments.append(f"alias: '{col_detail['alias']}'")
                    if col_detail.get('category'):
                        comments.append(f"category: {col_detail['category']}")
                    if col_detail.get('description'):
                        # Truncate long descriptions for brevity in the prompt
                        desc_short = col_detail['description']
                        if len(desc_short) > 100: desc_short = desc_short[:97] + "..."
                        comments.append(f"description: '{desc_short}'")
                    
                    if comments:
                        col_str += f" -- {'; '.join(comments)}"
                    col_def_strings.append(col_str)
                
                table_info_strings.append(",\n".join(col_def_strings))
                table_info_strings.append(");")
            elif any("error" in cd for cd in columns_details):
                 table_info_strings.append("    -- Error retrieving full column details --")
                 table_info_strings.append(");")
            else:
                table_info_strings.append("    -- No column definitions retrieved --")
                table_info_strings.append(");")


            # Sample rows (logic remains similar, but only if columns were successfully fetched)
            if self._sample_rows_in_table_info > 0 and columns_details and not any("error" in cd for cd in columns_details):
                sample_query = "" 
                try:
                    with self._connection.cursor() as sample_cursor:
                        # Select first few *visible* columns for sample query
                        cols_for_sample_query_names = [cd['name'] for cd in columns_details[:5]] # Get raw 'view.field' names
                        
                        if not cols_for_sample_query_names:
                            logger.warning(f"No columns available for sample query on {explore_name} after filtering/errors. Skipping sample rows.")
                        else:
                            # Enclose these names in backticks for the query
                            cols_for_sample_query_str = ", ".join([f"`{name}`" for name in cols_for_sample_query_names])
                            sample_query = f'SELECT {cols_for_sample_query_str} FROM `{self._lookml_model_name_for_schema}`.`{explore_name}` LIMIT {self._sample_rows_in_table_info}'
                            
                            logger.info(f"Attempting sample query: {sample_query}")
                            sample_cursor.execute(sample_query) 
                            sample_col_names_from_desc = [f"`{desc[0]}`" for desc in sample_cursor.description] if sample_cursor.description else []
                            sample_rows_data = sample_cursor.fetchall()
                            sample_rows_str = f"\n/*\n{self._sample_rows_in_table_info} example rows from Explore `{self._lookml_model_name_for_schema}`.`{explore_name}` (selected columns: {cols_for_sample_query_str}):\n"
                            if sample_col_names_from_desc: sample_rows_str += f"({', '.join(sample_col_names_from_desc)})\n"
                            for row_data in sample_rows_data: sample_rows_str += f"{tuple(str(x) for x in row_data)}\n"
                            sample_rows_str += "*/"
                            table_info_strings.append(sample_rows_str)
                except jaydebeapi.DatabaseError as db_err: 
                    logger.error(f"DatabaseError fetching sample rows for {explore_name} (Query: {sample_query}): {db_err}", exc_info=False)
                    table_info_strings.append(f"\n/* Could not fetch sample rows for `{self._lookml_model_name_for_schema}`.`{explore_name}`. Database Error. */")
                except Exception as e_other: 
                    logger.error(f"Generic error fetching sample rows for {explore_name} (Query: {sample_query}): {e_other}", exc_info=False)
                    table_info_strings.append(f"\n/* Could not fetch sample rows for `{self._lookml_model_name_for_schema}`.`{explore_name}`. Error: {e_other.__class__.__name__}. */")
        
        return "\n".join(table_info_strings) # Use single newline to join parts of a single table's info

    def _run_query_internal(self, command: str) -> Tuple[List[str], List[Tuple[Any, ...]]]:
        self._connect()

        # Clean the command: remove trailing semicolon and potential markdown code blocks
        processed_command = command.strip().rstrip(';')
        if processed_command.startswith("```sql"): # Common markdown start
            processed_command = processed_command[6:] # Remove "```sql"
        elif processed_command.startswith("```"):
             processed_command = processed_command[3:] # Remove "```"
        if processed_command.endswith("```"):
            processed_command = processed_command[:-3] # Remove trailing "```"

        command_to_execute = processed_command.strip() # Final strip

        with self._connection.cursor() as cursor:
            try:
                logger.info(f"Executing SQL (Avatica) on Looker: {command_to_execute[:500]}{'...' if len(command_to_execute) > 500 else ''}")
                cursor.execute(command_to_execute) 
                col_names: List[str] = []; results_data: List[Tuple[Any, ...]] = []
                if cursor.description: 
                    col_names = [desc[0] for desc in cursor.description] 
                    results_data = cursor.fetchall()
                else: 
                    rc_msg = ""; rc = getattr(cursor, 'rowcount', -1)
                    if rc != -1: rc_msg = f" {rc} rows affected."
                    return [], [(f"Query executed successfully.{rc_msg}",)]
                return col_names, results_data
            except Exception as e:
                err_msg = f"Error executing query on Looker (Avatica): {e.__class__.__name__}: {e}"
                if hasattr(e, 'jexception'):
                    try: err_msg += f"\n Java Exc: {e.jexception.getClass().getName()}, Java Msg: {e.jexception.getMessage()}"
                    except: pass
                logger.error(f"{err_msg}\nQuery: {command_to_execute}", exc_info=True) 
                raise RuntimeError(f"{err_msg}\nQuery: {command_to_execute}")

    def run(self, command: str, fetch: str = "all") -> str:
        if fetch not in ("all", "one"): return f"Error: fetch parameter must be 'all' or 'one', got {fetch}"
        try:
            col_names, results_data = self._run_query_internal(command) 
            if not col_names and results_data and len(results_data) == 1 and len(results_data[0]) == 1:
                 return str(results_data[0][0])
            if not results_data:
                msg = "Query executed successfully. No results returned."
                if col_names: msg = f"Columns: {[f'`{c}`' for c in col_names]}\n{msg}"
                else: msg = f"Columns: []\n{msg}"
                return msg
            display_col_names = [f"`{c}`" if not (c.startswith('`') and c.endswith('`')) else c for c in col_names]
            string_results = [tuple(str(item) for item in row) for row in results_data]
            if fetch == "one" and string_results:
                return f"Columns: {display_col_names}\nResult: {string_results[0]}"
            return f"Columns: {display_col_names}\nResults:\n" + "\n".join(map(str, string_results))
        except Exception as e:
            logger.error(f"Error during 'run' method for command '{command[:100]}...': {e}", exc_info=True)
            return f"Error: {e}"

    def close(self):
        if self._connection:
            try: self._connection.close(); self._connection = None
            except Exception as e: logger.error(f"Error closing Looker (Avatica) connection: {e}", exc_info=True); self._connection = None
            else: logger.info(f"Looker SQL Interface (Avatica) connection closed for {self._looker_instance_url}.")

# --- LookerSQLToolkit (Using Tool.from_function) ---
class LookerSQLToolkit(BaseToolkit):
    db: LookerSQLDatabase 
    class Config: arbitrary_types_allowed = True
    def _get_table_info_wrapper(self, table_names_str: str) -> str:
        processed_table_names = []
        if not isinstance(table_names_str, str):
            if isinstance(table_names_str, list):
                # If it's already a list, process each item
                for name in table_names_str:
                    if isinstance(name, str):
                        processed_table_names.append(name.strip().strip('`')) # Strip backticks
                    else:
                        logger.warning(f"Non-string item in table_names list: {name}")
            elif table_names_str is None: 
                processed_table_names = None 
            else: 
                return "Error: Expected a comma-separated string or list of table names."
        else: # It's a string
            tables_list_from_str = [name.strip().strip('`') for name in table_names_str.split(',') if name.strip()] # Strip backticks here too
            processed_table_names = tables_list_from_str
        
        if not processed_table_names and table_names_str is not None and (isinstance(table_names_str, str) and table_names_str.strip() != ""):
             return "Please provide one or more table (Explore) names, or an empty string/None for all."
        
        return self.db.get_table_info(processed_table_names) # Pass the cleaned list or None

    def get_tools(self) -> List[BaseTool]:
        if not isinstance(self.db, LookerSQLDatabase):
             raise ValueError("LookerSQLToolkit requires a 'db' attribute of type LookerSQLDatabase.")
        return [
            Tool.from_function(
                func=lambda _: ", ".join(self.db.get_usable_table_names()),
                name="sql_db_list_tables",
                description="Input is an empty string. Output is a comma separated list of available 'tables' (Looker Explores)."
            ),
            Tool.from_function(
                func=self._get_table_info_wrapper,
                name="sql_db_schema",
                description="Input is a comma separated list of 'table' (Explore) names or a single table name. Output is the schema (LookML model, Explore, and `view.field` columns) and sample rows (if available) for those Explores. Use an empty string or pass no input to get schema for all available Explores."
            ),
            Tool.from_function(
                func=self.db.run,
                name="sql_db_query",
                description="Input to this tool is a detailed and syntactically correct SQL query (using backticks for identifiers like `model`.`explore` and `view.field`). Output is a result from the database. DO NOT end queries with a semicolon. If the query is not correct, an error message will be returned. If an error is returned, rewrite the query (especially checking backtick usage and semicolon rule) and try again. If you encounter an issue with an Unknown column, use 'sql_db_schema' to verify the correct table and column names (`view.field` format)."
            )
        ]

# --- Agent Creation Function ---
REACT_CORE_PROMPT_STRUCTURE = """
TOOLS:
------
You have access to the following tools:

{tools}

To use a tool, please use the following format:

Thought: Do I need to use a tool? Yes
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
When you have a response to say to the Human, or if you do not need to use a tool, you MUST use the format:

Thought: Do I need to use a tool? No
Final Answer: [your response here]
Begin!

Previous conversation history:
{chat_history}

New input: {input}
Thought:{agent_scratchpad}"""

# ** UPDATED PROMPT Incorporating all SQL Limitations **
LOOKER_SQL_SYSTEM_INSTRUCTIONS_TEMPLATE = """You are an agent designed to interact with Looker's Open SQL Interface, which uses a Calcite SQL dialect.
Given an input question, create a syntactically correct {dialect} query to run, then look at the query result and return the answer.

IMPORTANT SQL SYNTAX RULES AND LIMITATIONS FOR LOOKER (CALCITE/AVATICA):

1.  **Query Types:** Only `SELECT` queries are supported. Do NOT use `UPDATE`, `DELETE`, `INSERT`, DDL (e.g., `CREATE TABLE`), or other DML/DCL statements.
2.  **Identifiers:** All LookML Model Names (schema), Explore Names (tables), and field names (`view_name.field_name`) MUST be enclosed in backticks (`).
    -   Example: `FROM \`your_model_name\`.\`your_explore_name\``
    -   Example: `SELECT \`your_view.your_field\``
3. The `sql_db_schema` tool will return CREATE TABLE statements in the format: CREATE TABLE `model_name`.`explore_name` (`view.field` TYPE -- comments with label, description, etc., ...).
   **You MUST use the actual `model_name` (e.g., `analytics`) and `explore_name` shown in the schema output for your queries.**
   Pay attention to the comments (--) next to column definitions as they provide useful metadata like labels, descriptions, and category (dimension/measure).    
4.  **Joins:** DO NOT use explicit `JOIN` operators. Joins between views are pre-defined within the Looker Explores. Query fields from the views as if they are part of one large table for the given Explore, using the Explore name in the `FROM` clause.
5.  **Measures (Aggregations):**
    *   LookML measures (often indicated with `MEASURE<TYPE>` in the schema, e.g., `MEASURE<DOUBLE>`) MUST be wrapped in the `AGGREGATE()` function, using their exact `\`view_name.measure_field_name\`` identifier.
    *   Example: `SELECT AGGREGATE(\`orders_view.total_sales\`), \`users_view.country\``
    *   It is critically-important that you use the correct view_name for your measure_field_name, do not assume that every measure is found in the view name corresponding to the explore nane; for example if a measure field name with the `web_sessions_fact` explore is called `web_events_fact.avg_session_value`, do not make the mistake of using `web_sessions_fact.avg_session_value` in your query
    *   Measures (fields wrapped in `AGGREGATE()`) CANNOT be used in a `GROUP BY` clause. Only dimensions (non-measure fields) can be in `GROUP BY`.
...
Example Query Structure:
SELECT `view_a.dimension_one`, AGGREGATE(\`view_b.measure_field_exact_name\`)  <-- Emphasize exact name
FROM `actual_model_name_from_schema`.`actual_explore_name_from_schema`
WHERE `view_a.filter_dimension` = 'some_value'
GROUP BY `view_a.dimension_one`
LIMIT {top_k}
...
If you get an error while executing a query, REWRITE THE QUERY paying close attention to ALL the rules above, especially:
    a) Backticks for ALL identifiers.
    b) The `FROM \`model_name\`.\`explore_name\`` format, using the correct model name.
    c) Wrapping measures with `AGGREGATE()` using the **exact** `\`view_name.measure_field_name\`` from the schema, and NOT using measures in `GROUP BY`....
6.  **Subqueries & Window Functions:** DO NOT use subqueries (nested SELECT statements) or SQL window functions (e.g., `ROW_NUMBER() OVER (...)`, `RANK()`, `LAG()`, `LEAD()`). Construct simpler queries if possible, or break down complex requests.
7.  **Schema Information:** The `sql_db_schema` tool provides the schema. It will show `CREATE TABLE \`model_name\`.\`explore_name\` (\`view.field\` TYPE, ...)` and may indicate measures by type (e.g., `MEASURE<TYPE>`).
    **You MUST use the EXACT `model_name` and `explore_name` shown in this schema output for your queries.** Do not use placeholder examples like `my_lookml_model` or `actual_model_name` if the schema tool has provided the correct one.
8.  **No Semicolons:** DO NOT end SQL queries with a semicolon (`;`).
9.  **Counting All Records:** To count all records in an Explore, use the standard `SELECT COUNT(*) FROM \`model_name\`.\`explore_name\``.
10.  **Standard Aggregates vs. LookML Measures:** Standard SQL aggregate functions like `SUM(\`view.dimension_name\`)`, `AVG(\`view.dimension_name\`)` can be used on *dimension* fields. Use `AGGREGATE(\`view.measure_name\`)` **only** for pre-defined LookML measures identified in the schema (e.g., type `MEASURE<TYPE>`).

Example Query Structure:
SELECT `view_a.dimension_one`, AGGREGATE(\`view_a.measure_one\`)
FROM `actual_model_name_from_schema`.`actual_explore_name_from_schema`
WHERE `view_a.filter_dimension` = 'some_value'
GROUP BY `view_a.dimension_one`
LIMIT {top_k}

Unless the user specifies a specific number of examples they wish to obtain, always limit your query to at most {top_k} results using a LIMIT clause (without a semicolon).
Never query for all the columns from a specific Explore, only ask for the relevant columns (`view_name.field_name`) given the question.
If you get an error while executing a query, REWRITE THE QUERY paying close attention to ALL the rules above, especially:
    a) Backticks for ALL identifiers.
    b) The `FROM \`model_name\`.\`explore_name\`` format, using the correct model name.
    c) Wrapping LookML measures with `AGGREGATE()` and NOT using them in `GROUP BY`.
    d) No `JOIN`s, subqueries, or window functions.
    e) No trailing semicolon.
Then try again.
DO NOT make any DML or DDL statements.
If the question does not seem related to the database, just return "I don't know" as the answer.
The 'tables' are Looker Explores. The 'schema' is the Looker Model name (e.g., `analytics`).
"""

def create_looker_sql_agent(
    llm: BaseLanguageModel,
    toolkit: LookerSQLToolkit,
    agent_type: str = "react", 
    verbose: bool = False,
    top_k: int = 10,
    agent_executor_kwargs: Optional[Dict[str, Any]] = None,
    **kwargs: Dict[str, Any], 
) -> AgentExecutor:
    tools = toolkit.get_tools()
    
    formatted_looker_instructions = LOOKER_SQL_SYSTEM_INSTRUCTIONS_TEMPLATE.format(
        dialect=toolkit.db.dialect, 
        top_k=top_k
    )

    if agent_type == "react":
        full_prompt_template_str = formatted_looker_instructions + "\n\n" + REACT_CORE_PROMPT_STRUCTURE
        prompt = PromptTemplate.from_template(full_prompt_template_str)
        
        logger.info(f"Using ReAct prompt template for Looker SQL (dialect: {toolkit.db.dialect}).")
        # logger.debug(f"Full prompt template for agent:\n{prompt.template}")

        agent_runnable = create_react_agent(llm, tools, prompt)
    else:
        raise ValueError(f"Unsupported agent_type: {agent_type}. Currently only 'react' is supported.")
        
    default_executor_params = { "handle_parsing_errors": True }
    final_executor_args = default_executor_params.copy()
    if agent_executor_kwargs: final_executor_args.update(agent_executor_kwargs)
    final_executor_args.update(kwargs)

    return AgentExecutor(
        agent=agent_runnable, tools=tools, verbose=verbose, **final_executor_args
    )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("--- Running langchain-looker-sql-agent.py directly (Avatica version, requires env vars) ---")
    try:
        from dotenv import load_dotenv
        if load_dotenv(): logger.info(".env file loaded for direct script test.")
        else: logger.warning(".env file not found. Relying on existing environment variables.")
    except ImportError: logger.warning("python-dotenv not installed, cannot load .env file.")

    required_env_vars = [
        "LOOKER_INSTANCE_URL", "LOOKML_MODEL_NAME", 
        "LOOKER_CLIENT_ID", "LOOKER_CLIENT_SECRET", "LOOKER_JDBC_DRIVER_PATH",
        "OPENAI_API_KEY" 
    ]
    missing_vars_for_test = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars_for_test:
        logger.error(f"Missing environment variables for direct test: {missing_vars_for_test}. Skipping live test.")
    else:
        logger.info("All required environment variables found for direct test.")
        try:
            from langchain_openai import ChatOpenAI
            test_llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo")

            test_db = LookerSQLDatabase(
                looker_instance_url=os.environ["LOOKER_INSTANCE_URL"],
                lookml_model_name=os.environ["LOOKML_MODEL_NAME"],
                client_id=os.environ["LOOKER_CLIENT_ID"],
                client_secret=os.environ["LOOKER_CLIENT_SECRET"],
                jdbc_driver_path=os.environ["LOOKER_JDBC_DRIVER_PATH"],
                sample_rows_in_table_info=1 
            )
            logger.info(f"Test DB Dialect: {test_db.dialect}")
            test_explores = list(test_db.get_usable_table_names())
            logger.info(f"Test DB Usable Explores: {test_explores}")
            if test_explores:
                logger.info(f"Test DB Info for Explore '{test_explores[0]}':\n{test_db.get_table_info([test_explores[0]])}")
            
            test_toolkit = LookerSQLToolkit(db=test_db)
            test_agent_executor = create_looker_sql_agent(
                llm=test_llm, toolkit=test_toolkit, verbose=True,
                agent_executor_kwargs={"max_iterations": 5, "return_intermediate_steps": True} # Example
            )
            logger.info(f"Test Agent Executor created: {type(test_agent_executor)}")
            
            if test_explores:
                response = test_agent_executor.invoke({
                    "input": f"How many records are in the Explore named {test_explores[0]}?",
                    "chat_history": [] 
                    })
                logger.info(f"Test Agent response: {response}")
            else:
                 response = test_agent_executor.invoke({
                     "input": "List available Explores.",
                     "chat_history": []
                     })
                 logger.info(f"Test Agent response to list Explores: {response}")
            test_db.close()
        except Exception as e:
            logger.error(f"Error during direct script test: {e}", exc_info=True)
    logger.info("--- Direct script test of langchain-looker-sql-agent.py (Avatica) complete ---")
