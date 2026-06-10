import pygame
import pygame_gui
import random
import sys
from collections import deque

from pygame_gui.elements import UIButton, UILabel

from configs.colors import *
from config_screen import run_config_screen

def default_genes(kind, cfg):
    if kind == "prey":
        return {
            "eat_energy": cfg["prey_eat_grass_energy"],
            "move_cost": cfg["prey_move_cost"],
            "max_energy": cfg["prey_max_energy"],
            "reproduce_energy": cfg["prey_reproduce_energy"],
            "reproduce_chance": cfg["prey_reproduce_chance"],
            "escape_chance": cfg["prey_escape_chance"],
            "move_distance": cfg["prey_move_distance"],
            "max_age": cfg["prey_max_age"],
            "metabolism": cfg["prey_metabolism"],
            "offspring_investment": cfg["prey_offspring_investment"],
        }
    return {
        "eat_energy": cfg["predator_eat_prey_energy"],
        "move_cost": cfg["predator_move_cost"],
        "max_energy": cfg["predator_max_energy"],
        "reproduce_energy": cfg["predator_reproduce_energy"],
        "reproduce_chance": cfg["predator_reproduce_chance"],
        "hunt_success": cfg["predator_hunt_success"],
        "move_distance": cfg["predator_move_distance"],
        "max_age": cfg["predator_max_age"],
        "metabolism": cfg["predator_metabolism"],
        "offspring_investment": cfg["predator_offspring_investment"],
    }


def mutate_genes(parent_genes, cfg):
    child = dict(parent_genes)
    n_min = int(cfg["mutation_min"])
    n_max = int(cfg["mutation_max"])
    strength = cfg["mutation_strength"]
    n = random.randint(min(n_min, n_max), max(n_min, n_max))
    if n > 0:
        keys = random.sample(list(child.keys()), min(n, len(child)))
        for k in keys:
            child[k] = max(0.0, child[k] * (1 + random.gauss(0, strength)))
    for k in ("reproduce_chance", "escape_chance", "hunt_success", "offspring_investment"):
        if k in child:
            child[k] = min(1.0, child[k])
    return child


class GrassCell:
    def __init__(self, amount=0.0):
        self.amount = float(amount)

    def grow(self, rate):
        self.amount = min(1.0, self.amount + rate)

    def eat(self, threshold, amount):
        if self.amount > threshold:
            self.amount = max(0.0, self.amount - amount)
            return True
        return False

    @property
    def color(self):
        if self.amount < 0.1: return C_GRASS_EMPTY
        elif self.amount < 0.4: return C_GRASS_LOW
        elif self.amount < 0.7: return C_GRASS_MID
        return C_GRASS_HIGH


class Animal:
    _id_counter = 0

    def __init__(self, x, y, kind, energy, cfg, genes=None):
        Animal._id_counter += 1
        self.id = Animal._id_counter
        self.x = x
        self.y = y
        self.kind = kind
        self.energy = energy
        self.cfg = cfg
        self.genes = genes if genes is not None else default_genes(kind, cfg)
        self.age = 0
        self.alive = True

    def move(self, gw, gh):
        dx, dy = random.choice([(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)])
        md = self.genes["move_distance"]
        n_full = int(md)
        n = max(1, n_full + (1 if random.random() < (md - n_full) else 0))
        for _ in range(n):
            self.x = (self.x + dx) % gw
            self.y = (self.y + dy) % gh
        self.energy -= self.genes["move_cost"] * n

    def is_alive(self):
        return self.alive and self.energy > 0


class Simulation:
    def __init__(self, cfg):
        Animal._id_counter = 0
        self.cfg = cfg
        self.gw = cfg["grid_width"]
        self.gh = cfg["grid_height"]
        self.grass = [[GrassCell(random.uniform(0.3, 1.0))
                       for _ in range(self.gw)] for _ in range(self.gh)]
        self.animals = []
        for _ in range(cfg["initial_prey"]):
            self.animals.append(Animal(
                random.randrange(self.gw), random.randrange(self.gh),
                'prey', cfg["prey_max_energy"] // 2, cfg))
        for _ in range(cfg["initial_predators"]):
            self.animals.append(Animal(
                random.randrange(self.gw), random.randrange(self.gh),
                'predator', cfg["predator_max_energy"] // 2, cfg))
        self.step_count = 0
        hl = cfg["history_length"]
        self.hist_prey = deque(maxlen=hl)
        self.hist_pred = deque(maxlen=hl)
        self.hist_grass = deque(maxlen=hl)
        self.hist_steps = deque(maxlen=hl)
        self.deaths = {
            "prey": {"starvation": 0, "predation": 0, "senescence": 0},
            "predator": {"starvation": 0, "predation": 0, "senescence": 0},
        }

    def step(self):
        self.step_count += 1
        cfg = self.cfg
        for row in self.grass:
            for cell in row:
                cell.grow(cfg["grass_regrowth_rate"])

        grid_prey, grid_pred = {}, {}
        for a in self.animals:
            if not a.is_alive(): continue
            key = (a.x, a.y)
            (grid_prey if a.kind == 'prey' else grid_pred).setdefault(key, []).append(a)

        new_animals, dead_set = [], set()

        for a in self.animals:
            if not a.is_alive() or a.id in dead_set:
                continue
            a.move(self.gw, self.gh)
            a.age += 1
            max_age = a.genes["max_age"]
            if a.age > max_age:
                p_senescence = min(1.0, 0.05 * (a.age / max_age - 1)) if max_age > 0 else 1.0
                if random.random() < p_senescence:
                    a.alive = False
                    dead_set.add(a.id)
                    self.deaths[a.kind]["senescence"] += 1
                    continue
            key = (a.x, a.y)

            if a.kind == 'prey':
                if self.grass[a.y][a.x].eat(cfg["grass_eat_threshold"], cfg["grass_eat_amount"]):
                    a.energy = min(a.genes["max_energy"],
                                   a.energy + a.genes["eat_energy"])
                a.energy -= a.genes["metabolism"]
                if key in grid_pred:
                    pred = next((p for p in grid_pred[key] if p.id not in dead_set), None)
                    if pred:
                        p_catch = pred.genes["hunt_success"] * (1 - a.genes["escape_chance"])
                        if random.random() < p_catch:
                            pred.energy = min(pred.genes["max_energy"],
                                              pred.energy + pred.genes["eat_energy"])
                            a.alive = False
                            dead_set.add(a.id)
                            self.deaths["prey"]["predation"] += 1
                            continue
                if (a.energy >= a.genes["reproduce_energy"] and
                        random.random() < a.genes["reproduce_chance"]):
                    transferred = int(a.energy * a.genes["offspring_investment"])
                    a.energy -= transferred
                    child_genes = mutate_genes(a.genes, cfg)
                    new_animals.append(Animal(
                        (a.x + random.randint(-1,1)) % self.gw,
                        (a.y + random.randint(-1,1)) % self.gh,
                        'prey', transferred, cfg, genes=child_genes))
            else:
                a.energy -= a.genes["metabolism"]
                if key in grid_prey:
                    prey = next((p for p in grid_prey[key] if p.id not in dead_set), None)
                    if prey:
                        p_catch = a.genes["hunt_success"] * (1 - prey.genes["escape_chance"])
                        if random.random() < p_catch:
                            a.energy = min(a.genes["max_energy"],
                                           a.energy + a.genes["eat_energy"])
                            prey.alive = False
                            dead_set.add(prey.id)
                            self.deaths["prey"]["predation"] += 1
                            grid_prey[key] = [p for p in grid_prey[key] if p.id != prey.id]
                if (a.energy >= a.genes["reproduce_energy"] and
                        random.random() < a.genes["reproduce_chance"]):
                    transferred = int(a.energy * a.genes["offspring_investment"])
                    a.energy -= transferred
                    child_genes = mutate_genes(a.genes, cfg)
                    new_animals.append(Animal(
                        (a.x + random.randint(-1,1)) % self.gw,
                        (a.y + random.randint(-1,1)) % self.gh,
                        'predator', transferred, cfg, genes=child_genes))

        for a in self.animals:
            if a.alive and a.energy <= 0 and a.id not in dead_set:
                self.deaths[a.kind]["starvation"] += 1
        self.animals = [a for a in self.animals if a.is_alive() and a.id not in dead_set]
        self.animals.extend(new_animals)

        pc = sum(1 for a in self.animals if a.kind == 'prey')
        dc = sum(1 for a in self.animals if a.kind == 'predator')
        gt = sum(c.amount for row in self.grass for c in row) / (self.gw * self.gh) * 100
        self.hist_prey.append(pc)
        self.hist_pred.append(dc)
        self.hist_grass.append(gt)
        self.hist_steps.append(self.step_count)

    def counts(self):
        return (sum(1 for a in self.animals if a.kind == 'prey'),
                sum(1 for a in self.animals if a.kind == 'predator'))

    def avg_energy(self):
        preys = [a.energy for a in self.animals if a.kind == 'prey']
        preds = [a.energy for a in self.animals if a.kind == 'predator']
        return (sum(preys)/len(preys) if preys else 0,
                sum(preds)/len(preds) if preds else 0)


class SimRenderer:
    PANEL = 290
    DISPLAY_MARGIN = 120

    def __init__(self, cfg):
        self.cfg = cfg
        self.gw = cfg["grid_width"]
        self.gh = cfg["grid_height"]
        pygame.init()
        initial_size = self._initial_window_size()
        self._update_layout(*initial_size)
        self.screen = pygame.display.set_mode((self.sw, self.sh), pygame.RESIZABLE)
        pygame.display.set_caption("Coevolution Simulator")
        self.clock = pygame.time.Clock()
        self.manager = None
        self.ui = {}
        self.action_buttons = {}
        self.selected_id = None
        self.scroll_offset = 0
        self.panel_content_height = 0
        self._build_ui()

    def _initial_window_size(self):
        info = pygame.display.Info()
        max_w = max(self.gw + self.PANEL, info.current_w - self.DISPLAY_MARGIN)
        max_h = max(self.gh, info.current_h - self.DISPLAY_MARGIN)
        cell = max(1, min((max_w - self.PANEL) // self.gw, max_h // self.gh))
        return (self.gw * cell + self.PANEL, self.gh * cell)

    def _update_layout(self, width, height):
        map_w_avail = max(self.gw, width - self.PANEL)
        height = max(self.gh, height)
        self.cell = max(1, min(map_w_avail // self.gw, height // self.gh))
        self.map_w = self.gw * self.cell
        self.map_h = self.gh * self.cell
        self.panel_x = self.map_w
        self.sw = self.map_w + self.PANEL
        self.sh = self.map_h

    def handle_resize(self, size):
        self._update_layout(*size)
        self.screen = pygame.display.set_mode((self.sw, self.sh), pygame.RESIZABLE)
        self._build_ui()

    def _build_ui(self):
        px, pw, ph = self.panel_x, self.PANEL, self.sh
        self.manager = pygame_gui.UIManager((self.sw, self.sh))
        self.ui = {}
        self.action_buttons = {}

        y = 10
        self.ui["title_state"] = UILabel(
            relative_rect=pygame.Rect(px + 10, y, pw - 20, 20),
            text="SIMULATION STATE",
            manager=self.manager,
        )
        y += 24
        stat_pairs = [
            ("step", "status"),
            ("prey", "pred"),
            ("ratio", None),
            ("prey_energy", "pred_energy"),
            ("prey_rep", "pred_rep"),
            ("grid", "grass"),
        ]
        half_w = (pw - 30) // 2
        for left_key, right_key in stat_pairs:
            self.ui[left_key] = UILabel(
                relative_rect=pygame.Rect(px + 10, y, half_w, 20),
                text="",
                manager=self.manager,
            )
            if right_key is not None:
                self.ui[right_key] = UILabel(
                    relative_rect=pygame.Rect(px + 10 + half_w + 10, y, half_w, 20),
                    text="",
                    manager=self.manager,
                )
            y += 20

        y += 8
        self.ui["title_chart"] = UILabel(
            relative_rect=pygame.Rect(px + 10, y, pw - 20, 20),
            text="CHART",
            manager=self.manager,
        )
        y += 24
        self.chart_rect = pygame.Rect(px + 6, y, pw - 12, 128)
        y += 136

        chart_labels = [
            ("chart_prey", "Prey"),
            ("chart_pred", "Predators"),
            ("chart_grass", "Grass %"),
        ]
        legend_w = (pw - 20) // 3
        for i, (key, text) in enumerate(chart_labels):
            self.ui[key] = UILabel(
                relative_rect=pygame.Rect(px + 10 + i * legend_w, y, legend_w, 20),
                text=text,
                manager=self.manager,
            )
        y += 20

        y += 8
        self.action_buttons["pause"] = UIButton(
            relative_rect=pygame.Rect(px + 10, y, pw - 20, 28),
            text="SPACE  Pause / Resume",
            manager=self.manager,
        )
        y += 32
        half_w = (pw - 30) // 2
        self.action_buttons["faster"] = UIButton(
            relative_rect=pygame.Rect(px + 10, y, half_w, 28),
            text="+  Faster",
            manager=self.manager,
        )
        self.action_buttons["slower"] = UIButton(
            relative_rect=pygame.Rect(px + 10 + half_w + 10, y, half_w, 28),
            text="-  Slower",
            manager=self.manager,
        )
        y += 32

        y += 8
        self.ui["title_deaths"] = UILabel(
            relative_rect=pygame.Rect(px + 10, y, pw - 20, 20),
            text="DEATHS (cumulative)",
            manager=self.manager,
        )
        y += 22
        self.ui["deaths_header_prey"] = UILabel(
            relative_rect=pygame.Rect(px + 125, y, 70, 20),
            text="Prey",
            manager=self.manager,
        )
        self.ui["deaths_header_pred"] = UILabel(
            relative_rect=pygame.Rect(px + 200, y, 70, 20),
            text="Pred",
            manager=self.manager,
        )
        y += 22
        for cause in ("starvation", "predation", "senescence"):
            self.ui[f"deaths_label_{cause}"] = UILabel(
                relative_rect=pygame.Rect(px + 10, y, 110, 20),
                text=cause,
                manager=self.manager,
            )
            self.ui[f"deaths_prey_{cause}"] = UILabel(
                relative_rect=pygame.Rect(px + 125, y, 70, 20),
                text="0",
                manager=self.manager,
            )
            self.ui[f"deaths_pred_{cause}"] = UILabel(
                relative_rect=pygame.Rect(px + 200, y, 70, 20),
                text="0",
                manager=self.manager,
            )
            y += 20

        y += 8
        self.ui["title_genes"] = UILabel(
            relative_rect=pygame.Rect(px + 10, y, pw - 20, 20),
            text="GENES (population avg)",
            manager=self.manager,
        )
        y += 22
        self.ui["gene_header_prey"] = UILabel(
            relative_rect=pygame.Rect(px + 125, y, 70, 20),
            text="Prey",
            manager=self.manager,
        )
        self.ui["gene_header_pred"] = UILabel(
            relative_rect=pygame.Rect(px + 200, y, 70, 20),
            text="Pred",
            manager=self.manager,
        )
        y += 22
        for display_key, label in [
            ("eat_energy", "eat energy"),
            ("move_cost", "move cost"),
            ("max_energy", "max energy"),
            ("reproduce_energy", "repro energy"),
            ("reproduce_chance", "repro chance"),
            ("encounter", "escape/hunt"),
            ("move_distance", "move dist"),
            ("max_age", "max age"),
            ("metabolism", "metabolism"),
            ("offspring_investment", "offspring inv"),
        ]:
            self.ui[f"gene_label_{display_key}"] = UILabel(
                relative_rect=pygame.Rect(px + 10, y, 110, 20),
                text=label,
                manager=self.manager,
            )
            self.ui[f"gene_prey_{display_key}"] = UILabel(
                relative_rect=pygame.Rect(px + 125, y, 70, 20),
                text="-",
                manager=self.manager,
            )
            self.ui[f"gene_pred_{display_key}"] = UILabel(
                relative_rect=pygame.Rect(px + 200, y, 70, 20),
                text="-",
                manager=self.manager,
            )
            y += 20

        self.panel_content_height = y + 10
        max_offset = max(0, self.panel_content_height - self.sh)
        self.scroll_offset = max(0, min(self.scroll_offset, max_offset))
        if self.scroll_offset > 0:
            self._move_panel_elements(self.scroll_offset)

    def _move_panel_elements(self, delta):
        for el in self.ui.values():
            r = el.get_relative_rect()
            el.set_relative_position((r.x, r.y - delta))
        for btn in self.action_buttons.values():
            r = btn.get_relative_rect()
            btn.set_relative_position((r.x, r.y - delta))
        self.chart_rect.y -= delta

    def apply_scroll(self, delta):
        max_offset = max(0, self.panel_content_height - self.sh)
        new_offset = max(0, min(self.scroll_offset + delta, max_offset))
        actual_delta = new_offset - self.scroll_offset
        if actual_delta != 0:
            self.scroll_offset = new_offset
            self._move_panel_elements(actual_delta)

    def update_panel_ui(self, sim, paused, speed):
        prey, pred = sim.counts()
        pe, de = sim.avg_energy()
        self.ui["step"].set_text(f"Step: {sim.step_count}")
        self.ui["status"].set_text("PAUSED" if paused else f"{speed} FPS")
        self.ui["prey"].set_text(f"Prey: {prey}")
        self.ui["pred"].set_text(f"Preds: {pred}")
        self.ui["ratio"].set_text(f"Ratio: {prey/(pred+1e-9):.1f}:1")
        self.ui["prey_energy"].set_text(f"Prey en: {pe:.1f}")
        self.ui["pred_energy"].set_text(f"Pred en: {de:.1f}")
        self.ui["prey_rep"].set_text(f"Prey rep: {self.cfg['prey_reproduce_chance']:.3f}")
        self.ui["pred_rep"].set_text(f"Pred rep: {self.cfg['predator_reproduce_chance']:.3f}")
        self.ui["grid"].set_text(f"Grid: {sim.gw}x{sim.gh}")
        self.ui["grass"].set_text(f"Grass: {self.cfg['grass_regrowth_rate']:.3f}")
        for cause in ("starvation", "predation", "senescence"):
            self.ui[f"deaths_prey_{cause}"].set_text(str(sim.deaths["prey"][cause]))
            self.ui[f"deaths_pred_{cause}"].set_text(str(sim.deaths["predator"][cause]))
        self._update_genes_ui(sim)

    def _update_genes_ui(self, sim):
        selected = None
        if self.selected_id is not None:
            selected = next((a for a in sim.animals if a.id == self.selected_id and a.is_alive()), None)
            if selected is None:
                self.selected_id = None

        if selected is not None:
            self.ui["title_genes"].set_text(f"GENES (selected {selected.kind} #{selected.id})")
        else:
            self.ui["title_genes"].set_text("GENES (population avg)")

        prey_animals = [a for a in sim.animals if a.kind == 'prey' and a.is_alive()]
        pred_animals = [a for a in sim.animals if a.kind == 'predator' and a.is_alive()]

        def avg(animals, gene_key):
            vals = [a.genes[gene_key] for a in animals if gene_key in a.genes]
            return sum(vals) / len(vals) if vals else 0.0

        rows = [
            ("eat_energy", "eat_energy", "eat_energy"),
            ("move_cost", "move_cost", "move_cost"),
            ("max_energy", "max_energy", "max_energy"),
            ("reproduce_energy", "reproduce_energy", "reproduce_energy"),
            ("reproduce_chance", "reproduce_chance", "reproduce_chance"),
            ("encounter", "escape_chance", "hunt_success"),
            ("move_distance", "move_distance", "move_distance"),
            ("max_age", "max_age", "max_age"),
            ("metabolism", "metabolism", "metabolism"),
            ("offspring_investment", "offspring_investment", "offspring_investment"),
        ]
        for display_key, prey_gene, pred_gene in rows:
            if selected is not None and selected.kind == 'prey':
                prey_val = selected.genes.get(prey_gene, 0.0)
            else:
                prey_val = avg(prey_animals, prey_gene)
            if selected is not None and selected.kind == 'predator':
                pred_val = selected.genes.get(pred_gene, 0.0)
            else:
                pred_val = avg(pred_animals, pred_gene)
            self.ui[f"gene_prey_{display_key}"].set_text(f"{prey_val:.2f}")
            self.ui[f"gene_pred_{display_key}"].set_text(f"{pred_val:.2f}")

    def draw_map(self, sim):
        c = self.cell
        for y, row in enumerate(sim.grass):
            for x, gc in enumerate(row):
                pygame.draw.rect(self.screen, gc.color, (x*c, y*c, c-1, c-1))
        for a in sim.animals:
            cx = a.x*c + c//2
            cy = a.y*c + c//2
            r = max(2, c//3)
            if a.kind == 'prey':
                pygame.draw.circle(self.screen, C_PREY_COL, (cx, cy), r)
                pygame.draw.circle(self.screen, C_PREY_DARK, (cx, cy), r, 1)
            else:
                pts = [(cx, cy-r), (cx-r, cy+r), (cx+r, cy+r)]
                pygame.draw.polygon(self.screen, C_PRED_COL, pts)
                pygame.draw.polygon(self.screen, C_PRED_DARK, pts, 1)
            if a.id == self.selected_id:
                pygame.draw.circle(self.screen, C_HIGHLIGHT, (cx, cy), r + 3, 2)

    def draw_chart(self, sim):
        x0, y0, w, h = self.chart_rect
        pygame.draw.rect(self.screen, C_PANEL2, self.chart_rect)
        pygame.draw.rect(self.screen, C_BORDER, self.chart_rect, 1)
        if len(sim.hist_prey) < 2:
            return
        max_pop = max(max(sim.hist_prey, default=1), max(sim.hist_pred, default=1), 1)

        def pts_for(data, vmax):
            n = len(data)
            return [(x0 + int(i/(n-1)*(w-2))+1,
                     y0 + h - int((v/vmax)*(h-6)) - 3)
                    for i, v in enumerate(data)]

        for data, color, vmax in [
            (list(sim.hist_grass), C_GRASS_COL, 100),
            (list(sim.hist_prey), C_PREY_COL, max_pop),
            (list(sim.hist_pred), C_PRED_COL, max_pop),
        ]:
            if len(data) >= 2:
                pygame.draw.lines(self.screen, color, False, pts_for(data, vmax), 2)

    def draw_panel_background(self):
        px, pw, ph = self.panel_x, self.PANEL, self.sh
        pygame.draw.rect(self.screen, C_PANEL, (px, 0, pw, ph))
        pygame.draw.line(self.screen, C_BORDER, (px, 0), (px, ph), 2)
        for key, color in [("chart_prey", C_PREY_COL), ("chart_pred", C_PRED_COL), ("chart_grass", C_GRASS_COL)]:
            rect = self.ui[key].get_relative_rect()
            pygame.draw.rect(self.screen, color, (rect.x, rect.y + 6, 8, 6))

    def draw_panel(self, sim, paused, speed):
        self.update_panel_ui(sim, paused, speed)
        self.draw_panel_background()
        original_clip = self.screen.get_clip()
        self.screen.set_clip(pygame.Rect(self.panel_x, 0, self.PANEL, self.sh))
        self.draw_chart(sim)
        self.manager.draw_ui(self.screen)
        self.screen.set_clip(original_clip)

    def tick(self, fps):
        return self.clock.tick(fps) / 1000.0


def run_simulation(cfg):
    sim = Simulation(cfg)
    renderer = SimRenderer(cfg)
    paused = False
    speed = int(cfg.get("simulation_speed", 10))

    while True:
        time_delta = renderer.tick(speed if not paused else 30)
        renderer.screen.fill(C_BG)
        renderer.draw_map(sim)
        renderer.draw_panel(sim, paused, speed)
        pygame.display.flip()

        if not paused:
            sim.step()
            if all(c == 0 for c in sim.counts()):
                paused = True

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.VIDEORESIZE:
                renderer.handle_resize(event.size)
                continue
            renderer.manager.process_events(event)
            if event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()
                if mx >= renderer.panel_x:
                    renderer.apply_scroll(-event.y * 30)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if mx < renderer.map_w and my < renderer.map_h and renderer.cell > 0:
                    gx, gy = mx // renderer.cell, my // renderer.cell
                    clicked = next(
                        (a for a in sim.animals if a.x == gx and a.y == gy and a.is_alive()),
                        None,
                    )
                    renderer.selected_id = clicked.id if clicked else None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key in (pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_EQUALS):
                    speed = min(60, speed + 5)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    speed = max(1, speed - 5)
                elif event.key == pygame.K_r:
                    sim = Simulation(cfg)
                    renderer.selected_id = None
                elif event.key == pygame.K_ESCAPE:
                    pygame.display.quit()
                    return
            elif event.type == pygame_gui.UI_BUTTON_PRESSED:
                if event.ui_element == renderer.action_buttons.get("pause"):
                    paused = not paused
                elif event.ui_element == renderer.action_buttons.get("faster"):
                    speed = min(60, speed + 5)
                elif event.ui_element == renderer.action_buttons.get("slower"):
                    speed = max(1, speed - 5)
        renderer.manager.update(time_delta)


def main():
    while True:
        cfg = run_config_screen()
        run_simulation(cfg)

if __name__ == "__main__":
    main()
