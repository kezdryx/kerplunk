from __future__ import annotations
import sys
import time
import random
import math
import os

LANE_COUNT = 5
CAR_CHARS = ["<#>", "[=]", "<o>"]
PLAYER_CHAR = "<P>"
FPS = 18.0
SPAWN_INTERVAL = 0.8  # seconds (base)
INITIAL_DISTANCE_MAX = 8  # how far 'away' a car can start (negative y)

# Base lane speeds in rows/sec (how many terminal rows a car moves per second)
BASE_LANE_SPEEDS = [0.9, 1.2, 1.6, 1.0, 1.4]

# Minimum terminal size required (width in characters)
MIN_WIDTH = 40
MIN_HEIGHT = 12


def clamp(v, a, b):
    return max(a, min(b, v))


class Car:
    def __init__(self, lane: int, y: float, art: str):
        self.lane = lane
        self.y = y
        self.art = art


class Game:
    def __init__(self, screen, use_curses: bool = True):
        self.screen = screen
        self.use_curses = use_curses
        # store curses module when available so handlers can reference KEY_LEFT/KEY_RIGHT
        self.curses = None
        if self.use_curses:
            try:
                import curses as _curses
                self.curses = _curses
            except Exception:
                self.curses = None
        self.height = 24
        self.width = 80
        self.last_time = time.time()
        self.spawn_timer = 0.0
        self.cars: list[Car] = []
        self.passed = 0
        self.global_speed = 1.0
        self.player_lane = LANE_COUNT // 2
        self.running = True
        self.score = 0

    def setup_dimensions(self):
        if self.use_curses:
            try:
                self.height, self.width = self.screen.getmaxyx()
            except Exception:
                # curses may raise if screeen is odd - fallback
                self.height, self.width = 24, 80
        else:
            # Try terminal size via env
            try:
                import shutil
                s = shutil.get_terminal_size()
                self.width, self.height = s.columns, s.lines
            except Exception:
                self.width, self.height = 80, 24

        self.height = int(self.height)
        self.width = int(self.width)

    def lane_x_positions(self) -> list[int]:
        # Divide width into lanes and return x centers for each lane.
        # Use a smaller fixed minimum gap so narrow lanes fit small car art.
        usable = max(self.width - 10, 20)
        gap = max(6, usable // (LANE_COUNT * 2))
        # total span between first and last lane
        total_span = gap * (LANE_COUNT - 1)
        start = (self.width - total_span) // 2
        xs = [start + gap * i for i in range(LANE_COUNT)]
        return xs

    def spawn_car(self):
        lane = random.randrange(0, LANE_COUNT)
        art = random.choice(CAR_CHARS)
        # start y negative so it appears after some time (various distances away)
        y = -random.uniform(0.0, INITIAL_DISTANCE_MAX)
        self.cars.append(Car(lane, y, art))

    def update(self, dt: float):
        # spawn logic
        self.spawn_timer -= dt
        spawn_interval = max(0.15, SPAWN_INTERVAL / (self.global_speed * 0.9))
        if self.spawn_timer <= 0.0:
            self.spawn_timer = random.uniform(spawn_interval * 0.6, spawn_interval * 1.4)
            self.spawn_car()

        # Move cars
        lane_speeds = [s * self.global_speed for s in BASE_LANE_SPEEDS]
        to_remove: list[Car] = []
        for car in self.cars:
            speed = lane_speeds[car.lane]
            car.y += speed * dt
            if int(car.y) >= self.player_row() + 1:
                # car passed the player
                to_remove.append(car)
                self.passed += 1
                self.score += 1
                if self.passed % 10 == 0:
                    # speed up every 10 cars passed
                    self.global_speed *= 1.22

        for c in to_remove:
            if c in self.cars:
                self.cars.remove(c)

        # Collision check
        for car in self.cars:
            if int(round(car.y)) == self.player_row() and car.lane == self.player_lane:
                # collision!
                self.running = False

    def player_row(self) -> int:
        return self.height - 3

    def handle_input(self):
        if self.use_curses and self.curses is not None:
            try:
                ch = self.screen.getch()
                if ch != -1:
                    # support q, arrow keys and a/d
                    if ch in (ord('q'), ord('Q')):
                        self.running = False
                    elif ch in (self.curses.KEY_LEFT, ord('a'), ord('A')):
                        self.player_lane = clamp(self.player_lane - 1, 0, LANE_COUNT - 1)
                    elif ch in (self.curses.KEY_RIGHT, ord('d'), ord('D')):
                        self.player_lane = clamp(self.player_lane + 1, 0, LANE_COUNT - 1)
            except Exception:
                pass
        else:
            # Windows fallback uses msvcrt
            try:
                import msvcrt
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ('q', 'Q'):
                        self.running = False
                    elif ch in ('a', 'A', '\x1b[D'):
                        self.player_lane = clamp(self.player_lane - 1, 0, LANE_COUNT - 1)
                    elif ch in ('d', 'D', '\x1b[C'):
                        self.player_lane = clamp(self.player_lane + 1, 0, LANE_COUNT - 1)
            except Exception:
                # no input available
                pass

    def draw(self):
        if self.width < MIN_WIDTH or self.height < MIN_HEIGHT:
            msg = f"Terminal too small: need {MIN_WIDTH}x{MIN_HEIGHT}, got {self.width}x{self.height}"
            if self.use_curses:
                try:
                    self.screen.clear()
                    self.screen.addstr(0, 0, msg)
                    self.screen.refresh()
                except Exception:
                    pass
            else:
                print(msg)
            return

        xs = self.lane_x_positions()

        if self.use_curses:
            try:
                self.screen.clear()
                # draw lane separators between lanes (closer spacing for small cars)
                for i in range(LANE_COUNT - 1):
                    sep_x = (xs[i] + xs[i + 1]) // 2
                    for y in range(0, self.height - 1):
                        if 0 <= sep_x < self.width:
                            try:
                                self.screen.addch(y, sep_x, '|')
                            except Exception:
                                pass

                # draw cars
                for car in self.cars:
                    y = int(round(car.y))
                    if 0 <= y < self.height - 1:
                        x = xs[car.lane]
                        s = car.art
                        # center art
                        startx = x - len(s) // 2
                        try:
                            self.screen.addstr(y, startx, s)
                        except Exception:
                            pass

                # draw player
                py = self.player_row()
                px = xs[self.player_lane]
                startx = px - len(PLAYER_CHAR) // 2
                try:
                    self.screen.addstr(py, startx, PLAYER_CHAR)
                except Exception:
                    pass

                # HUD
                hud = f" Passed: {self.passed}  Speed: {self.global_speed:.2f}  (q to quit)"
                try:
                    self.screen.addstr(self.height - 1, 0, hud[: self.width - 1])
                except Exception:
                    pass

                self.screen.refresh()
            except Exception:
                pass
        else:
            # simple print fallback
            os.system('cls' if os.name == 'nt' else 'clear')
            buffer = [" " * self.width for _ in range(self.height)]
            # draw cars
            for car in self.cars:
                y = int(round(car.y))
                if 0 <= y < self.height - 1:
                    x = xs[car.lane]
                    s = car.art
                    startx = clamp(x - len(s) // 2, 0, self.width - len(s))
                    row = buffer[y]
                    buffer[y] = row[:startx] + s + row[startx + len(s):]

            # player
            py = self.player_row()
            px = xs[self.player_lane]
            startx = clamp(px - len(PLAYER_CHAR) // 2, 0, self.width - len(PLAYER_CHAR))
            row = buffer[py]
            buffer[py] = row[:startx] + PLAYER_CHAR + row[startx + len(PLAYER_CHAR):]

            # HUD
            hud = f" Passed: {self.passed}  Speed: {self.global_speed:.2f}  (q to quit)"
            buffer[self.height - 1] = hud[: self.width - 1].ljust(self.width - 1)

            print("\n".join(buffer))

    def loop(self):
        self.setup_dimensions()
        # seed some starting cars so player sees traffic immediately
        for _ in range(6):
            self.spawn_car()

        target_frame_time = 1.0 / FPS
        while self.running:
            now = time.time()
            dt = now - self.last_time
            self.last_time = now
            # clamp dt to avoid huge jumps
            dt = min(dt, 0.2)

            self.handle_input()
            self.update(dt)
            self.draw()

            # sleep to maintain FPS, but respect game speed by lowering sleep when fast
            time_spent = time.time() - now
            to_sleep = target_frame_time - time_spent
            if to_sleep > 0:
                time.sleep(to_sleep)

        # exit message
        if self.use_curses:
            try:
                self.screen.nodelay(False)
                self.screen.clear()
                msg = f"Game over! Plunks passed: {self.passed}. Press any key to exit."
                self.screen.addstr(0, 0, msg[: self.width - 1])
                self.screen.refresh()
                self.screen.getch()
            except Exception:
                pass
        else:
            print(f"Game over! Plunks passed: {self.passed}.")


def run_curses():
    import curses

    def _wrapped(scr):
        # configure
        scr.nodelay(True)
        scr.keypad(True)
        g = Game(scr, use_curses=True)
        g.loop()

    try:
        import curses
        curses.wrapper(_wrapped)
    except Exception:
        print("Curses mode failed, falling back to simple console mode.")
        run_nocurses()


def run_nocurses():
    # Windows-friendly fallback
    g = Game(None, use_curses=False)
    # try to put terminal into a sane mode: not necessary for simple fallback
    try:
        g.loop()
    except KeyboardInterrupt:
        print('\nQuit')


def main():
    # pick curses mode if available and not on windows without curses
    use_curses = False
    if os.name != 'nt':
        try:
            import curses
            use_curses = True
        except Exception:
            use_curses = False

    if use_curses:
        run_curses()
    else:
        run_nocurses()


if __name__ == '__main__':
    main()
