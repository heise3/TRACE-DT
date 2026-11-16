"""Capacity-coupled consensus bounds, standard-library implementation (MIT).

Exact endpoints require a closed proof gap. Interrupted branch-and-bound returns
certified outer bounds and feasible incumbents, never an unproved exact label.
"""
from collections import Counter, deque
from itertools import combinations
import math
import sys
import time


def _normalise(cells):
    if not cells:
        raise ValueError('At least one cell is required')
    if len({c.context_id for c in cells}) != 1:
        raise ValueError('Consensus cells must share a context')
    if len({c.specification_id for c in cells}) != len(cells):
        raise ValueError('Duplicate specification identifiers')
    fixed=[set(c.necessary) for c in cells]
    ties=[set(c.possible)-f for c,f in zip(cells,fixed)]
    cap=[len(c.deterministic)-len(f) for c,f in zip(cells,fixed)]
    for c,f,t,r in zip(cells,fixed,ties,cap):
        if f&t or not 0<=r<=len(t) or not (f<=set(c.deterministic)<=f|t):
            raise ValueError('Invalid cell capacity/membership')
    return fixed,ties,cap


def consensus_size(allocation,q):
    return sum(v>=q for v in Counter(u for s in allocation for u in s).values())


def validate_witness(cells, allocation, q, expected):
    fixed,ties,cap=_normalise(cells)
    if len(allocation)!=len(cells): return False
    for f,t,r,s in zip(fixed,ties,cap,allocation):
        if len(s)!=len(f)+r or not f<=set(s)<=f|t:return False
    return consensus_size(allocation,q)==expected


def _union_max(fixed,ties,cap):
    """q=1 maximum: maximum capacitated bipartite matching plus legal fills."""
    known=set().union(*fixed); universe=sorted(set().union(*ties)-known)
    M=len(ties); index={u:M+1+i for i,u in enumerate(universe)}
    sink=M+1+len(universe); graph=[[] for _ in range(sink+1)]
    def edge(a,b,c):
        graph[a].append([b,c,len(graph[b])]); graph[b].append([a,0,len(graph[a])-1])
    for m,(t,r) in enumerate(zip(ties,cap)):
        edge(0,m+1,r)
        for u in sorted(t-known):edge(m+1,index[u],1)
    for v in index.values():edge(v,sink,1)
    flow=0
    while True:
        parent={0:None};todo=deque([0])
        while todo and sink not in parent:
            u=todo.popleft()
            for k,(v,c,rev) in enumerate(graph[u]):
                if c and v not in parent:parent[v]=(u,k);todo.append(v)
        if sink not in parent:break
        v=sink
        while v:
            u,k=parent[v];e=graph[u][k];e[1]-=1;graph[v][e[2]][1]+=1;v=u
        flow+=1
    reverse={v:u for u,v in index.items()};allocation=[]
    for m,(f,t,r) in enumerate(zip(fixed,ties,cap)):
        chosen={reverse[v] for v,c,rev in graph[m+1] if v in reverse and c==0}
        chosen.update(sorted(t-chosen)[:r-len(chosen)])
        allocation.append(f|chosen)
    assert consensus_size(allocation,1)==len(known)+flow
    return len(known)+flow,allocation


def _root_problem(fixed,ties,q):
    h=Counter(u for s in fixed for u in s)
    active=set().union(*ties)
    constant=sum(v>=q for u,v in h.items() if u not in active)
    items=[]
    for u in active:
        mask=tuple(m for m,t in enumerate(ties) if u in t)
        items.append((u,h[u],mask))
    # Group equal signatures consecutively; order is outcome-independent.
    items.sort(key=lambda a:(-len(a[2]),q-a[1],a[2],a[0]))
    return items,constant


def _relax(groups, caps, q):
    """Integer vote-conservation relaxation, valid for every suffix allocation."""
    available=[0]*len(caps)
    for (h,mask),n in groups.items():
        for m in mask:available[m]+=n
    if any(r<0 or r>n for r,n in zip(caps,available)):return None
    forced=0; total=sum(caps); below_ceiling=0;minimum_votes=0;gains=[];costs=[]
    for (h,mask),n in groups.items():
        if not n:continue
        low=h+sum(caps[m]==available[m] for m in mask)
        high=h+sum(caps[m]>0 for m in mask)
        total+=n*h; minimum_votes+=n*low
        if low>=q:
            forced+=n;below_ceiling+=n*high
        else:
            below_ceiling+=n*min(high,q-1)
            if high>=q:gains.append((high-q+1,n));costs.append((q-low,n))
    excess=max(0,total-below_ceiling);lower=forced
    for gain,n in sorted(gains,reverse=True):
        if not excess:break
        k=min(n,(excess+gain-1)//gain);lower+=k;excess=max(0,excess-k*gain)
    resource=total-minimum_votes;upper=forced
    for cost,n in sorted(costs):
        k=min(n,resource//cost);upper+=k;resource-=k*cost
    return lower,upper


def _search(cells,fixed,ties,cap,q,maximise,node_limit,time_limit,seeds):
    items,constant=_root_problem(fixed,ties,q)
    groups=Counter((h,mask) for _,h,mask in items)
    root=_relax(groups,cap,q)
    outer=constant+root[int(maximise)]
    best_alloc=min(seeds,key=lambda a:(-1 if maximise else 1)*consensus_size(a,q))
    best=consensus_size(best_alloc,q)
    if best==outer:return best,outer,best_alloc,0,True
    start=time.monotonic();nodes=0;interrupted=False;memo={}
    work=[set(f) for f in fixed];caps=list(cap)
    old_limit=sys.getrecursionlimit();sys.setrecursionlimit(max(old_limit,len(items)+150))
    def visit(i,value):
        nonlocal best,best_alloc,nodes,interrupted
        if nodes>=node_limit or time.monotonic()-start>=time_limit:
            interrupted=True;return
        nodes+=1
        bound=_relax(groups,caps,q)
        if bound is None:return
        optimistic=value+bound[int(maximise)]
        if (optimistic<=best if maximise else optimistic>=best):return
        key=(i,tuple(caps));prior=memo.get(key)
        if prior is not None and (prior>=value if maximise else prior<=value):return
        memo[key]=value
        if i==len(items):
            best=value;best_alloc=[set(s) for s in work];return
        u,h,mask=items[i]
        available=[sum(n for (_,ms),n in groups.items() if m in ms) for m in mask]
        mandatory=tuple(m for m,n in zip(mask,available) if caps[m]==n)
        free=tuple(m for m,n in zip(mask,available) if 0<caps[m]<n)
        need=q-h-len(mandatory)
        # Search threshold-adjacent patterns first; correctness does not depend on order.
        ks=list(range(len(free)+1))
        ks.sort(key=lambda k: ((not (k>=need)) if maximise else (k>=need),abs(k-need)))
        sig=(h,mask);groups[sig]-=1
        try:
            for k in ks:
                for combo in combinations(free,k):
                    if interrupted:return
                    selected=mandatory+combo
                    for m in selected:caps[m]-=1;work[m].add(u)
                    visit(i+1,value+int(h+len(selected)>=q))
                    for m in selected:caps[m]+=1;work[m].remove(u)
                    if best==outer:return
        finally:groups[sig]+=1
    try:visit(0,constant)
    finally:sys.setrecursionlimit(old_limit)
    closed=(not interrupted) or best==outer
    return best,(best if closed else outer),best_alloc,nodes,closed


def consensus_bounds(cells,q,node_limit=100000,time_limit=10.0):
    if not isinstance(q,int) or isinstance(q,bool) or not 1<=q<=len(cells):
        raise ValueError('q must be an integer between 1 and M')
    if node_limit<0 or time_limit<0:raise ValueError('Negative search limit')
    fixed,ties,cap=_normalise(cells)
    universe=set().union(*(f|t for f,t in zip(fixed,ties)))
    marginal_necessary=sum(sum(u in f for f in fixed)>=q for u in universe)
    marginal_possible=sum(sum(u in f or u in t for f,t in zip(fixed,ties))>=q for u in universe)
    seeds=[[set(c.deterministic) for c in cells],
           [f|set(sorted(t,reverse=True)[:r]) for f,t,r in zip(fixed,ties,cap)]]
    # Feasible greedy seeds spread/concentrate votes, without asserting optimality.
    for concentrate in [True,False]:
        for reverse in [False,True]:
            alloc=[set(f) for f in fixed];votes=Counter(u for f in fixed for u in f)
            order=list(range(len(cells)))[::(-1 if reverse else 1)]
            for m in order:
                ranked=sorted(ties[m],key=lambda u:((-votes[u] if concentrate else votes[u]),u))
                for u in ranked[:cap[m]]:alloc[m].add(u);votes[u]+=1
            seeds.append(alloc)
    low,lower,wlo,nlo,clo=_search(cells,fixed,ties,cap,q,False,node_limit,time_limit,seeds)
    if q==1:
        high,whi=_union_max(fixed,ties,cap);upper=high;nhi=0;chi=True
    else:
        high,upper,whi,nhi,chi=_search(cells,fixed,ties,cap,q,True,node_limit,time_limit,seeds)
    assert marginal_necessary<=lower<=low<=high<=upper<=marginal_possible
    assert validate_witness(cells,wlo,q,low) and validate_witness(cells,whi,q,high)
    return dict(q=q,M=len(cells),status='EXACT' if clo and chi else 'BOUNDED_NOT_EXACT',
                marginal_lower=marginal_necessary,marginal_upper=marginal_possible,
                certified_lower=lower,minimum_feasible=low,maximum_feasible=high,certified_upper=upper,
                minimum_proven=clo,maximum_proven=chi,nodes_min=nlo,nodes_max=nhi,
                witness_min=[sorted(s) for s in wlo],witness_max=[sorted(s) for s in whi],
                specifications=[c.specification_id for c in cells])
