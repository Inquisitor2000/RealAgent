#!/usr/bin/env python3
"""
Database Performance Metrics
============================

A helper module to measure and log SQLite database query performance.
Provides decorators and wrapper functions for timing database operations.

Usage:
    from Helper.db_metrics import timed_db_connection, log_query_time, db_metrics

Features:
    - Automatic query timing
    - Color-coded CLI output (green=fast, yellow=medium, red=slow)
    - Query statistics tracking
    - Configurable thresholds
"""

import sqlite3
import time
import functools
from datetime import datetime
from collections import defaultdict

# ANSI color codes for CLI output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    GRAY = '\033[90m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

# Performance thresholds (in milliseconds)
THRESHOLDS = {
    'fast': 50,      # < 50ms = green
    'medium': 200,   # 50-200ms = yellow
    'slow': 200      # > 200ms = red
}

# Global metrics storage
class DBMetrics:
    def __init__(self):
        self.enabled = True
        self.verbose = False  # Set to True to see every query
        self.queries = []
        self.stats = defaultdict(lambda: {'count': 0, 'total_time': 0, 'max_time': 0, 'min_time': float('inf')})
        self._current_endpoint = None
        self._endpoint_queries = []
    
    def reset(self):
        """Reset all collected metrics."""
        self.queries = []
        self.stats = defaultdict(lambda: {'count': 0, 'total_time': 0, 'max_time': 0, 'min_time': float('inf')})
        self._current_endpoint = None
        self._endpoint_queries = []
    
    def log(self, endpoint, query_type, duration_ms, query_preview=""):
        """Log a query execution."""
        if not self.enabled:
            return
        
        # Store query info
        query_info = {
            'timestamp': datetime.now(),
            'endpoint': endpoint,
            'query_type': query_type,
            'duration_ms': duration_ms,
            'query_preview': query_preview[:100] if query_preview else ""
        }
        self.queries.append(query_info)
        
        # Update stats
        self.stats[endpoint]['count'] += 1
        self.stats[endpoint]['total_time'] += duration_ms
        self.stats[endpoint]['max_time'] = max(self.stats[endpoint]['max_time'], duration_ms)
        self.stats[endpoint]['min_time'] = min(self.stats[endpoint]['min_time'], duration_ms)
        
        # Track queries for current endpoint
        if endpoint != self._current_endpoint:
            # New endpoint - print summary of previous if exists
            if self._current_endpoint and self._endpoint_queries:
                self._print_endpoint_summary()
            self._current_endpoint = endpoint
            self._endpoint_queries = []
        
        self._endpoint_queries.append(query_info)
        
        # Only print individual queries if verbose OR if slow
        if self.verbose or duration_ms >= THRESHOLDS['medium']:
            self._print_metric(endpoint, query_type, duration_ms, query_preview)
    
    def flush_endpoint(self):
        """Flush and print summary for current endpoint."""
        if self._current_endpoint and self._endpoint_queries:
            self._print_endpoint_summary()
            self._current_endpoint = None
            self._endpoint_queries = []
    
    def _print_endpoint_summary(self):
        """Print a compact summary for the current endpoint's queries."""
        if not self._endpoint_queries:
            return
        
        total_time = sum(q['duration_ms'] for q in self._endpoint_queries)
        query_count = len(self._endpoint_queries)
        
        # Count by type
        type_counts = defaultdict(int)
        for q in self._endpoint_queries:
            type_counts[q['query_type']] += 1
        
        # Determine color based on total time
        if total_time < THRESHOLDS['fast']:
            color = Colors.GREEN
            icon = "✓"
        elif total_time < THRESHOLDS['medium']:
            color = Colors.YELLOW
            icon = "●"
        else:
            color = Colors.RED
            icon = "⚠"
        
        # Format type breakdown
        type_str = " ".join([f"{t}:{c}" for t, c in sorted(type_counts.items())])
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{Colors.GRAY}[{timestamp}]{Colors.RESET} "
              f"{color}{icon}{Colors.RESET} "
              f"{Colors.CYAN}{self._current_endpoint:20}{Colors.RESET} "
              f"{color}{total_time:>8.2f}ms{Colors.RESET} "
              f"{Colors.GRAY}({query_count} queries: {type_str}){Colors.RESET}")
    
    def _print_metric(self, endpoint, query_type, duration_ms, query_preview):
        """Print colored metric to CLI (for slow queries or verbose mode)."""
        # Determine color based on duration
        if duration_ms < THRESHOLDS['fast']:
            color = Colors.GREEN
            status = "FAST"
        elif duration_ms < THRESHOLDS['medium']:
            color = Colors.YELLOW
            status = "OK"
        else:
            color = Colors.RED
            status = "SLOW"
        
        # Format the output
        timestamp = datetime.now().strftime("%H:%M:%S")
        duration_str = f"{duration_ms:.2f}ms"
        
        # Truncate query preview
        preview = query_preview[:60] + "..." if len(query_preview) > 60 else query_preview
        preview = preview.replace('\n', ' ').strip()
        
        print(f"{Colors.GRAY}[{timestamp}]{Colors.RESET} "
              f"{Colors.CYAN}DB{Colors.RESET} "
              f"{color}{Colors.BOLD}{status:4}{Colors.RESET} "
              f"{color}{duration_str:>10}{Colors.RESET} "
              f"{Colors.GRAY}│{Colors.RESET} {endpoint} "
              f"{Colors.GRAY}({query_type}){Colors.RESET} "
              f"{Colors.GRAY}{preview}{Colors.RESET}")
    
    def print_summary(self):
        """Print a summary of all collected metrics."""
        if not self.stats:
            print(f"{Colors.GRAY}No database metrics collected.{Colors.RESET}")
            return
        
        print(f"\n{Colors.BOLD}{'='*70}{Colors.RESET}")
        print(f"{Colors.BOLD}DATABASE PERFORMANCE SUMMARY{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*70}{Colors.RESET}")
        
        for endpoint, stats in sorted(self.stats.items(), key=lambda x: x[1]['total_time'], reverse=True):
            avg_time = stats['total_time'] / stats['count'] if stats['count'] > 0 else 0
            
            # Color based on average time
            if avg_time < THRESHOLDS['fast']:
                color = Colors.GREEN
            elif avg_time < THRESHOLDS['medium']:
                color = Colors.YELLOW
            else:
                color = Colors.RED
            
            print(f"{Colors.CYAN}{endpoint:30}{Colors.RESET} "
                  f"│ calls: {stats['count']:4} "
                  f"│ avg: {color}{avg_time:>8.2f}ms{Colors.RESET} "
                  f"│ max: {stats['max_time']:>8.2f}ms "
                  f"│ total: {stats['total_time']:>10.2f}ms")
        
        print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")

# Global metrics instance
db_metrics = DBMetrics()


class TimedCursor:
    """A cursor wrapper that times query execution."""
    
    def __init__(self, cursor, endpoint="unknown"):
        self._cursor = cursor
        self._endpoint = endpoint
        self._last_query = ""
    
    def execute(self, query, params=None):
        """Execute a query and log its timing."""
        self._last_query = query
        start = time.perf_counter()
        
        if params:
            result = self._cursor.execute(query, params)
        else:
            result = self._cursor.execute(query)
        
        duration_ms = (time.perf_counter() - start) * 1000
        
        # Determine query type
        query_upper = query.strip().upper()
        if query_upper.startswith('SELECT'):
            query_type = 'SELECT'
        elif query_upper.startswith('INSERT'):
            query_type = 'INSERT'
        elif query_upper.startswith('UPDATE'):
            query_type = 'UPDATE'
        elif query_upper.startswith('DELETE'):
            query_type = 'DELETE'
        else:
            query_type = 'OTHER'
        
        db_metrics.log(self._endpoint, query_type, duration_ms, query)
        return result
    
    def executemany(self, query, params_list):
        """Execute many queries and log timing."""
        self._last_query = query
        start = time.perf_counter()
        result = self._cursor.executemany(query, params_list)
        duration_ms = (time.perf_counter() - start) * 1000
        db_metrics.log(self._endpoint, 'BATCH', duration_ms, f"{query} ({len(params_list)} rows)")
        return result
    
    def fetchone(self):
        return self._cursor.fetchone()
    
    def fetchall(self):
        return self._cursor.fetchall()
    
    def fetchmany(self, size=None):
        if size:
            return self._cursor.fetchmany(size)
        return self._cursor.fetchmany()
    
    @property
    def lastrowid(self):
        return self._cursor.lastrowid
    
    @property
    def rowcount(self):
        return self._cursor.rowcount
    
    @property
    def description(self):
        return self._cursor.description
    
    def __iter__(self):
        return iter(self._cursor)


class TimedConnection:
    """A connection wrapper that provides timed cursors."""
    
    def __init__(self, connection, endpoint="unknown"):
        self._connection = connection
        self._endpoint = endpoint
    
    def cursor(self):
        return TimedCursor(self._connection.cursor(), self._endpoint)
    
    def commit(self):
        return self._connection.commit()
    
    def rollback(self):
        return self._connection.rollback()
    
    def close(self):
        db_metrics.flush_endpoint()  # Print summary before closing
        return self._connection.close()
    
    def execute(self, query, params=None):
        """Direct execute on connection."""
        cursor = TimedCursor(self._connection.cursor(), self._endpoint)
        return cursor.execute(query, params)
    
    @property
    def row_factory(self):
        return self._connection.row_factory
    
    @row_factory.setter
    def row_factory(self, value):
        self._connection.row_factory = value
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._connection.close()


def timed_db_connection(db_path, endpoint="unknown"):
    """
    Create a timed database connection.
    
    Usage:
        conn = timed_db_connection(DB_PATH, endpoint="/api/listings")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM listings")
    """
    conn = sqlite3.connect(str(db_path))
    return TimedConnection(conn, endpoint)


def with_db_metrics(endpoint_name):
    """
    Decorator to add database metrics to a function.
    
    Usage:
        @with_db_metrics("/api/listings")
        def get_listings():
            conn = get_db_connection()
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000
            
            # Log total endpoint time if it was slow
            if duration_ms > THRESHOLDS['medium']:
                print(f"{Colors.GRAY}[{datetime.now().strftime('%H:%M:%S')}]{Colors.RESET} "
                      f"{Colors.RED}⚠ TOTAL {endpoint_name}: {duration_ms:.2f}ms{Colors.RESET}")
            
            return result
        return wrapper
    return decorator


# Utility function to enable/disable metrics
def set_metrics_enabled(enabled):
    """Enable or disable metrics logging."""
    db_metrics.enabled = enabled


def set_metrics_verbose(verbose):
    """Enable or disable verbose mode (show every query)."""
    db_metrics.verbose = verbose


def get_metrics_summary():
    """Get a dictionary of current metrics."""
    return {
        'queries': db_metrics.queries[-100:],  # Last 100 queries
        'stats': dict(db_metrics.stats)
    }
