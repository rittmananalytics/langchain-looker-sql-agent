!sudo apt-get update
!sudo apt-get install -y openjdk-11-jdk --no-install-recommends
!java -version # Verify installation
!export JAVA_HOME=$(java -XshowSettings:properties -version 2>&1 > /dev/null | grep 'java.home' | awk '{print $3}')
!echo $JAVA_HOME
!mkdir drivers
!cd drivers
!wget https://github.com/looker-open-source/calcite-avatica/releases/download/avatica-1.26.0-looker/avatica-1.26.0-looker.jar
!pip install langchain-looker-agent langchain-openai python-dotenv

# examples/quickstart.py
import os
import logging
from dotenv import load_dotenv

# It's good practice for examples to configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to load .env file from the project root (assuming script is run from project root or examples/)
# For a library user, they'd manage their .env in their own project.
# This makes the example self-contained if .env is at project root.
dotenv_path_project_root = os.path.join(os.path.dirname(__file__), os.pardir, '.env') # Path to .env if quickstart.py is in examples/
dotenv_path_current_dir = os.path.join(os.getcwd(), '.env') # Path to .env if script run from project root

if os.path.exists(dotenv_path_project_root):
    if load_dotenv(dotenv_path_project_root):
        logger.info(f"Loaded .env from: {dotenv_path_project_root}")
elif os.path.exists(dotenv_path_current_dir):
    if load_dotenv(dotenv_path_current_dir):
        logger.info(f"Loaded .env from: {dotenv_path_current_dir}")
else:
    logger.warning(".env file not found in expected locations. Relying on system environment variables.")


# These imports assume the package 'langchain_looker_agent' is installed
# (e.g., via `pip install -e .` from project root, or `pip install langchain-looker-agent` if published)
try:
    from langchain_looker_agent import LookerSQLDatabase, LookerSQLToolkit, create_looker_sql_agent
    from langchain_openai import ChatOpenAI # Example LLM
    from langchain.memory import ConversationBufferMemory # For conversational agent
except ImportError as e:
    logger.error(f"ImportError: {e}. Ensure 'langchain_looker_agent' is installed and prerequisites are met.")
    logger.error("If running from the repository, run 'pip install -e .' from the project root first.")
    exit(1)

def main():
    logger.info("Starting Looker Agent Quickstart Example...")

    # --- 1. Load Configuration from Environment Variables ---
    looker_instance_url = os.getenv("LOOKER_INSTANCE_URL")
    lookml_model_name = os.getenv("LOOKML_MODEL_NAME")
    looker_client_id = os.getenv("LOOKER_CLIENT_ID")
    looker_client_secret = os.getenv("LOOKER_CLIENT_SECRET")
    looker_jdbc_driver_path = os.getenv("LOOKER_JDBC_DRIVER_PATH") # Needs to be resolvable
    openai_api_key = os.getenv("OPENAI_API_KEY")

    required_vars = {
        "LOOKER_INSTANCE_URL": looker_instance_url,
        "LOOKML_MODEL_NAME": lookml_model_name,
        "LOOKER_CLIENT_ID": looker_client_id,
        "LOOKER_CLIENT_SECRET": looker_client_secret,
        "LOOKER_JDBC_DRIVER_PATH": looker_jdbc_driver_path,
        "OPENAI_API_KEY": openai_api_key
    }
    missing = [key for key, value in required_vars.items() if not value]
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}. Please set them in your .env file or environment.")
        return

    # Resolve JDBC driver path if it's relative (assuming relative to project root for this example)
    jdbc_driver_full_path = looker_jdbc_driver_path
    if not os.path.isabs(looker_jdbc_driver_path):
        # This assumes quickstart.py is in examples/, so pardir is project root
        proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        jdbc_driver_full_path = os.path.join(proj_root, looker_jdbc_driver_path) 
    
    if not os.path.exists(jdbc_driver_full_path):
        logger.error(f"JDBC Driver not found at resolved path: {jdbc_driver_full_path}")
        return

    # --- 2. Initialize LookerSQLDatabase ---
    try:
        db = LookerSQLDatabase(
            looker_instance_url=looker_instance_url,
            lookml_model_name=lookml_model_name,
            client_id=looker_client_id,
            client_secret=looker_client_secret,
            jdbc_driver_path=jdbc_driver_full_path,
            sample_rows_in_table_info=0 # Disable samples for quickstart simplicity
        )
        logger.info("LookerSQLDatabase initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize LookerSQLDatabase: {e}", exc_info=True)
        return

    # --- 3. Initialize LLM ---
    try:
        llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0) # Use a faster/cheaper model for quickstart
        logger.info(f"LLM initialized ({llm.model_name}).")
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}", exc_info=True)
        return

    # --- 4. Initialize Toolkit & Agent ---
    try:
        looker_toolkit = LookerSQLToolkit(db=db)
        
        # For a simple, non-conversational query, memory might not be strictly needed
        # or can be omitted if the agent supports it. 
        # For this quickstart, let's show it without explicit memory management in the executor.
        agent_executor = create_looker_sql_agent(
            llm=llm,
            toolkit=looker_toolkit,
            verbose=False, # Keep quickstart output clean
            top_k=5
            # Not passing agent_executor_kwargs with memory here for simplicity,
            # so it will be a stateless agent for this single query.
        )
        logger.info("Looker SQL Agent created.")
    except Exception as e:
        logger.error(f"Failed to create Looker Agent/Toolkit: {e}", exc_info=True)
        return

    # --- 5. Ask a Question ---
    question = "How many Explores are available in the current model?" 
    # A more data-oriented question (replace 'your_explore' with a real one if known):
    # question = "What is the total count from the `your_explore` Explore?"
    
    print(f"\nAsking agent: \"{question}\"")
    try:
        # For stateless invoke (no memory passed to AgentExecutor during creation)
        response = agent_executor.invoke({"input": question, "chat_history": []}) 
        answer = response.get("output", "No output received.")
        print(f"Agent's Answer: {answer}")
    except Exception as e:
        logger.error(f"Error invoking agent: {e}", exc_info=True)
        print(f"Error during query: {e}")
    finally:
        # --- 6. Close Database Connection ---
        if db:
            db.close()

if __name__ == "__main__":
    main()
