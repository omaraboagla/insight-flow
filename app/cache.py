from collections import OrderedDict
from copy import deepcopy
import hashlib,json
class ResponseCache:
    def __init__(self,capacity=128): self.values=OrderedDict(); self.capacity=capacity
    def key(self,question,schema_hash,model,**options): return hashlib.sha256(json.dumps([question,schema_hash,model,options],sort_keys=True,default=str).encode()).hexdigest()
    def get(self,key):
        if key not in self.values:return None
        self.values.move_to_end(key); return deepcopy(self.values[key])
    def set(self,key,value):
        self.values[key]=deepcopy(value); self.values.move_to_end(key)
        while len(self.values)>self.capacity:self.values.popitem(last=False)
