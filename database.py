import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime
import time

class DatabaseManager:
    def __init__(self, config_file="db_config.json"):
        """Initialize database connection"""
        self.config = self.load_config(config_file)
        self.connection = None
        self.connect()
        self.create_tables()
    
    def load_config(self, config_file):
        """Load database configuration"""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Default config
            default_config = {
                "host": "localhost",
                "database": "worker_tracking",
                "user": "postgres",
                "password": "password",
                "port": 5432
            }
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            print(f"Created default database config: {config_file}")
            return default_config
    
    def connect(self):
        """Connect to PostgreSQL database"""
        try:
            self.connection = psycopg2.connect(
                host=self.config['host'],
                database=self.config['database'],
                user=self.config['user'],
                password=self.config['password'],
                port=self.config['port']
            )
            self.connection.autocommit = True
            print("[DB] Connected to PostgreSQL database")
        except Exception as e:
            print(f"[DB] Connection error: {e}")
            raise
    
    def create_tables(self):
        """Create tables if they don't exist"""
        try:
            cursor = self.connection.cursor()
            
            # Activity logs table - untuk log real-time
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    camera INTEGER NOT NULL,
                    zone_name VARCHAR(100) NOT NULL,
                    event VARCHAR(50) NOT NULL,
                    status_change VARCHAR(50),
                    last_seen TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Summary table - untuk summary per jam
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS worker_summary (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    camera INTEGER NOT NULL,
                    zone_name VARCHAR(100) NOT NULL,
                    working_time_seconds INTEGER DEFAULT 0,
                    idle_time_seconds INTEGER DEFAULT 0,
                    away_time_seconds INTEGER DEFAULT 0,
                    working_time_formatted VARCHAR(20),
                    idle_time_formatted VARCHAR(20),
                    away_time_formatted VARCHAR(20),
                    summary_hour TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Index untuk performa
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_activity_logs_camera_zone 
                ON activity_logs(camera, zone_name, timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_summary_camera_zone_hour 
                ON worker_summary(camera, zone_name, summary_hour)
            """)
            
            cursor.close()
            print("[DB] Tables created successfully")
            
        except Exception as e:
            print(f"[DB] Error creating tables: {e}")
    
    def log_activity(self, camera, zone_name, event, status_change, last_seen_timestamp):
        """Insert activity log immediately"""
        try:
            cursor = self.connection.cursor()
            
            last_seen = datetime.fromtimestamp(last_seen_timestamp) if last_seen_timestamp else None
            
            cursor.execute("""
                INSERT INTO activity_logs (camera, zone_name, event, status_change, last_seen)
                VALUES (%s, %s, %s, %s, %s)
            """, (camera, zone_name, event, status_change, last_seen))
            
            cursor.close()
            
        except Exception as e:
            print(f"[DB] Error logging activity: {e}")
    
    def save_summary(self, camera, zone_summaries, summary_hour):
        """Save hourly summary to database"""
        try:
            cursor = self.connection.cursor()
            
            # Delete existing summary for this hour (if any)
            cursor.execute("""
                DELETE FROM worker_summary 
                WHERE camera = %s AND summary_hour = %s
            """, (camera, summary_hour))
            
            # Insert new summary data
            for zone_name, times in zone_summaries.items():
                working_seconds = int(times['working_time'])
                idle_seconds = int(times['idle_time'])
                away_seconds = int(times['away_time'])
                
                cursor.execute("""
                    INSERT INTO worker_summary (
                        camera, zone_name, working_time_seconds, idle_time_seconds, 
                        away_time_seconds, working_time_formatted, idle_time_formatted, 
                        away_time_formatted, summary_hour
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    camera, zone_name, working_seconds, idle_seconds, away_seconds,
                    times['working_time_formatted'], times['idle_time_formatted'], 
                    times['away_time_formatted'], summary_hour
                ))
            
            cursor.close()
            print(f"[DB] Summary saved for Camera {camera} at {summary_hour}")
            
        except Exception as e:
            print(f"[DB] Error saving summary: {e}")
    
    def get_recent_activities(self, limit=50):
        """Get recent activity logs"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT * FROM activity_logs 
                ORDER BY timestamp DESC 
                LIMIT %s
            """, (limit,))
            return cursor.fetchall()
        except Exception as e:
            print(f"[DB] Error fetching activities: {e}")
            return []
    
    def get_summary_by_hour(self, camera=None, date=None):
        """Get summary data by hour"""
        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            query = "SELECT * FROM worker_summary WHERE 1=1"
            params = []
            
            if camera:
                query += " AND camera = %s"
                params.append(camera)
            
            if date:
                query += " AND DATE(summary_hour) = %s"
                params.append(date)
            
            query += " ORDER BY summary_hour DESC, camera, zone_name"
            
            cursor.execute(query, params)
            return cursor.fetchall()
        except Exception as e:
            print(f"[DB] Error fetching summary: {e}")
            return []
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            print("[DB] Connection closed")