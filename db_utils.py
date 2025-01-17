import sqlite3
import time
from functools import wraps
from contextlib import contextmanager

def execute_with_retry(cursor, query, params=None, max_retries=3):
    """
    데이터베이스 쿼리 실행을 재시도하는 함수
    """
    for attempt in range(max_retries):
        try:
            if params is None:
                return cursor.execute(query)
            return cursor.execute(query, params)
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                time.sleep(0.1 * (attempt + 1))
                continue
            raise

def executemany_with_retry(cursor, query, params_list, max_retries=3):
    """
    여러 개의 데이터를 한 번에 실행하는 함수
    """
    for attempt in range(max_retries):
        try:
            return cursor.executemany(query, params_list)
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                time.sleep(0.1 * (attempt + 1))
                continue
            raise

@contextmanager
def get_db_connection():
    """
    데이터베이스 연결을 관리하는 컨텍스트 매니저
    """
    conn = sqlite3.connect('sql_challenge.db', timeout=20)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()