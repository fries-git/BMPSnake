# AI generated proof of concept, then modified by me. All time generated from this was real (~15 minutes) as it was time spent by me, tweaking by hand.

from PIL import Image
from flask import Flask, Response
from threading import Thread, Lock
from collections import deque
from io import BytesIO
import os
import time
import random

size = 100
TICK = float(os.environ.get("SNAKE_TICK", "0.1"))
PORT = 5613

DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]  # right, left, down, up

app = Flask(__name__)
frame_lock = Lock()
published_frame = Image.new("RGB", (size, size), (0, 0, 0))
stats = {"length": 3, "best": 3, "games": 0}


# ---------------------------------------------------------------- web server
@app.route("/")
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Live Snake</title>
        <style>
            body { background: #111; color: white; font-family: monospace; text-align: center; }
            img { width: min(90vw, 600px); image-rendering: pixelated; image-rendering: crisp-edges; }
        </style>
    </head>
    <body>
        <h1>Live Snake</h1>
        <img src="/stream">
        <p id="s"></p>
        <script>
            async function poll() {
                try {
                    const r = await (await fetch('/stats')).json();
                    document.getElementById('s').textContent =
                        'length ' + r.length + '  |  best ' + r.best + '  |  games ' + r.games;
                } catch (e) {}
                setTimeout(poll, 1000);
            }
            poll();
        </script>
    </body>
    </html>
    """


@app.route("/stats")
def stats_route():
    return stats


@app.route("/stream")
def stream():
    def generate():
        while True:
            with frame_lock:
                current_frame = published_frame
            output = BytesIO()
            current_frame.save(output, format="JPEG", quality=95)
            frame = output.getvalue()
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(frame)).encode() +
                b"\r\n\r\n" + frame + b"\r\n"
            )
            time.sleep(0.05)

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


def run_server():
    app.run(host="0.0.0.0", port=PORT, threaded=True, use_reloader=False)


# ---------------------------------------------------------------------- AI
def neighbors(x, y):
    for dx, dy in DIRS:
        nx, ny = x + dx, y + dy
        if 0 <= nx < size and 0 <= ny < size:
            yield nx, ny


def bfs_path(start, goal, free_time):
    """Shortest path from start to goal that respects when body cells vacate.

    free_time[cell] = number of moves until that body cell is empty.
    Returns list of cells (excluding start, including goal) or None.
    """
    if start == goal:
        return []
    prev = {start: None}
    q = deque([(start, 0)])
    while q:
        cur, d = q.popleft()
        for nb in neighbors(*cur):
            if nb in prev:
                continue
            # we arrive at nb after d+1 moves; it must be empty by then
            if free_time.get(nb, 0) > d + 1:
                continue
            prev[nb] = cur
            if nb == goal:
                path = [nb]
                while prev[path[-1]] is not start:
                    path.append(prev[path[-1]])
                path.reverse()
                return path
            q.append((nb, d + 1))
    return None


def reachable_area(start, blocked, limit=None):
    seen = {start}
    q = deque([start])
    while q:
        cur = q.popleft()
        for nb in neighbors(*cur):
            if nb not in seen and nb not in blocked:
                seen.add(nb)
                if limit and len(seen) >= limit:
                    return len(seen)
                q.append(nb)
    return len(seen)


def make_free_time(body, pending):
    # body[0] is the tail; it vacates after 1 move (plus any pending growth)
    return {cell: i + 1 + pending for i, cell in enumerate(body)}


def can_reach_tail_after(body, path, pending):
    """Simulate following `path` (eating the apple at its end) and check the
    snake can still reach its own tail afterwards, i.e. it is not trapped."""
    # Snake length after path: current + growth consumed on the way + apple
    length_after = len(body) + min(pending, len(path)) + 1
    sim = (list(body) + list(path))[-length_after:]
    head, tail = sim[-1], sim[0]
    blocked = set(sim[1:])  # tail cell will move away, so it's a valid target
    # head must be able to reach a cell adjacent to the tail (or the tail itself)
    if head == tail:
        return True
    seen = {head}
    q = deque([head])
    while q:
        cur = q.popleft()
        for nb in neighbors(*cur):
            if nb == tail:
                return True
            if nb not in seen and nb not in blocked:
                seen.add(nb)
                q.append(nb)
    return False


def choose_direction(body, pending, apple):
    head = body[-1]
    free_time = make_free_time(body, pending)

    # 1) Shortest path to apple, only if it leaves an escape route.
    path = bfs_path(head, apple, free_time)
    if path and can_reach_tail_after(body, path, pending):
        return path[0]

    # 2) Otherwise chase the tail (always safe while the tail keeps moving).
    tail = body[0]
    if len(body) > 1:
        tpath = bfs_path(head, tail, free_time)
        if tpath:
            # Prefer the *longest* safe-looking route by picking the
            # neighbor that is farthest from the tail when possible.
            best = None
            best_score = -1
            for nb in neighbors(*head):
                if free_time.get(nb, 0) > 1:
                    continue
                p = bfs_path(nb, tail, {c: t - 1 for c, t in free_time.items() if t - 1 > 0})
                if p is not None and len(p) + 1 > best_score:
                    best_score = len(p) + 1
                    best = nb
            if best:
                return best
            return tpath[0]

    # 3) Fallback: move to whichever free neighbour has the most room.
    best, best_area = None, -1
    blocked = set(body[1:])
    for nb in neighbors(*head):
        if nb in blocked:
            continue
        area = reachable_area(nb, blocked | {head}, limit=size * size)
        if area > best_area:
            best_area, best = area, nb
    return best


# ---------------------------------------------------------------- rendering
def render(body, apple, dead=False):
    img = Image.new("RGB", (size, size), (200, 0, 0) if dead else (0, 0, 0))
    px = img.load()
    n = len(body)
    for i, (x, y) in enumerate(body):
        # tail dim -> head bright
        b = 105 + int(140 * (i / max(1, n - 1)))
        px[x, y] = (0, b, 0)
    hx, hy = body[-1]
    px[hx, hy] = (150, 255, 150)
    if apple:
        px[apple[0], apple[1]] = (200, 0, 0) if not dead else (255, 255, 255)
    return img


def publish(img):
    global published_frame
    with frame_lock:
        published_frame = img


def spawn_apple(body_set):
    free = [(x, y) for x in range(size) for y in range(size) if (x, y) not in body_set]
    return random.choice(free) if free else None


# ---------------------------------------------------------------- game loop
def play():
    body = deque([(0, size // 2)])
    pending = 2  # start with length 3
    body_set = set(body)
    apple = spawn_apple(body_set)
    result = "playing"

    while True:
        publish(render(body, apple))
        time.sleep(TICK)

        move = choose_direction(list(body), pending, apple)
        if move is None:
            result = "trapped"
            break

        # move the tail first (if not growing) so stepping onto it is legal
        if pending > 0:
            pending -= 1
        else:
            body_set.discard(body.popleft())

        if move in body_set:
            result = "selfhit"
            body.append(move)
            break

        body.append(move)
        body_set.add(move)

        if move == apple:
            pending += 1
            apple = spawn_apple(body_set)
            if apple is None:
                result = "won"
                break

        stats["length"] = len(body) + pending
        stats["best"] = max(stats["best"], stats["length"])

    stats["games"] += 1
    print(f"game over: {result}, length {len(body)}", flush=True)
    publish(render(body, apple, dead=True))
    time.sleep(2 if result != "won" else 5)


if __name__ == "__main__":
    Thread(target=run_server, daemon=True).start()
    while True:
        play()