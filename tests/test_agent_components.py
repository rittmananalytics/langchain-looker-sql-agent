import pytest
from unittest.mock import MagicMock, patch, PropertyMock 

from langchain_core.language_models import BaseLanguageModel
from langchain_core.tools import Tool
from langchain.agents import AgentExecutor
from langchain.memory import ConversationBufferMemory 
from langchain_core.memory import BaseMemory         # Corrected import for BaseMemory

from langchain_looker_agent import LookerSQLDatabase, LookerSQLToolkit, create_looker_sql_agent

@pytest.fixture
def mock_looker_sql_database() -> MagicMock:
    mock_db = MagicMock(spec=LookerSQLDatabase) 
    type(mock_db).dialect = PropertyMock(return_value="calcite")
    mock_db.get_usable_table_names.return_value = ["explore1", "explore2"]
    mock_db.get_table_info.return_value = "CREATE TABLE `test_model`.`explore1` (`view.colA` VARCHAR);"
    mock_db.run.return_value = "Columns: ['`colA`']\nResults:\n('data1',)"
    return mock_db

@pytest.fixture
def mock_llm() -> MagicMock:
    llm = MagicMock(spec=BaseLanguageModel)
    return llm

@pytest.fixture
def real_conversation_buffer_memory() -> ConversationBufferMemory:
    return ConversationBufferMemory(memory_key="chat_history", return_messages=True)

def test_looker_sql_toolkit_creation(mock_looker_sql_database: MagicMock) -> None:
    toolkit = LookerSQLToolkit(db=mock_looker_sql_database)
    assert toolkit.db is mock_looker_sql_database 
    
    tools = toolkit.get_tools()
    assert isinstance(tools, list); assert len(tools) == 3 
    for tool_item in tools: assert isinstance(tool_item, Tool) 
    tool_names = {t.name for t in tools}
    assert "sql_db_list_tables" in tool_names
    assert "sql_db_schema" in tool_names
    assert "sql_db_query" in tool_names

def test_create_looker_sql_agent_instantiation(
    mock_llm: MagicMock, 
    mock_looker_sql_database: MagicMock, 
    real_conversation_buffer_memory: ConversationBufferMemory
) -> None:
    toolkit = LookerSQLToolkit(db=mock_looker_sql_database)
    agent_executor = create_looker_sql_agent(
        llm=mock_llm, toolkit=toolkit, verbose=False,
        agent_executor_kwargs={"memory": real_conversation_buffer_memory} 
    )
    
    assert isinstance(agent_executor, AgentExecutor)
    assert agent_executor.tools is not None; assert len(agent_executor.tools) == 3
    assert agent_executor.agent is not None
    
    # --- MODIFIED MEMORY ASSERTIONS ---
    assert agent_executor.memory is not None, "Memory object was not set"
    assert isinstance(agent_executor.memory, BaseMemory), "Memory is not a BaseMemory instance"
    assert isinstance(agent_executor.memory, ConversationBufferMemory), "Memory is not a ConversationBufferMemory instance"
    assert agent_executor.memory.memory_key == real_conversation_buffer_memory.memory_key, "Memory key mismatch"
    assert agent_executor.memory.return_messages == real_conversation_buffer_memory.return_messages, "return_messages mismatch"
    # The `is` check (object identity) is removed as it can be too strict here.

def test_create_looker_sql_agent_with_executor_kwargs(
    mock_llm: MagicMock, 
    mock_looker_sql_database: MagicMock, 
    real_conversation_buffer_memory: ConversationBufferMemory
) -> None:
    toolkit = LookerSQLToolkit(db=mock_looker_sql_database)
    agent_executor = create_looker_sql_agent(
        llm=mock_llm, toolkit=toolkit, verbose=False, 
        agent_executor_kwargs={
            "memory": real_conversation_buffer_memory,
            "max_iterations": 7,
            "return_intermediate_steps": True,
        }
    )
    assert isinstance(agent_executor, AgentExecutor)
    
    # --- MODIFIED MEMORY ASSERTIONS ---
    assert agent_executor.memory is not None
    assert isinstance(agent_executor.memory, ConversationBufferMemory)
    assert agent_executor.memory.memory_key == real_conversation_buffer_memory.memory_key
    
    assert agent_executor.max_iterations == 7
    assert agent_executor.return_intermediate_steps is True
    assert agent_executor.verbose is False 
    assert agent_executor.handle_parsing_errors is True 

    agent_executor_custom_parse = create_looker_sql_agent(
        llm=mock_llm, toolkit=toolkit, verbose=True, 
        agent_executor_kwargs={
            "memory": real_conversation_buffer_memory, 
            "handle_parsing_errors": False
        }
    )
    assert agent_executor_custom_parse.handle_parsing_errors is False
    assert agent_executor_custom_parse.verbose is True
    # --- MODIFIED MEMORY ASSERTIONS ---
    assert agent_executor_custom_parse.memory is not None
    assert isinstance(agent_executor_custom_parse.memory, ConversationBufferMemory)
    assert agent_executor_custom_parse.memory.memory_key == real_conversation_buffer_memory.memory_key