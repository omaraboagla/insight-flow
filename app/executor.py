import threading
import duckdb
from .ingest import clean_value

class Executor:
    def __init__(self,tables):
        self.connection=duckdb.connect(':memory:',config={'enable_external_access':'false','threads':'2'})
        self.lock=threading.RLock()
        for name,table in tables.items(): self.connection.register(name,table.frame)
    def execute(self,sql,timeout=10):
        with self.lock:
            timer=threading.Timer(timeout,self.connection.interrupt); timer.daemon=True; timer.start()
            try:
                cursor=self.connection.execute(sql)
                columns=[d[0] for d in cursor.description]
                raw=cursor.fetchmany(1001)
                return {'columns':columns,'rows':[[clean_value(v) for v in row] for row in raw[:1000]],'row_count':min(len(raw),1000),'capped':len(raw)>1000}
            finally: timer.cancel()
    def close(self):
        with self.lock: self.connection.close()
