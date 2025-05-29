import pytest
from unittest.mock import MagicMock, patch 
# Corrected: Add all necessary typing imports at the top level of the file
from typing import Optional, List, Dict, Any, Iterable, Tuple, Callable 

# Import the class to be tested
from langchain_looker_agent import LookerSQLDatabase # Assumes src layout and -e . install

# --- Mock Fixtures ---

@pytest.fixture
def mock_java_objects() -> Dict[str, Any]:
    """
    Creates a dictionary of reusable mock Java objects for JDBC metadata,
    including DatabaseMetaData and helper class for ResultSet iteration.
    """
    
    # Helper class to simulate java.sql.ResultSet iteration and data access
    class MockResultSet:
        def __init__(self, rows_data: List[Dict[str, Any]]):
            self._rows = iter(rows_data)
            self.current_row: Optional[Dict[str, Any]] = None # Uses imported Optional
            self._closed: bool = False

        def next(self) -> bool:
            if self._closed: raise Exception("ResultSet closed")
            try:
                self.current_row = next(self._rows)
                return True
            except StopIteration:
                self.current_row = None
                return False

        def getString(self, column_label_or_index: Any) -> Optional[str]: # Uses imported Optional
            if self._closed: raise Exception("ResultSet closed")
            if self.current_row:
                key_to_use = ""
                if isinstance(column_label_or_index, str):
                    key_to_use = column_label_or_index.upper() 
                elif isinstance(column_label_or_index, int): 
                    # This mock currently only supports string labels for simplicity for getString
                    # For a more complete mock, map known indices for getString if needed
                    # For now, assume string labels are used for getString by the main code
                    key_to_use = f"COL_INDEX_{column_label_or_index}" 
                
                value = self.current_row.get(key_to_use)
                return str(value) if value is not None else None
            return None

        def getBoolean(self, column_label_or_index: Any) -> Optional[bool]: # Uses imported Optional
            if self._closed: raise Exception("ResultSet closed")
            if self.current_row:
                key_to_use = ""
                if isinstance(column_label_or_index, str):
                    key_to_use = column_label_or_index.upper()
                elif isinstance(column_label_or_index, int):
                     key_to_use = f"COL_INDEX_{column_label_or_index}"

                value = self.current_row.get(key_to_use)
                if isinstance(value, bool): return value
                if isinstance(value, str): return value.upper() == 'TRUE'
                if isinstance(value, int): return value != 0
            return None 

        def getMetaData(self) -> MagicMock: 
            mock_rs_meta = MagicMock(name="ResultSetMetaDataForColumns")
            mock_rs_meta.getColumnCount.return_value = 11 
            col_names_map = {
                1: "TABLE_CAT", 2: "TABLE_SCHEM", 3: "TABLE_NAME", 
                4: "COLUMN_NAME", 5: "DATA_TYPE", 6: "TYPE_NAME",
                7: "HIDDEN", 8: "FIELD_LABEL", 9: "FIELD_DESCRIPTION", 
                10: "FIELD_CATEGORY", 11: "FIELD_ALIAS"
            } 
            mock_rs_meta.getColumnName.side_effect = lambda i: col_names_map.get(i, f"OTHER_COL_{i}")
            return mock_rs_meta

        def close(self) -> None: 
            self._closed = True

    table_rows_data = [
        {"TABLE_NAME": "explore_one", "TABLE_SCHEM": "test_model"},
        {"TABLE_NAME": "explore_two", "TABLE_SCHEM": "test_model"},
    ]

    cols_explore_one_data = [
        {"COLUMN_NAME": "view1.fieldA", "TYPE_NAME": "VARCHAR", "HIDDEN": False, 
         "FIELD_LABEL": "Field A Label", "FIELD_DESCRIPTION": "Description for Field A", 
         "FIELD_CATEGORY": "DIMENSION", "FIELD_ALIAS": "AliasA"},
        {"COLUMN_NAME": "view1.fieldB_measure", "TYPE_NAME": "MEASURE<DOUBLE>", "HIDDEN": False,
         "FIELD_LABEL": "Field B Measure", "FIELD_DESCRIPTION": "Desc for Field B", 
         "FIELD_CATEGORY": "MEASURE", "FIELD_ALIAS": None},
        {"COLUMN_NAME": "view1.hidden_field", "TYPE_NAME": "VARCHAR", "HIDDEN": True,
         "FIELD_LABEL": "A Hidden Field", "FIELD_DESCRIPTION": "This is hidden",
         "FIELD_CATEGORY": "DIMENSION", "FIELD_ALIAS": None}
    ]
    
    mock_db_meta = MagicMock(name="DatabaseMetaData")
    # Use list() to ensure a fresh iterator from MockResultSet each time getTables is called
    mock_db_meta.getTables.side_effect = lambda cat, schema, table, types: MockResultSet(list(table_rows_data))

    def get_columns_router(catalog: Optional[str], schema_pattern: Optional[str], 
                           table_name_pattern: str, column_name_pattern: Optional[str]) -> MockResultSet:
        if table_name_pattern == "explore_one":
            return MockResultSet(list(cols_explore_one_data)) # Fresh iterator
        return MockResultSet([]) 

    mock_db_meta.getColumns.side_effect = get_columns_router

    return {"db_meta_data": mock_db_meta}


@pytest.fixture
def mock_jdbc_connection(mock_java_objects: Dict[str, Any]) -> MagicMock:
    """Mocks the JayDeBeApi connection and configures its metadata calls."""
    mock_conn = MagicMock(name="JayDeBeApiConnection")
    mock_cursor = MagicMock(name="JayDeBeApiCursor")

    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.jconn.getMetaData.return_value = mock_java_objects["db_meta_data"]

    mock_cursor.description = [('col_a',0,0,0,0,0,0), ('col_b',0,0,0,0,0,0)] 
    mock_cursor.fetchall.return_value = [("val1", 100), ("val2", 200)]
    mock_cursor.rowcount = -1
    
    return mock_conn

@pytest.fixture
def db_instance(mock_jdbc_connection: MagicMock) -> LookerSQLDatabase:
    """Creates a LookerSQLDatabase instance with a mocked JDBC connection."""
    with patch('jaydebeapi.connect', return_value=mock_jdbc_connection) as mock_jaydebeapi_connect, \
         patch('jpype.isJVMStarted', return_value=True): 
            db = LookerSQLDatabase(
                looker_instance_url="https://test.looker.com",
                lookml_model_name="test_model",
                client_id="test_id",
                client_secret="test_secret",
                jdbc_driver_path="/mock/driver.jar",
                sample_rows_in_table_info=1 
            )
            mock_jaydebeapi_connect.assert_called_once() 
            assert db._connection is mock_jdbc_connection 
            return db

# --- Actual Tests ---

def test_looker_sql_database_init_connects(db_instance: LookerSQLDatabase) -> None:
    """Test that LookerSQLDatabase's _connection is set after initialization."""
    assert db_instance._connection is not None 

def test_dialect_property(db_instance: LookerSQLDatabase) -> None:
    """Test the dialect property."""
    assert db_instance.dialect == "calcite"

def test_get_usable_table_names(db_instance: LookerSQLDatabase, mock_java_objects: Dict[str, Any]) -> None:
    """Test fetching usable table (Explore) names."""
    db_meta_data_mock = mock_java_objects["db_meta_data"]
    tables = list(db_instance.get_usable_table_names())
    db_meta_data_mock.getTables.assert_called_with(None, "test_model", "%", ["TABLE", "VIEW"])
    assert tables == ["explore_one", "explore_two"]

def test_get_table_info_explore_one(db_instance: LookerSQLDatabase, mock_java_objects: Dict[str, Any], mock_jdbc_connection: MagicMock) -> None:
    """Test get_table_info for a specific Explore, including Looker metadata and sample rows."""
    db_meta_data_mock = mock_java_objects["db_meta_data"]
    mock_cursor_for_sample = mock_jdbc_connection.cursor.return_value.__enter__.return_value 
    mock_cursor_for_sample.description = [('view1.fieldA',0,0,0,0,0,0), ('view1.fieldB_measure',0,0,0,0,0,0)] 
    mock_cursor_for_sample.fetchall.return_value = [("SampleA_Value", 123.45)]

    info = db_instance.get_table_info(["explore_one"])

    assert "CREATE TABLE `test_model`.`explore_one`" in info
    assert "`view1.fieldA` VARCHAR -- label: 'Field A Label'; alias: 'AliasA'; category: DIMENSION; description: 'Description for Field A'" in info
    assert "`view1.fieldB_measure` MEASURE<DOUBLE> -- label: 'Field B Measure'; category: MEASURE; description: 'Desc for Field B'" in info
    assert "view1.hidden_field" not in info 
    assert "/*\n1 example rows from Explore `test_model`.`explore_one`" in info
    assert "selected columns: `view1.fieldA`, `view1.fieldB_measure`" in info 
    assert "(`view1.fieldA`, `view1.fieldB_measure`)" in info 
    assert "('SampleA_Value', '123.45')" in info 
    db_meta_data_mock.getColumns.assert_called_with(None, "test_model", "explore_one", "%")
    expected_sample_query = "SELECT `view1.fieldA`, `view1.fieldB_measure` FROM `test_model`.`explore_one` LIMIT 1"
    
    called_with_sample_query = False
    for call_args in mock_cursor_for_sample.execute.call_args_list:
        if call_args[0][0] == expected_sample_query:
            called_with_sample_query = True; break
    assert called_with_sample_query, f"Expected sample query not found. Calls: {mock_cursor_for_sample.execute.call_args_list}"

def test_run_query(db_instance: LookerSQLDatabase, mock_jdbc_connection: MagicMock) -> None:
    """Test the run method for executing a SQL query."""
    mock_cursor = mock_jdbc_connection.cursor.return_value.__enter__.return_value
    mock_cursor.description = [('result_col',0,0,0,0,0,0)]
    mock_cursor.fetchall.return_value = [("query_result_1",)]
    sql_command: str = "SELECT `view.some_field` FROM `test_model`.`some_explore`"
    result_str = db_instance.run(sql_command)
    mock_cursor.execute.assert_called_with(sql_command) 
    assert "Columns: ['`result_col`']" in result_str
    assert "('query_result_1',)" in result_str

def test_run_query_strips_semicolon_and_markdown(db_instance: LookerSQLDatabase, mock_jdbc_connection: MagicMock) -> None:
    """Test that run method strips trailing semicolons and markdown."""
    mock_cursor = mock_jdbc_connection.cursor.return_value.__enter__.return_value
    
    sql_command_with_semicolon: str = "SELECT `view.field` FROM `model`.`explore`;;;  "
    expected_executed_command_1: str = "SELECT `view.field` FROM `model`.`explore`"
    db_instance.run(sql_command_with_semicolon)
    mock_cursor.execute.assert_called_with(expected_executed_command_1)

    sql_command_with_markdown: str = "```sql\nSELECT `view.field2` FROM `model`.`explore2`\n```"
    expected_executed_command_2: str = "SELECT `view.field2` FROM `model`.`explore2`"
    db_instance.run(sql_command_with_markdown)
    mock_cursor.execute.assert_called_with(expected_executed_command_2)

    sql_command_with_markdown_no_lang: str = "```\nSELECT `view.field3` FROM `model`.`explore3`\n```"
    expected_executed_command_3: str = "SELECT `view.field3` FROM `model`.`explore3`"
    db_instance.run(sql_command_with_markdown_no_lang)
    mock_cursor.execute.assert_called_with(expected_executed_command_3)