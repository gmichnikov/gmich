import os
import requests
import logging
import time
from urllib.parse import quote

logger = logging.getLogger(__name__)

class DoltHubClient:
    """
    Client for interacting with DoltHub SQL API (v1alpha1).
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
        Automatically detects if it's a read or write query.
        """
        if not self.api_token:
            return {"error": "API token missing"}

        # Normalize query to check for write keywords
        query_upper = sql_query.strip().upper()
        write_keywords = ["INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER"]
        is_write = any(query_upper.startswith(kw) for kw in write_keywords)

        if is_write:
            return self._execute_write_query(sql_query)
        else:
            return self._execute_read_query(sql_query)

    def _execute_read_query(self, sql_query):
        """Execute a read-only query using GET."""
        url = f"{self.BASE_URL}/{self.owner}/{self.repo}/{self.branch}"
        params = {"q": sql_query}
        headers = {"authorization": f"{self.api_token}"}

        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"DoltHub Read API error: {e}")
            return {"error": str(e)}

    def _execute_write_query(self, sql_query):
        """Execute a write query using POST to the /write endpoint with polling."""
        # Endpoint: /write/{from_branch}/{to_branch}?q={sql}
        url = f"{self.BASE_URL}/{self.owner}/{self.repo}/write/{self.branch}/{self.branch}"
        params = {"q": sql_query}
        headers = {
            "authorization": f"{self.api_token}",
            "Content-Type": "application/json"
        }

        try:
            # Step 1: Initiate the write
            logger.info(f"Initiating write query on DoltHub...")
            response = requests.post(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            operation_name = data.get("operationName")
            if not operation_name:
                return data

            # Step 2: Poll for completion
            return self._poll_operation(operation_name)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"DoltHub Write API error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response body: {e.response.text}")
            return {"error": str(e)}

    def _poll_operation(self, operation_name):
        """Poll the operation status until done."""
        url = f"{self.BASE_URL}/{self.owner}/{self.repo}/write"
        params = {"operationName": operation_name}
        headers = {"authorization": f"{self.api_token}"}
        
        max_retries = 30
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                response = requests.get(url, params=params, headers=headers, timeout=20)
                response.raise_for_status()
                data = response.json()
                
                if data.get("done"):
                    logger.info("DoltHub write operation complete.")
                    return data
                
                logger.info(f"Waiting for DoltHub write operation '{operation_name}'...")
                time.sleep(2)  # Wait 2 seconds before polling again
                retry_count += 1
                
            except requests.exceptions.RequestException as e:
                logger.error(f"DoltHub Polling error: {e}")
                return {"error": str(e)}
        
        return {"error": "Timeout waiting for DoltHub operation to complete"}

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
