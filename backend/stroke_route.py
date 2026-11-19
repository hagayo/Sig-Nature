"""Direction-aware continuous traversal of a skeletonized handwriting glyph.

Edges are visited before needless retracing; at junctions a smooth heading
wins. Where retracing is unavoidable, use the shortest graph connection,
not an entire reversed DFS subtree. No invisible pen lifts are introduced.
"""
from collections import deque
from math import hypot

Point = tuple[int, int]


def _components(graph: dict[Point, set[Point]]) -> list[list[Point]]:
    seen: set[Point] = set()
    parts = []
    for start in sorted(graph):
        if start in seen:
            continue
        seen.add(start)
        todo = [start]
        group = []
        while todo:
            point = todo.pop()
            group.append(point)
            for neighbor in graph[point]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    todo.append(neighbor)
        parts.append(group)
    return parts


def _edge(a: Point, b: Point) -> tuple[Point, Point]:
    return (a,b) if a < b else (b,a)


def route_skeleton(skeleton: set[Point], *, rtl: bool = True) -> list[Point]:
    if not skeleton:
        raise ValueError("Cannot route an empty handwriting skeleton")
    neighbors = ((1,0),(-1,0),(0,1),(0,-1),
                 (1,1),(1,-1),(-1,1),(-1,-1))
    graph = {p:set() for p in skeleton}
    for x,y in skeleton:
        for dx,dy in neighbors:
            q = (x+dx,y+dy)
            if q not in skeleton:
                continue
            # Remove diagonal shortcuts where the orthogonal skeleton already
            # describes the stroke; this also prevents tiny triangular loops.
            if dx and dy and ((x+dx,y) in skeleton or (x,y+dy) in skeleton):
                continue
            graph[(x,y)].add(q)
    groups = _components(graph)
    while len(groups)>1:
        def ends(group):
            tips = [point for point in group if len(graph[point]) <= 1]
            return tips if tips else [min(group),max(group)]
        candidates = [ends(group) for group in groups]
        _,_,_,i,j,a,b = min(
            ((a[0]-b[0])**2+(a[1]-b[1])**2,a,b,i,j,a,b)
            for i in range(len(candidates))
            for j in range(i+1,len(candidates))
            for a in candidates[i] for b in candidates[j]
        )
        graph[a].add(b)
        graph[b].add(a)
        groups[i].extend(groups[j])
        groups.pop(j)
    edges = {_edge(p,q) for p,near in graph.items() for q in near}
    if not edges:
        return [next(iter(skeleton))]
    endpoints = [p for p in graph if len(graph[p])==1]
    start = (max(endpoints or graph, key=lambda p: (p[0],-p[1]))
             if rtl else min(endpoints or graph, key=lambda p: (p[0],p[1])))
    result = [start]
    current = start
    remaining = set(edges)
    previous: Point | None = None
    while remaining:
        available = [q for q in graph[current] if _edge(current,q) in remaining]
        if available:
            def score(point):
                dx,dy = point[0]-current[0],point[1]-current[1]
                norm = hypot(dx,dy)
                horizontal = (-dx if rtl else dx)/norm
                if previous is None:
                    return (.25*horizontal,-point[1],-point[0])
                old = (current[0]-previous[0],current[1]-previous[1])
                old_norm = hypot(*old)
                straight = (old[0]*dx+old[1]*dy)/(old_norm*norm) if old_norm else 0.
                return (straight+.13*horizontal,-point[1],-point[0])
            chosen = max(available,key=score)
            remaining.discard(_edge(current,chosen))
            previous,current = current,chosen
            result.append(current)
            continue
        # Shortest available return to a junction with unvisited ink.
        queue = deque([current])
        parent = {current:None}
        target = None
        while queue:
            node = queue.popleft()
            if any(_edge(node,q) in remaining for q in graph[node]):
                target = node
                break
            for q in sorted(graph[node]):
                if q not in parent:
                    parent[q] = node
                    queue.append(q)
        if target is None:
            raise RuntimeError("Unable to reconnect a complete pen-down path")
        bridge = []
        while target != current:
            bridge.append(target)
            target = parent[target]
        for point in reversed(bridge):
            previous,current = current,point
            result.append(point)
    return result
