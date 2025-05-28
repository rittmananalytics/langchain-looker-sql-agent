"""
LangChain SQL Agent for Looker's Open SQL Interface.

This module provides the components to create a LangChain agent capable of 
interacting with a Looker instance using its JDBC-based Open SQL Interface 
(Avatica/Calcite). It allows for natural language querying of Looker Explores.

Key Components:
- LookerSQLDatabase: A custom class that wraps the Looker JDBC connection,
  mimicking the interface of LangChain's SQLDatabase utility. It handles
  connecting to Looker, fetching metadata (Explores as tables, Fields as columns),
  and executing SQL queries. It's specifically designed to work with Looker's
  SQL dialect (Calcite) including backticked identifiers and AGGREGATE() for measures.
- LookerSQLToolkit: A LangChain toolkit that bundles database interaction tools
  (list tables/Explores, get schema, query database) using the LookerSQLDatabase.
- create_looker_sql_agent: A factory function to create a LangChain ReAct agent
  pre-configured with the LookerSQLToolkit and a specialized system prompt
  guiding the LLM on Looker's specific SQL syntax and data structures.

The agent enables conversational interaction with Looker-governed data,
leveraging LookML models as the semantic layer.
"""
import re
import logging
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple, Callable

try:
    import jaydebeapi  
    import jpype  
except ImportError:  
    # This allows the module to be imported for type checking or documentation
    # even if jaydebeapi/jpype are not installed, but will fail at runtime if used.
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
    """
    A database interface for Looker's Open SQL Interface using JDBC.

    This class provides a LangChain-compatible interface to a Looker instance,
    allowing an LLM agent to query Looker Explores as if they were SQL tables.
    It handles JDBC connectivity via JayDeBeApi, metadata retrieval using
    JDBC DatabaseMetaData (mapping LookML models to schemas and Explores to tables),
    and execution of SQL queries compliant with Looker's Calcite dialect.

    Attributes:
        dialect (str): The SQL dialect, returns "calcite".
    """
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
    ) -> None:
        """
        Initializes the LookerSQLDatabase instance.

        Args:
            looker_instance_url: The full HTTPS URL of the Looker instance 
                (e.g., "https://yourcompany.cloud.looker.com").
            lookml_model_name: The name of the LookML model to be treated as the
                primary SQL schema for metadata calls.
            client_id: The Looker API3 Client ID for authentication.
            client_secret: The Looker API3 Client Secret for authentication.
            jdbc_driver_path: The local file system path to the Looker Avatica JDBC
                driver JAR file (e.g., "avatica-1.26.0-looker.jar").
            jdbc_driver_class: The fully qualified class name of the Looker JDBC driver.
                Defaults to "org.apache.calcite.avatica.remote.looker.LookerDriver".
            include_tables: An optional list of Explore names to include. If provided,
                only these Explores will be considered "usable tables". If None,
                all accessible Explores under the `lookml_model_name` will be listed.
            sample_rows_in_table_info: The number of sample rows to fetch and include
                in the schema information provided by `get_table_info`. Set to 0
                to disable sample row fetching.
            connect_args: An optional dictionary of additional properties to be
                passed to the JDBC driver during connection.
        
        Raises:
            ConnectionError: If the connection to Looker fails during initialization.
            ImportError: If `jaydebeapi` or `jpype` are not installed when attempting to connect.
        """
        if not looker_instance_url.startswith(("http://", "https://")):
            self._looker_instance_url: str = f"https://{looker_instance_url}"
        else:
            self._looker_instance_url = looker_instance_url
            
        self._lookml_model_name_for_schema: str = lookml_model_name 
        self._client_id: str = client_id
        self._client_secret: str = client_secret
        self._jdbc_driver_path: str = jdbc_driver_path
        self._jdbc_driver_class: str = jdbc_driver_class
        self._include_tables: Optional[set[str]] = set(include_tables) if include_tables else None
        self._sample_rows_in_table_info: int = sample_rows_in_table_info
        self._connect_args: Dict[str, Any] = connect_args or {}
        self._connection: Optional[Any] = None # Should be jaydebeapi.Connection if successful
        
        if jaydebeapi is None or jpype is None:
            logger.warning("jaydebeapi or jpype not imported. Connection will fail if attempted at runtime.")

        try:
            self._connect()
            logger.info(f"Successfully connected to Looker SQL Interface (Avatica) for: {self._looker_instance_url} using model '{self._lookml_model_name_for_schema}'.")
        except Exception as e:
            logger.error(f"Failed to connect to Looker SQL Interface (Avatica) during initialization: {e}", exc_info=True)
            raise ConnectionError(f"Failed to connect to Looker SQL Interface (Avatica): {e}")

    def _connect(self) -> None:
        """
        Establishes or validates the JDBC connection to Looker.
        
        This method is called internally to ensure an active connection exists
        before performing database operations. It handles reconnection if needed.

        Raises:
            ImportError: If `jaydebeapi` or `jpype` are not installed (runtime check).
            ConnectionError: If the JDBC connection fails for any reason.
        """
        if self._connection:
            try:
                # It's good practice to use a new cursor for a test query
                with self._connection.cursor() as cursor: 
                    cursor.execute("SELECT 1") 
                logger.debug("Existing Looker (Avatica) connection is alive.")
                return 
            except Exception as e: # Catch broad JayDeBeApi/JDBC errors
                logger.warning(f"Existing Looker (Avatica) connection test failed: {e}. Attempting to reconnect.")
                try: 
                    self._connection.close()
                except Exception: 
                    pass # Ignore errors during close of an already potentially broken connection
                self._connection = None
        
        if jaydebeapi is None or jpype is None: # Runtime check if not caught by import
            raise ImportError(
                "jaydebeapi or jpype is not installed. Please install with `pip install JayDeBeApi JPype1`."
            )
        
        if not jpype.isJVMStarted(): 
            logger.info("JVM not started by JPype explicitly. JayDeBeApi will attempt to start it.")
            # For explicit JVM start with classpath if needed:
            # try:
            #     if not jpype.isJVMStarted():
            #         logger.info(f"Starting JVM with classpath including: {self._jdbc_driver_path}")
            #         jpype.startJVM(jpype.getDefaultJVMPath(), f"-Djava.class.path={self._jdbc_driver_path}", convertStrings=False)
            # except Exception as e_jvm:
            #     logger.error(f"Error explicitly starting JVM: {e_jvm}", exc_info=True)

        jdbc_url: str = f"jdbc:looker:url={self._looker_instance_url}"
        props: Dict[str, Any] = { "user": self._client_id, "password": self._client_secret }
        props.update(self._connect_args) 
        
        logger.info(f"Attempting to connect to Looker (Avatica): {jdbc_url} with driver {self._jdbc_driver_class}")
        try:
            self._connection = jaydebeapi.connect(self._jdbc_driver_class, jdbc_url, props, jars=[self._jdbc_driver_path])
            logger.info("JayDeBeApi connection (Avatica) successful.")
        except Exception as e: # Catch all exceptions from jaydebeapi.connect
            err_msg: str = f"JayDeBeApi conn error (Avatica): {e.__class__.__name__}: {e}"
            if hasattr(e, 'jexception'): # If it's a wrapped Java exception from JPype
                try:
                    java_exception = e.jexception # type: ignore
                    err_msg += f"\n   Java Exception: {java_exception.getClass().getName()}"
                    err_msg += f"\n   Java Message: {java_exception.getMessage()}"
                    if hasattr(java_exception, 'getErrorCode'): 
                        err_msg += f"\n   JDBC Error Code: {java_exception.getErrorCode()}"
                    if hasattr(java_exception, 'getSQLState'): 
                        err_msg += f"\n   SQLState: {java_exception.getSQLState()}"
                except Exception as je: 
                    logger.error(f"Error while trying to get details from Java exception: {je}")
            logger.error(err_msg, exc_info=True)
            raise ConnectionError(err_msg)

    @property
    def dialect(self) -> str:
        """
        Returns the SQL dialect used by Looker's Open SQL Interface.

        This is important for guiding the LLM on SQL syntax generation.
        Looker's OSQI uses a Calcite-based SQL dialect.

        Returns:
            str: The dialect name, "calcite".
        """
        return "calcite" 

    def get_usable_table_names(self) -> Iterable[str]: 
        """
        Retrieves a list of usable "tables" (Looker Explores) from the configured
        LookML model.

        Uses JDBC DatabaseMetaData to list tables where the schema name matches
        the `lookml_model_name` provided during initialization.

        Returns:
            Iterable[str]: A sorted list of Explore names. Returns an empty list
                           if no Explores are found or if metadata cannot be accessed.
        """
        self._connect() 
        explore_names_found: set[str] = set()
        try: 
            # Access the underlying Java connection object for DatabaseMetaData
            db_meta_data: Any = self._connection.jconn.getMetaData() # type: ignore 
        except Exception as e_meta:
            logger.error(f"Could not get DatabaseMetaData object: {e_meta}", exc_info=True)
            return []
        
        schema_to_try: Optional[str] = self._lookml_model_name_for_schema
        logger.debug(f"Attempting to get tables (Explores) with schemaPattern (Model)='{schema_to_try}' via DatabaseMetaData")
        java_result_set: Optional[Any] = None # Should be java.sql.ResultSet
        try:
            java_result_set = db_meta_data.getTables(None, schema_to_try, "%", ["TABLE", "VIEW"])
            while java_result_set.next():
                explore_name: Optional[str] = java_result_set.getString("TABLE_NAME") 
                if explore_name: 
                    explore_names_found.add(explore_name)
            
            if explore_names_found: 
                logger.info(f"Found {len(explore_names_found)} Explores under model '{schema_to_try}'.")
            else: 
                logger.warning(f"No Explores found under model '{schema_to_try}'. Check model name and user permissions.")
        except Exception as e: 
            logger.warning(f"Failed to get Explores for model '{schema_to_try}' (Avatica). Error: {e}", exc_info=True)
        finally:
            if java_result_set:
                try: 
                    java_result_set.close()
                except Exception as e_close: 
                    logger.error(f"Error closing ResultSet for tables: {e_close}")
        
        if not explore_names_found: 
            logger.warning(f"No usable Explores found for model '{self._lookml_model_name_for_schema}'.")
        
        if self._include_tables: 
            return sorted(list(self._include_tables.intersection(explore_names_found)))
        return sorted(list(explore_names_found))

    def get_table_info(self, table_names: Optional[List[str]] = None) -> str: 
        """
        Retrieves schema information for the specified "tables" (Looker Explores).

        For each Explore, it fetches column details (name, type, and Looker-specific
        metadata like labels, descriptions, category) using JDBC DatabaseMetaData.
        Hidden fields are excluded. It formats this into a `CREATE TABLE`-like string.
        Optionally, it also fetches and appends sample rows.

        Args:
            table_names: An optional list of Explore names for which to retrieve
                schema information. If None, information for all usable Explores
                under the configured LookML model is fetched.

        Returns:
            str: A string containing the `CREATE TABLE`-like definitions and
                 sample rows for the specified Explores. Returns an error message
                 if metadata cannot be accessed or no Explores are found.
        """
        self._connect()
        try: 
            db_meta_data: Any = self._connection.jconn.getMetaData() # type: ignore
        except Exception as e_meta: 
            logger.error(f"Could not get DatabaseMetaData object: {e_meta}", exc_info=True)
            return "Error: Could not access database metadata."
            
        all_usable_explores: Iterable[str] = self.get_usable_table_names()
        target_explores: Iterable[str]
        if table_names is None: 
            target_explores = all_usable_explores
        else:
            target_explores = [t for t in table_names if t in all_usable_explores]
            if len(target_explores) != len(table_names): 
                missing_explores = set(table_names) - set(target_explores)
                logger.warning(f"Requested Explores not found or not usable: {missing_explores}")
        
        if not target_explores: 
            return "No Explores found or specified Explores are not accessible."

        table_info_strings: List[str] = []
        for explore_name in target_explores:
            logger.debug(f"Getting enhanced schema for Explore: `{self._lookml_model_name_for_schema}`.`{explore_name}`")
            columns_details: List[Dict[str, Any]] = [] 
            java_result_set_cols: Optional[Any] = None # Should be java.sql.ResultSet
            
            try:
                java_result_set_cols = db_meta_data.getColumns(None, self._lookml_model_name_for_schema, explore_name, "%")
                got_columns_metadata: bool = False
                
                rs_meta: Any = java_result_set_cols.getMetaData() # java.sql.ResultSetMetaData
                col_count: int = rs_meta.getColumnCount()
                # Store metadata column names in uppercase for case-insensitive lookup, as JDBC standard is often uppercase
                col_names_in_rs: List[str] = [rs_meta.getColumnName(i + 1).upper() for i in range(col_count)]

                def safe_get_string(rs: Any, col_label_standard_jdbc: str) -> Optional[str]:
                    col_label_upper: str = col_label_standard_jdbc.upper()
                    try:
                        if col_label_upper in col_names_in_rs:
                            val: Optional[str] = rs.getString(col_label_upper) # Use uppercase for lookup
                            return val if val is not None else None 
                        else:
                            logger.debug(f"Metadata column '{col_label_upper}' not found in ResultSet for getColumns.")
                    except Exception as e_safe_get:
                        logger.debug(f"Safe get string failed for '{col_label_upper}': {e_safe_get}")
                    return None

                def safe_get_boolean(rs: Any, col_label_standard_jdbc: str) -> Optional[bool]:
                    col_label_upper: str = col_label_standard_jdbc.upper()
                    try:
                        if col_label_upper in col_names_in_rs:
                            return rs.getBoolean(col_label_upper) # Use uppercase for lookup
                        else:
                            logger.debug(f"Metadata column '{col_label_upper}' not found for getBoolean.")
                    except Exception as e_safe_get_bool:
                         logger.debug(f"Safe get boolean failed for '{col_label_upper}': {e_safe_get_bool}")
                    return None

                while java_result_set_cols.next():
                    got_columns_metadata = True
                    column_name: Optional[str] = java_result_set_cols.getString("COLUMN_NAME") 
                    type_name: Optional[str] = java_result_set_cols.getString("TYPE_NAME")    
                    
                    is_hidden: Optional[bool] = safe_get_boolean(java_result_set_cols, "HIDDEN")
                    
                    if is_hidden is True: 
                        logger.debug(f"Skipping hidden field: `{column_name}` in Explore `{explore_name}`")
                        continue 

                    field_label: Optional[str] = safe_get_string(java_result_set_cols, "FIELD_LABEL")
                    field_alias: Optional[str] = safe_get_string(java_result_set_cols, "FIELD_ALIAS") 
                    field_description: Optional[str] = safe_get_string(java_result_set_cols, "FIELD_DESCRIPTION")
                    field_category: Optional[str] = safe_get_string(java_result_set_cols, "FIELD_CATEGORY") 

                    if column_name and type_name:
                        columns_details.append({
                            "name": column_name, "type": type_name, "label": field_label,
                            "alias": field_alias, "description": field_description,
                            "category": field_category
                        })

                if got_columns_metadata and columns_details: # Check if any non-hidden columns were processed
                    logger.info(f"Retrieved {len(columns_details)} visible columns for Explore `{explore_name}`.")
                elif got_columns_metadata: # Metadata was fetched but all columns were hidden or invalid
                     logger.info(f"All columns for Explore `{explore_name}` were hidden or invalid.")
                else: # No metadata rows at all
                    logger.warning(f"No column metadata found for Explore `{explore_name}`.")

            except Exception as e: 
                logger.error(f"Error retrieving columns metadata for Explore `{explore_name}`: {e}", exc_info=True)
                columns_details.append({"error": f"Error fetching columns: {e}"})
            finally:
                if java_result_set_cols:
                    try: java_result_set_cols.close()
                    except Exception as e_close: logger.error(f"Error closing ResultSet for columns: {e_close}")
            
            create_table_header: str = f"CREATE TABLE `{self._lookml_model_name_for_schema}`.`{explore_name}` ("
            table_info_strings.append(create_table_header)

            if columns_details and not any("error" in cd for cd in columns_details):
                col_def_strings: List[str] = []
                for col_detail in columns_details:
                    col_str: str = f"    `{col_detail['name']}` {col_detail['type']}"
                    comments: List[str] = []
                    if col_detail.get('label') and col_detail['label'] != col_detail['name']:
                        comments.append(f"label: '{col_detail['label']}'")
                    if col_detail.get('alias'): 
                        comments.append(f"alias: '{col_detail['alias']}'")
                    if col_detail.get('category'):
                        comments.append(f"category: {col_detail['category']}")
                    if col_detail.get('description'):
                        desc_short: Optional[str] = col_detail['description']
                        if desc_short and len(desc_short) > 100: desc_short = desc_short[:97] + "..."
                        if desc_short: comments.append(f"description: '{desc_short}'")
                    if comments: col_str += f" -- {'; '.join(comments)}"
                    col_def_strings.append(col_str)
                table_info_strings.append(",\n".join(col_def_strings)); table_info_strings.append(");")
            elif any("error" in cd for cd in columns_details):
                 table_info_strings.append("    -- Error retrieving full column details --"); table_info_strings.append(");")
            else: # No columns_details or it's empty
                table_info_strings.append("    -- No column definitions retrieved --"); table_info_strings.append(");")

            if self._sample_rows_in_table_info > 0 and columns_details and not any("error" in cd for cd in columns_details):
                sample_query: str = "" 
                try:
                    with self._connection.cursor() as sample_cursor:
                        cols_for_sample_query_names: List[str] = [cd['name'] for cd in columns_details[:5]]
                        if not cols_for_sample_query_names:
                            logger.warning(f"No columns available for sample query on {explore_name} after filtering/errors. Skipping sample rows.")
                        else:
                            cols_for_sample_query_str: str = ", ".join([f"`{name}`" for name in cols_for_sample_query_names])
                            sample_query = f'SELECT {cols_for_sample_query_str} FROM `{self._lookml_model_name_for_schema}`.`{explore_name}` LIMIT {self._sample_rows_in_table_info}'
                            logger.info(f"Attempting sample query: {sample_query}")
                            sample_cursor.execute(sample_query) 
                            sample_col_names_from_desc: List[str] = [f"`{desc[0]}`" for desc in sample_cursor.description] if sample_cursor.description else []
                            sample_rows_data: List[Tuple[Any,...]] = sample_cursor.fetchall()
                            sample_rows_str: str = f"\n/*\n{self._sample_rows_in_table_info} example rows from Explore `{self._lookml_model_name_for_schema}`.`{explore_name}` (selected columns: {cols_for_sample_query_str}):\n"
                            if sample_col_names_from_desc: sample_rows_str += f"({', '.join(sample_col_names_from_desc)})\n"
                            for row_data_tuple in sample_rows_data: sample_rows_str += f"{tuple(str(x) for x in row_data_tuple)}\n"
                            sample_rows_str += "*/"; table_info_strings.append(sample_rows_str)
                except jaydebeapi.DatabaseError as db_err: 
                    logger.error(f"DatabaseError fetching sample rows for {explore_name} (Query: {sample_query}): {db_err}", exc_info=False)
                    table_info_strings.append(f"\n/* Could not fetch sample rows for `{self._lookml_model_name_for_schema}`.`{explore_name}`. Database Error. */")
                except Exception as e_other: 
                    logger.error(f"Generic error fetching sample rows for {explore_name} (Query: {sample_query}): {e_other}", exc_info=False)
                    table_info_strings.append(f"\n/* Could not fetch sample rows for `{self._lookml_model_name_for_schema}`.`{explore_name}`. Error: {e_other.__class__.__name__}. */")
        return "\n".join(table_info_strings)

    def _run_query_internal(self, command: str) -> Tuple[List[str], List[Tuple[Any, ...]]]:
        """
        Executes a SQL command after ensuring connection and cleaning the command.

        Args:
            command: The SQL command string to execute. Trailing semicolons and
                     markdown code fences are stripped.

        Returns:
            A tuple: (list_of_column_names, list_of_result_rows).
            For non-SELECT or no-row commands, column_names is empty and
            result_rows may contain a status message.

        Raises:
            RuntimeError: If query execution fails.
        """
        self._connect()
        processed_command: str = command.strip().rstrip(';')
        if processed_command.startswith("```sql"): processed_command = processed_command[6:]
        elif processed_command.startswith("```"): processed_command = processed_command[3:]
        if processed_command.endswith("```"): processed_command = processed_command[:-3]
        command_to_execute: str = processed_command.strip()

        with self._connection.cursor() as cursor:
            try:
                logger.info(f"Executing SQL (Avatica) on Looker: {command_to_execute[:500]}{'...' if len(command_to_execute) > 500 else ''}")
                cursor.execute(command_to_execute) 
                col_names: List[str] = []; results_data: List[Tuple[Any, ...]] = []
                if cursor.description: 
                    col_names = [desc[0] for desc in cursor.description] 
                    results_data = cursor.fetchall()
                else: 
                    rc_msg: str = ""; rc: int = getattr(cursor, 'rowcount', -1)
                    if rc != -1: rc_msg = f" {rc} rows affected."
                    return [], [(f"Query executed successfully.{rc_msg}",)]
                return col_names, results_data
            except Exception as e: # Catch all from execute or fetchall
                err_msg: str = f"Error executing query on Looker (Avatica): {e.__class__.__name__}: {e}"
                if hasattr(e, 'jexception'):
                    try: 
                        java_exception = e.jexception # type: ignore
                        err_msg += f"\n Java Exc: {java_exception.getClass().getName()}, Java Msg: {java_exception.getMessage()}"
                    except: pass
                logger.error(f"{err_msg}\nQuery: {command_to_execute}", exc_info=True) 
                raise RuntimeError(f"{err_msg}\nQuery: {command_to_execute}")

    def run(self, command: str, fetch: str = "all") -> str:
        """
        Executes a SQL command and returns the results as a formatted string.

        Args:
            command: The SQL query string to execute.
            fetch: Determines result formatting. "all" returns all rows,
                   "one" returns only the first row.

        Returns:
            A string representation of the query results or an error message.
        """
        if fetch not in ("all", "one"): return f"Error: fetch parameter must be 'all' or 'one', got {fetch}"
        try:
            col_names, results_data = self._run_query_internal(command) 
            if not col_names and results_data and len(results_data) == 1 and len(results_data[0]) == 1:
                 return str(results_data[0][0])
            if not results_data:
                msg: str = "Query executed successfully. No results returned."
                if col_names: msg = f"Columns: {[f'`{c}`' for c in col_names]}\n{msg}"
                else: msg = f"Columns: []\n{msg}"
                return msg
            display_col_names: List[str] = [f"`{c}`" if not (c.startswith('`') and c.endswith('`')) else c for c in col_names]
            string_results: List[Tuple[str, ...]] = [tuple(str(item) for item in row) for row in results_data]
            if fetch == "one" and string_results:
                return f"Columns: {display_col_names}\nResult: {string_results[0]}"
            return f"Columns: {display_col_names}\nResults:\n" + "\n".join(map(str, string_results))
        except Exception as e:
            logger.error(f"Error during 'run' method for command '{command[:100]}...': {e}", exc_info=True)
            return f"Error: {e}"

    def close(self) -> None:
        """Closes the JDBC connection to Looker if it is open."""
        if self._connection:
            try: 
                self._connection.close()
                self._connection = None
            except Exception as e: 
                logger.error(f"Error closing Looker (Avatica) connection: {e}", exc_info=True)
                self._connection = None # Ensure it's marked as closed
            else: 
                logger.info(f"Looker SQL Interface (Avatica) connection closed for {self._looker_instance_url}.")

# --- LookerSQLToolkit ---
class LookerSQLToolkit(BaseToolkit):
    """
    Toolkit for LangChain agents to interact with LookerSQLDatabase.

    Provides tools for listing Explores, getting Explore schemas (including
    Looker-specific metadata), and querying data.

    Attributes:
        db (LookerSQLDatabase): An instance of the LookerSQLDatabase.
    """
    db: LookerSQLDatabase 
    
    class Config: 
        arbitrary_types_allowed = True
        
    def _get_table_info_wrapper(self, table_names_str: str) -> str:
        """
        Wrapper for `db.get_table_info` to parse LLM-provided table name strings.
        Handles comma-separated strings, lists, or None/empty string for all tables.
        Strips backticks from input table names.

        Args:
            table_names_str: A string of table names (Explores), potentially
                             comma-separated, or a list of table names, or None/empty.

        Returns:
            The formatted schema string from `db.get_table_info`.
        """
        processed_table_names: Optional[List[str]]
        if not isinstance(table_names_str, str):
            if isinstance(table_names_str, list):
                processed_table_names = [
                    name.strip().strip('`') for name in table_names_str if isinstance(name, str) and name.strip()
                ]
                if len(processed_table_names) != len(table_names_str): # type: ignore
                    logger.warning(f"Some non-string or empty items found and removed from table_names list input: {table_names_str}")
            elif table_names_str is None: 
                processed_table_names = None 
            else: 
                return "Error: sql_db_schema tool expected a comma-separated string, a list of table names, or None/empty string."
        else: # It's a string
            if table_names_str.strip() == "": 
                processed_table_names = None
            else:
                processed_table_names = [name.strip().strip('`') for name in table_names_str.split(',') if name.strip()]
        
        if processed_table_names == [] and table_names_str is not None and \
           (isinstance(table_names_str, str) and table_names_str.strip() != ""):
             # This case means the input string was not empty but resulted in an empty list after processing
             return "Please provide one or more valid table (Explore) names, or an empty string/None for all."
        
        return self.db.get_table_info(processed_table_names)

    def get_tools(self) -> List[BaseTool]:
        """
        Returns a list of LangChain tools for interacting with the Looker database.
        
        Returns:
            List[BaseTool]: Tools for listing Explores, getting Explore schema,
                            and querying the database.
        """
        if not isinstance(self.db, LookerSQLDatabase):
             raise ValueError("LookerSQLToolkit requires a 'db' attribute of type LookerSQLDatabase.")
        return [
            Tool.from_function(
                func=lambda _: ", ".join(self.db.get_usable_table_names()),
                name="sql_db_list_tables",
                description="Input is an empty string. Output is a comma separated list of available 'tables' (which are Looker Explores that can be queried)."
            ),
            Tool.from_function(
                func=self._get_table_info_wrapper,
                name="sql_db_schema",
                description="Input is a comma separated list of 'table' (Explore) names or a single table name. Output is the schema (LookML model, Explore, and `view.field` columns with their types and descriptions/labels as comments) and sample rows (if available) for those Explores. Use an empty string or pass no input (None) to get schema for all available Explores."
            ),
            Tool.from_function(
                func=self.db.run,
                name="sql_db_query",
                description="Input to this tool is a detailed and syntactically correct SQL query (using backticks for identifiers like `model`.`explore` and `view.field`). Output is a result from the database. DO NOT end queries with a semicolon. If the query is not correct, an error message will be returned. If an error is returned, rewrite the query (especially checking backtick usage, model/explore names, and semicolon rule) and try again. If you encounter an issue with an Unknown column, use 'sql_db_schema' to verify the correct table and column names (`view.field` format)."
            )
        ]

# --- Agent Creation Function ---
REACT_CORE_PROMPT_STRUCTURE: str = """
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

LOOKER_SQL_SYSTEM_INSTRUCTIONS_TEMPLATE: str = """You are an agent designed to interact with Looker's Open SQL Interface, which uses a Calcite SQL dialect.
Given an input question, create a syntactically correct {dialect} query to run, then look at the query result and return the answer.

IMPORTANT SQL SYNTAX RULES AND LIMITATIONS FOR LOOKER (CALCITE/AVATICA):

1.  **Query Types:** Only `SELECT` queries are supported. Do NOT use `UPDATE`, `DELETE`, `INSERT`, DDL (e.g., `CREATE TABLE`), or other DML/DCL statements.
2.  **Identifiers:** All LookML Model Names (schema), Explore Names (tables), and field names (`view_name.field_name`) MUST be enclosed in backticks (`).
    -   Example: `FROM \`your_model_name\`.\`your_explore_name\``
    -   Example: `SELECT \`your_view.your_field\``
3.  The `sql_db_schema` tool will return CREATE TABLE statements in the format: CREATE TABLE `model_name`.`explore_name` (`view.field` TYPE -- comments with label, description, etc., ...).
    **You MUST use the actual `model_name` (e.g., `analytics`) and `explore_name` shown in the schema output for your queries.** Do not use placeholder examples like `my_lookml_model` or `actual_model_name` if the schema tool has provided the correct one.
    Pay attention to the comments (--) next to column definitions as they provide useful metadata like labels, descriptions, and category (dimension/measure).    
4.  **Joins:** DO NOT use explicit `JOIN` operators. Joins between views are pre-defined within the Looker Explores. Query fields from the views as if they are part of one large table for the given Explore, using the Explore name in the `FROM` clause.
5.  **Measures (Aggregations):**
    *   LookML measures (often indicated with `MEASURE<TYPE>` in the schema, e.g., `MEASURE<DOUBLE>`) MUST be wrapped in the `AGGREGATE()` function, using their exact `\`view_name.measure_field_name\`` identifier.
    *   Example: `SELECT AGGREGATE(\`orders_view.total_sales\`), \`users_view.country\``
    *   It is critically-important that you use the correct view_name for your measure_field_name, do not assume that every measure is found in the view name corresponding to the explore nane; for example if a measure field name with the `web_sessions_fact` explore is called `web_events_fact.avg_session_value`, do not make the mistake of using `web_sessions_fact.avg_session_value` in your query
    *   Measures (fields wrapped in `AGGREGATE()`) CANNOT be used in a `GROUP BY` clause. Only dimensions (non-measure fields) can be in `GROUP BY`.
6.  **Subqueries & Window Functions:** DO NOT use subqueries (nested SELECT statements) or SQL window functions (e.g., `ROW_NUMBER() OVER (...)`, `RANK()`, `LAG()`, `LEAD()`). Construct simpler queries if possible, or break down complex requests.
7.  **Schema Information:** The `sql_db_schema` tool provides the schema. It will show `CREATE TABLE \`model_name\`.\`explore_name\` (\`view.field\` TYPE, ...)` and may indicate measures by type (e.g., `MEASURE<TYPE>`).
    **You MUST use the EXACT `model_name` and `explore_name` shown in this schema output for your queries.** Do not use placeholder examples like `my_lookml_model` or `actual_model_name` if the schema tool has provided the correct one.
8.  **No Semicolons:** DO NOT end SQL queries with a semicolon (`;`).
9.  **Counting All Records:** To count all records in an Explore, use the standard `SELECT COUNT(*) FROM \`model_name\`.\`explore_name\``.
10. **Standard Aggregates vs. LookML Measures:** Standard SQL aggregate functions like `SUM(\`view.dimension_name\`)`, `AVG(\`view.dimension_name\`)` can be used on *dimension* fields. Use `AGGREGATE(\`view.measure_name\`)` **only** for pre-defined LookML measures identified in the schema (e.g., type `MEASURE<TYPE>`).

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
    """
    Constructs a LangChain ReAct agent for interacting with Looker.

    This function sets up a ReAct agent pre-configured with the LookerSQLToolkit
    and a specialized system prompt guiding the LLM on Looker's specific SQL syntax
    (Calcite dialect, backticked identifiers, AGGREGATE() for measures, etc.)
    and data structures (Models, Explores, View.Fields).

    Args:
        llm: The LangChain BaseLanguageModel instance to use (e.g., ChatOpenAI).
        toolkit: An instance of LookerSQLToolkit containing the tools for Looker interaction.
        agent_type: The type of agent to create. Currently, only "react" is supported.
        verbose: Boolean flag to set the AgentExecutor to verbose mode for detailed logging.
        top_k: Default number of rows to limit queries to if not specified by the user.
               This is also formatted into the system prompt for the LLM.
        agent_executor_kwargs: A dictionary of keyword arguments to pass directly to
                               the AgentExecutor constructor (e.g., for memory, max_iterations).
        **kwargs: Additional keyword arguments to pass to the AgentExecutor constructor,
                  which will be merged with agent_executor_kwargs.

    Returns:
        An initialized LangChain AgentExecutor ready to interact with Looker.

    Raises:
        ValueError: If an unsupported `agent_type` is specified.
    """
    tools: List[BaseTool] = toolkit.get_tools()
    
    formatted_looker_instructions: str = LOOKER_SQL_SYSTEM_INSTRUCTIONS_TEMPLATE.format(
        dialect=toolkit.db.dialect, 
        top_k=top_k
    )

    if agent_type == "react":
        full_prompt_template_str: str = formatted_looker_instructions + "\n\n" + REACT_CORE_PROMPT_STRUCTURE
        prompt: PromptTemplate = PromptTemplate.from_template(full_prompt_template_str)
        
        logger.info(f"Using ReAct prompt template for Looker SQL (dialect: {toolkit.db.dialect}).")
        # logger.debug(f"Full prompt template for agent:\n{prompt.template}")

        agent_runnable: Runnable = create_react_agent(llm, tools, prompt) # type: ignore
    else:
        raise ValueError(f"Unsupported agent_type: {agent_type}. Currently only 'react' is supported.")
        
    # Consolidate arguments for AgentExecutor
    default_executor_params: Dict[str, Any] = { "handle_parsing_errors": True }
    final_executor_args: Dict[str, Any] = default_executor_params.copy()
    if agent_executor_kwargs: 
        final_executor_args.update(agent_executor_kwargs)
    # Any additional kwargs passed to create_looker_sql_agent also go to AgentExecutor
    final_executor_args.update(kwargs) 

    return AgentExecutor(
        agent=agent_runnable, 
        tools=tools, 
        verbose=verbose, 
        **final_executor_args
    )

# Self-test block
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("--- Running langchain_looker_sql_agent.py directly (Avatica version, requires env vars) ---")
    
    try:
        from dotenv import load_dotenv
        project_root_for_dotenv = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        # Try .env in parent (common for src/pkg/module.py structure) or current dir
        if not load_dotenv(dotenv_path=os.path.join(project_root_for_dotenv, ".env")):
            if not load_dotenv(): # Try current directory as a fallback
                 logger.warning(".env file not found in common locations. Relying on existing environment variables.")
            else:
                logger.info(".env file loaded from current directory for direct script test.")
        else:
             logger.info(f".env file loaded from {project_root_for_dotenv} for direct script test.")
    except ImportError: 
        logger.warning("python-dotenv not installed, cannot load .env file. Relying on existing environment variables.")

    required_env_vars: List[str] = [
        "LOOKER_INSTANCE_URL", "LOOKML_MODEL_NAME", 
        "LOOKER_CLIENT_ID", "LOOKER_CLIENT_SECRET", "LOOKER_JDBC_DRIVER_PATH",
        "OPENAI_API_KEY" 
    ]
    missing_vars_for_test: List[str] = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars_for_test:
        logger.error(f"Missing environment variables for direct test: {missing_vars_for_test}. Skipping live test.")
    else:
        logger.info("All required environment variables found for direct test.")
        try:
            from langchain_openai import ChatOpenAI # type: ignore
            test_llm: BaseLanguageModel = ChatOpenAI(temperature=0, model="gpt-3.5-turbo")

            jdbc_driver_path_from_env: Optional[str] = os.environ.get("LOOKER_JDBC_DRIVER_PATH")
            resolved_jdbc_path: Optional[str] = None
            if jdbc_driver_path_from_env:
                if not os.path.isabs(jdbc_driver_path_from_env):
                    # Assume relative path from where python command is run, or project root if more complex
                    # For a script in src/pkg/module.py, project root might be two levels up.
                    # This path resolution might need adjustment based on execution context.
                    # For simplicity, let's assume it's relative to CWD or an absolute path.
                    resolved_jdbc_path = os.path.abspath(jdbc_driver_path_from_env) 
                else:
                    resolved_jdbc_path = jdbc_driver_path_from_env
            
            if not resolved_jdbc_path or not os.path.exists(resolved_jdbc_path):
                 logger.error(f"JDBC Driver not found at resolved path: {resolved_jdbc_path}. Check LOOKER_JDBC_DRIVER_PATH.")
                 exit(1) # Or raise an error

            logger.info(f"Using JDBC Driver at: {resolved_jdbc_path}")

            test_db: LookerSQLDatabase = LookerSQLDatabase(
                looker_instance_url=os.environ["LOOKER_INSTANCE_URL"],
                lookml_model_name=os.environ["LOOKML_MODEL_NAME"],
                client_id=os.environ["LOOKER_CLIENT_ID"],
                client_secret=os.environ["LOOKER_CLIENT_SECRET"],
                jdbc_driver_path=resolved_jdbc_path,
                sample_rows_in_table_info=0 
            )
            logger.info(f"Test DB Dialect: {test_db.dialect}")
            test_explores: List[str] = list(test_db.get_usable_table_names())
            logger.info(f"Test DB Usable Explores: {test_explores[:5]}{'...' if len(test_explores)>5 else ''} (Total: {len(test_explores)})")
            
            if test_explores:
                logger.info(f"Test DB Info for Explore '{test_explores[0]}':\n{test_db.get_table_info([test_explores[0]])}")
            
            test_toolkit: LookerSQLToolkit = LookerSQLToolkit(db=test_db)
            test_agent_executor: AgentExecutor = create_looker_sql_agent(
                llm=test_llm, 
                toolkit=test_toolkit, 
                verbose=True, 
                agent_executor_kwargs={"max_iterations": 3, "return_intermediate_steps": False} 
            )
            logger.info(f"Test Agent Executor created: {type(test_agent_executor)}")
            
            test_question: str = "List available Explores."
            if test_explores:
                test_question = f"How many records are in the Explore named {test_explores[0]}?"
            
            logger.info(f"Invoking agent with question: {test_question}")
            response: Dict[str, Any] = test_agent_executor.invoke({ # type: ignore
                "input": test_question,
                "chat_history": [] 
                })
            logger.info(f"Test Agent response: {response.get('output')}")
            
            test_db.close()
        except Exception as e:
            logger.error(f"Error during direct script test: {e}", exc_info=True)
            
    logger.info("--- Direct script test of langchain_looker_sql_agent.py (Avatica) complete ---")