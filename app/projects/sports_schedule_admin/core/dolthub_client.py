import os
import requests
import logging

logger = logging.getLogger(__name__)

class DoltHubClient:
    """
    Client for interacting with DoltHub SQL API.
    """
    BASE_URL = "https://www.dolthub.com/api/v1alpha1"

    def __init__(self):
        self.api_token = os.getenv("DOLTHUB_API_TOKEN")
        self.owner = os.getenv("DOLTHUB_OWNER")
        self.repo = os.getenv("DOLTHUB_REPO")
        self.branch = os.getenv("DOLTHUB_BRANCH", "main")

        if not all([self.api_token, self.owner, self.repo]):
            logger.error("DoltHub configuration missing in environment variables.")

    def execute_sql(self, sql_query):
        """
        Execute a SQL query on DoltHub.
        """
        if not self.api_token:
            return {"error": "API token missing"}

        url = f"{self.BASE_URL}/{self.owner}/{self.repo}/{self.branch}"
        
        headers = {
            "authorization": f"{self.api_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": sql_query
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"DoltHub API error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response body: {e.response.text}")
            return {"error": str(e)}

    def batch_upsert(self, table_name, rows):
        """
        Perform a batch upsert (INSERT ... ON DUPLICATE KEY UPDATE).
        Rows is a list of dictionaries where keys are column names.
        """
        if not rows:
            return None

        columns = list(rows[0].keys())
        col_list = ", ".join([f"`{col}`" for col in columns])
        
        # Prepare values for the query
        values_placeholders = []
        for row in rows:
            row_values = []
            for col in columns:
                val = row[col]
                if val is None:
                    row_values.append("NULL")
                elif isinstance(val, str):
                    # Basic escaping for single quotes
                    escaped_val = val.replace("'", "''")
                    row_values.append(f"'{escaped_val}'")
                else:
                    row_values.append(str(val))
            values_placeholders.append(f"({', '.join(row_values)})")
        
        values_str = ", ".join(values_placeholders)
        
        # Build ON DUPLICATE KEY UPDATE clause
        # Note: primary_key should not be updated
        update_cols = [col for col in columns if col != "primary_key"]
        update_clause = ", ".join([f"`{col}` = VALUES(`{col}`)" for col in update_cols])
        
        sql = f"""
        INSERT INTO `{table_name}` ({col_list})
        VALUES {values_str}
        ON DUPLICATE KEY UPDATE {update_clause}
        """
        
        return self.execute_sql(sql)
