import json,urllib.request,sys,time
B="https://api.elections.kalshi.com/trade-api/v2"
def get(path):
    for i in range(4):
        try:
            with urllib.request.urlopen(B+path,timeout=30) as r: return json.load(r)
        except Exception as e:
            time.sleep(1+i); err=e
    return {"error":str(err)}
