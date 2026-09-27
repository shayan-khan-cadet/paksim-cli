#!/usr/bin/env python3
"""
SQLite Query History - Log every query and enable search
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.path.expanduser("~/.paksim/queries.db")


class QueryDB:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_schema()
    
    def _init_schema(self):
        """Create tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                query_type TEXT NOT NULL,
                query_value TEXT NOT NULL,
                ghost_mode INTEGER DEFAULT 0,
                success INTEGER DEFAULT 0,
                result_json TEXT,
                notes TEXT
            )
        """)
        
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_value
            ON queries(query_value)
        """)
        
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_query_type
            ON queries(query_type)
        """)
        
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON queries(timestamp)
        """)
        
        conn.commit()
        conn.close()
    
    def log(self, query_type: str, query_value: str, result: Any,
            ghost_mode: bool = False, success: bool = True,
            notes: str = "") -> int:
        """Log a query result"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO queries
            (timestamp, query_type, query_value, ghost_mode, success, result_json, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            query_type,
            query_value,
            1 if ghost_mode else 0,
            1 if success else 0,
            json.dumps(result, ensure_ascii=False) if result else None,
            notes
        ))
        
        row_id = c.lastrowid
        conn.commit()
        conn.close()
        return row_id
    
    def search(self, term: str, limit: int = 50) -> List[Dict]:
        """Search queries by value (LIKE match)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("""
            SELECT id, timestamp, query_type, query_value, ghost_mode, success, notes
            FROM queries
            WHERE query_value LIKE ?
               OR result_json LIKE ?
               OR notes LIKE ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (f"%{term}%", f"%{term}%", f"%{term}%", limit))
        
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows
    
    def recent(self, limit: int = 20) -> List[Dict]:
        """Get most recent queries"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("""
            SELECT id, timestamp, query_type, query_value, ghost_mode, success, notes
            FROM queries
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows
    
    def get_result(self, query_id: int) -> Optional[Dict]:
        """Get full result for a query by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT * FROM queries WHERE id = ?", (query_id,))
        row = c.fetchone()
        conn.close()
        
        if not row:
            return None
        
        result = dict(row)
        if result.get("result_json"):
            try:
                result["result"] = json.loads(result["result_json"])
            except:
                result["result"] = None
        return result
    
    def stats(self) -> Dict:
        """Get statistics"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM queries")
        total = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM queries WHERE success = 1")
        successful = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM queries WHERE ghost_mode = 1")
        ghost = c.fetchone()[0]
        
        c.execute("SELECT query_type, COUNT(*) FROM queries GROUP BY query_type")
        by_type = dict(c.fetchall())
        
        conn.close()
        return {
            "total": total,
            "successful": successful,
            "failed": total - successful,
            "ghost_mode": ghost,
            "by_type": by_type,
        }
    
    def export_csv(self, path: str):
        """Export all queries to CSV"""
        import csv
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT id, timestamp, query_type, query_value, ghost_mode, success, notes FROM queries ORDER BY timestamp")
        rows = c.fetchall()
        conn.close()
        
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["id", "timestamp", "query_type", "query_value", "ghost_mode", "success", "notes"])
            writer.writerows(rows)
        
        return len(rows)


if __name__ == "__main__":
    import sys
    
    db = QueryDB()
    
    if len(sys.argv) < 2:
        print("Usage: python3 db_history.py [stats|recent|search <term>|export <file>]")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "stats":
        s = db.stats()
        print(json.dumps(s, indent=2))
    elif cmd == "recent":
        for row in db.recent(20):
            print(f"  [{row['id']}] {row['timestamp'][:19]} | {row['query_type']:8} | {row['query_value']}")
    elif cmd == "search" and len(sys.argv) > 2:
        results = db.search(sys.argv[2])
        print(f"Found {len(results)} results for '{sys.argv[2]}':")
        for row in results:
            print(f"  [{row['id']}] {row['timestamp'][:19]} | {row['query_type']:8} | {row['query_value']}")
    elif cmd == "export" and len(sys.argv) > 2:
        count = db.export_csv(sys.argv[2])
        print(f"✅ Exported {count} rows to {sys.argv[2]}")
    else:
        print("Unknown command")
