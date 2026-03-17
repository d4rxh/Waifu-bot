"""
Database handler for Waifu Grabber Bot
Uses SQLite for data persistence
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional


class Database:
    def __init__(self, db_file='waifu_bot.db'):
        self.db_file = db_file
        self.init_db()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                last_daily TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # User waifus table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_waifus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                waifu_name TEXT,
                waifu_anime TEXT,
                waifu_rarity TEXT,
                waifu_image TEXT,
                claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_user_waifus_user_id 
            ON user_waifus(user_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_user_waifus_name 
            ON user_waifus(waifu_name)
        ''')
        
        conn.commit()
        conn.close()
    
    def add_user(self, user_id: int, username: str = None):
        """Add or update user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username)
            VALUES (?, ?)
        ''', (user_id, username))
        
        conn.commit()
        conn.close()
    
    def add_waifu_to_user(self, user_id: int, username: str, waifu: Dict):
        """Add a waifu to user's collection"""
        self.add_user(user_id, username)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO user_waifus (user_id, waifu_name, waifu_anime, waifu_rarity, waifu_image)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, waifu['name'], waifu['anime'], waifu['rarity'], waifu['image']))
        
        conn.commit()
        conn.close()
    
    def get_user_waifus(self, user_id: int) -> List[Dict]:
        """Get all waifus for a user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT waifu_name as name, waifu_anime as anime, 
                   waifu_rarity as rarity, waifu_image as image,
                   claimed_at
            FROM user_waifus
            WHERE user_id = ?
            ORDER BY claimed_at DESC
        ''', (user_id,))
        
        waifus = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return waifus
    
    def remove_waifu_from_user(self, user_id: int, waifu_name: str) -> bool:
        """Remove a waifu from user's collection"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if user has this waifu
        cursor.execute('''
            SELECT id FROM user_waifus
            WHERE user_id = ? AND waifu_name = ?
            LIMIT 1
        ''', (user_id, waifu_name))
        
        result = cursor.fetchone()
        
        if result:
            cursor.execute('''
                DELETE FROM user_waifus
                WHERE id = ?
            ''', (result['id'],))
            conn.commit()
            conn.close()
            return True
        
        conn.close()
        return False
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get top users by waifu count"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.user_id, u.username, COUNT(uw.id) as count
            FROM users u
            LEFT JOIN user_waifus uw ON u.user_id = uw.user_id
            GROUP BY u.user_id, u.username
            HAVING count > 0
            ORDER BY count DESC
            LIMIT ?
        ''', (limit,))
        
        leaderboard = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return leaderboard
    
    def get_last_daily(self, user_id: int) -> Optional[datetime]:
        """Get last daily claim time"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT last_daily FROM users
            WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result['last_daily']:
            return datetime.fromisoformat(result['last_daily'])
        return None
    
    def update_last_daily(self, user_id: int):
        """Update last daily claim time"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users
            SET last_daily = ?
            WHERE user_id = ?
        ''', (datetime.now().isoformat(), user_id))
        
        conn.commit()
        conn.close()
    
    def get_user_waifu_count(self, user_id: int) -> int:
        """Get count of user's waifus"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) as count
            FROM user_waifus
            WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result['count'] if result else 0
    
    def search_waifu(self, name: str) -> Optional[Dict]:
        """Search for a waifu by name"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT waifu_name as name, waifu_anime as anime,
                   waifu_rarity as rarity, waifu_image as image
            FROM user_waifus
            WHERE waifu_name LIKE ?
            LIMIT 1
        ''', (f'%{name}%',))
        
        result = cursor.fetchone()
        conn.close()
        
        return dict(result) if result else None
    
    def get_stats(self) -> Dict:
        """Get overall bot statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(DISTINCT user_id) as total_users FROM users')
        total_users = cursor.fetchone()['total_users']
        
        cursor.execute('SELECT COUNT(*) as total_waifus FROM user_waifus')
        total_waifus = cursor.fetchone()['total_waifus']
        
        cursor.execute('''
            SELECT waifu_rarity as rarity, COUNT(*) as count
            FROM user_waifus
            GROUP BY waifu_rarity
        ''')
        rarity_stats = {row['rarity']: row['count'] for row in cursor.fetchall()}
        
        conn.close()
        
        return {
            'total_users': total_users,
            'total_waifus': total_waifus,
            'rarity_stats': rarity_stats
        }
        