import pandas as pd
from sqlalchemy import create_engine, text
from langchain_community.utilities.sql_database import SQLDatabase

class DatabaseService:
    def __init__(self, db_uri):
        """
        Initializes the DatabaseService with a generic SQLAlchemy URI.
        For local sqlite files, db_uri should be like 'sqlite:///path/to/db.sqlite'
        """
        self.db_uri = db_uri
        self.engine = create_engine(self.db_uri)
        
        # We wrap it in LangChain's SQLDatabase to easily extract the schema
        self.db = SQLDatabase(self.engine)

    def get_schema(self) -> str:
        """
        Returns a string representation of the database schema, including table names,
        columns, and a few sample rows for the LLM to understand the structure.
        """
        try:
            return self.db.get_table_info()
        except Exception as e:
            return f"Error retrieving schema: {str(e)}"

    def get_dialect(self) -> str:
        """
        Returns the SQLAlchemy dialect name (e.g., 'sqlite', 'postgresql').
        """
        return self.engine.dialect.name

    def execute(self, query: str) -> str:
        """
        Executes a raw SQL query and returns the results formatted as a string table using Pandas.
        """
        try:
            with self.engine.connect() as conn:
                df = pd.read_sql_query(text(query), conn)
                return df.to_string()
        except Exception as e:
            return f"Query Execution Error: {str(e)}"
