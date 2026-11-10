def intersect(a,b):
    lo=max(a[0],b[0]);hi=min(a[1],b[1]);return [lo,hi] if lo<hi else None
def subtract(window,blocked):
    result=[list(window)]
    for block in blocked:
        next_=[]
        for a,b in result:
            c,d=block
            if d<=a or c>=b:next_.append([a,b]);continue
            if a<c:next_.append([a,c])
            if d<b:next_.append([d,b])
        result=next_
    return result
def zone_overlap(a,b):return sorted(set(a)&set(b))
TOOLS={'intersect':intersect,'subtract':subtract,'zone_overlap':zone_overlap}
