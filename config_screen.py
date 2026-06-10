import json
import os
import sys

import pygame
import pygame_gui
from pygame_gui.elements import UIButton, UIDropDownMenu, UILabel, UIScrollingContainer, UITextBox, UITextEntryLine

from configs.colors import *

DEFAULT_CONFIG_PATH = os.path.join("configs", "parameters", "default.json")
PARAMETERS_DIR = os.path.dirname(DEFAULT_CONFIG_PATH)
PARAM_GROUPS_PATH = os.path.join("configs", "param_groups.json")
LAYOUT_PATH = os.path.join("configs", "layout.json")
GENES_INFO_PATH = os.path.join("configs", "genes_info.json")


def load_layout():
    with open(LAYOUT_PATH, encoding="utf-8") as f:
        return json.load(f)


_LAYOUT = load_layout()
HEADER_H = _LAYOUT["header_h"]
TOPBAR_H = _LAYOUT["topbar_h"]
SEP_H = _LAYOUT["sep_h"]
FOOTER_H = _LAYOUT["footer_h"]
WIN_W = _LAYOUT["win_w"]
WIN_H = _LAYOUT["win_h"]
ROW_H = _LAYOUT["row_h"]
LBL_W = _LAYOUT["lbl_w"]
COLS = _LAYOUT["cols"]
SECTION_HEADER_H = _LAYOUT["section_header_h"]
SECTION_HEADER_GAP = _LAYOUT["section_header_gap"]
SECTION_GAP = _LAYOUT["section_gap"]
TABS_H = _LAYOUT["tabs_h"]
TABS_GAP = _LAYOUT["tabs_gap"]


def build_genes_html(data):
    parts = [f"<b>{data['title']}</b><br><br>", data["intro_html"], "<br><br>"]
    for gene in data["genes"]:
        parts.append(f"<b>{gene['name']}</b>")
        if gene.get("qualifier"):
            parts.append(f" <i>{gene['qualifier']}</i>")
        parts.append(f"<br>{gene['description_html']}<br><br>")
    parts.append(f"<b>{data['mutation_title']}</b><br><br>")
    parts.append(data["mutation_intro_html"])
    parts.append("<br><br>")
    for param in data["mutation_params"]:
        parts.append(f"<b>{param['name']}</b><br>{param['description_html']}<br><br>")
    return "".join(parts).rstrip()


def load_genes_info():
    with open(GENES_INFO_PATH, encoding="utf-8") as f:
        return json.load(f)


GENES_INFO_HTML = build_genes_html(load_genes_info())


def load_param_groups():
    with open(PARAM_GROUPS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return [(g["key"], g["title"], list(g["params"])) for g in data["groups"]]


PARAM_GROUPS = load_param_groups()


def _normalize_grouped(data):
    if data and all(isinstance(v, dict) for v in data.values()):
        return data
    grouped = {}
    for group_name, _, keys in PARAM_GROUPS:
        grouped[group_name] = {k: data[k] for k in keys if k in data}
    return grouped


def flatten_grouped(grouped):
    flat = {}
    for group_data in grouped.values():
        if isinstance(group_data, dict):
            flat.update(group_data)
    return flat


def load_json_config(path):
    with open(path, encoding="utf-8") as f:
        return _normalize_grouped(json.load(f))


def ensure_parameters_dir():
    os.makedirs(PARAMETERS_DIR, exist_ok=True)


def list_parameter_files():
    ensure_parameters_dir()
    return sorted(name for name in os.listdir(PARAMETERS_DIR) if name.endswith(".json"))


DEFAULT_CONFIG_GROUPED = load_json_config(DEFAULT_CONFIG_PATH)
DEFAULT_CONFIG = flatten_grouped(DEFAULT_CONFIG_GROUPED)


def infer_value_type(value):
    return float if isinstance(value, float) else int


def prettify_label(key):
    return key.replace("_", " ").capitalize()


class ConfigScreen:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE)
        pygame.display.set_caption("Coevolution Simulator")
        self.clock = pygame.time.Clock()
        self.cfg = dict(DEFAULT_CONFIG)
        self.status_message = "Set parameters and click START"
        self.selected_file = os.path.basename(DEFAULT_CONFIG_PATH)
        self.ui = {}
        self.input_fields = {}
        self.manager = None
        self.view_mode = "config"
        self.build_ui()

    def format_value(self, key, value):
        value_type = infer_value_type(DEFAULT_CONFIG[key])
        return f"{value:.3f}" if value_type == float else str(int(value))

    def parse_input_value(self, key, text):
        value_text = text.strip().replace(",", ".")
        if not value_text:
            raise ValueError("puste pole")
        value_type = infer_value_type(DEFAULT_CONFIG[key])
        return int(value_text) if value_type == int else float(value_text)

    def set_status(self, message):
        self.status_message = message
        if self.ui.get("status_label"):
            self.ui["status_label"].set_text(message)

    def preserve_ui_state(self):
        values = {key: field.get_text() for key, field in self.input_fields.items()}
        save_name = self.ui["save_name_entry"].get_text() if self.ui.get("save_name_entry") else "config"
        return values, save_name

    def build_ui(self):
        size = self.screen.get_size()
        preserved_values = {}
        save_name = "config"
        if self.input_fields:
            preserved_values, save_name = self.preserve_ui_state()

        self.manager = pygame_gui.UIManager(size, os.path.join("configs", "styles.json"))
        self.manager.preload_fonts([
            {"name": "noto_sans", "point_size": 14, "style": "bold"},
            {"name": "noto_sans", "point_size": 14, "style": "bold_italic"},
        ])
        self.ui = {}
        self.input_fields = {}
        W, H = size

        self.ui["title"] = UILabel(
            relative_rect=pygame.Rect(W // 2 - 300, 12, 600, 48),
            text="PREDATOR–PREY COEVOLUTION SIMULATION",
            manager=self.manager,
            object_id="#title",
        )

        file_options = list_parameter_files() or [os.path.basename(DEFAULT_CONFIG_PATH)]
        if self.selected_file not in file_options:
            self.selected_file = file_options[0]

        top_y = HEADER_H + 6
        self.ui["files_label"] = UILabel(
            relative_rect=pygame.Rect(16, top_y, 140, 24),
            text="Configuration file:",
            manager=self.manager,
        )
        self.ui["file_dropdown"] = UIDropDownMenu(
            options_list=file_options,
            starting_option=self.selected_file,
            relative_rect=pygame.Rect(160, top_y, 230, 30),
            manager=self.manager,
        )
        self.ui["load_button"] = UIButton(
            relative_rect=pygame.Rect(400, top_y, 92, 30),
            text="Load",
            manager=self.manager,
        )
        self.ui["save_name_label"] = UILabel(
            relative_rect=pygame.Rect(W - 350, top_y, 90, 24),
            text="Save as:",
            manager=self.manager,
        )
        self.ui["save_name_entry"] = UITextEntryLine(
            relative_rect=pygame.Rect(W - 255, top_y, 155, 30),
            manager=self.manager,
        )
        self.ui["save_name_entry"].set_text(save_name)
        self.ui["save_button"] = UIButton(
            relative_rect=pygame.Rect(W - 92, top_y, 76, 30),
            text="Save",
            manager=self.manager,
        )

        tabs_y = HEADER_H + TOPBAR_H + SEP_H + TABS_GAP
        tab_w = 180
        for i, (key, label) in enumerate([("config", "Configuration"), ("genes", "Genes")]):
            self.ui[f"tab_{key}"] = UIButton(
                relative_rect=pygame.Rect(16 + i * (tab_w + 8), tabs_y, tab_w, TABS_H),
                text=label,
                manager=self.manager,
                object_id="#tab_active" if self.view_mode == key else None,
            )

        content_top = tabs_y + TABS_H + TABS_GAP
        footer_y = H - FOOTER_H
        area_h = max(60, footer_y - content_top - 8)

        if self.view_mode == "genes":
            self.ui["genes_textbox"] = UITextBox(
                relative_rect=pygame.Rect(16, content_top, W - 32, area_h),
                html_text=GENES_INFO_HTML,
                manager=self.manager,
            )
        else:
            self._build_config_sections(W, content_top, area_h, preserved_values)

        self.ui["status_label"] = UILabel(
            relative_rect=pygame.Rect(16, footer_y + 18, 300, 40),
            text=self.status_message,
            manager=self.manager,
        )
        self.ui["start_button"] = UIButton(
            relative_rect=pygame.Rect(W // 2 - 140, footer_y + 18, 280, 40),
            text="START",
            manager=self.manager,
        )

    def _build_config_sections(self, W, content_top, area_h, preserved_values):
        container = UIScrollingContainer(
            relative_rect=pygame.Rect(8, content_top, W - 16, area_h),
            manager=self.manager,
            allow_scroll_x=False,
        )
        self.ui["param_scroll"] = container

        inner_w = (W - 16) - 25
        cols = max(1, min(COLS, inner_w // (LBL_W + 150)))
        col_w = inner_w // cols
        entry_w = max(120, col_w - LBL_W - 16)

        y = 4
        for group_key, group_title, group_keys in PARAM_GROUPS:
            self.ui[f"section_{group_key}"] = UILabel(
                relative_rect=pygame.Rect(8, y, inner_w - 8, SECTION_HEADER_H),
                text=group_title,
                manager=self.manager,
                container=container,
                object_id="#section_header",
            )
            y += SECTION_HEADER_H + SECTION_HEADER_GAP

            if not group_keys:
                self.ui[f"empty_{group_key}"] = UILabel(
                    relative_rect=pygame.Rect(20, y, inner_w - 24, 24),
                    text="(no parameters — placeholder for future settings)",
                    manager=self.manager,
                    container=container,
                    object_id="#section_empty",
                )
                y += 24 + SECTION_GAP
                continue

            col_cnt = [0] * cols
            for idx, key in enumerate(group_keys):
                col = idx % cols
                row = col_cnt[col]
                xo = 8 + col * col_w
                yo = y + row * ROW_H
                col_cnt[col] += 1

                self.ui[f"label_{key}"] = UILabel(
                    relative_rect=pygame.Rect(xo, yo, LBL_W, 24),
                    text=prettify_label(key),
                    manager=self.manager,
                    container=container,
                )
                entry = UITextEntryLine(
                    relative_rect=pygame.Rect(xo + LBL_W + 8, yo, entry_w, 28),
                    manager=self.manager,
                    container=container,
                )
                entry.set_text(
                    preserved_values.get(key, self.format_value(key, self.cfg.get(key, DEFAULT_CONFIG[key])))
                )
                self.input_fields[key] = entry

            rows_used = max(col_cnt) if col_cnt else 0
            y += rows_used * ROW_H + SECTION_GAP

        container.set_scrollable_area_dimensions((inner_w, y + 6))

    def commit_inputs(self):
        for key, entry in self.input_fields.items():
            try:
                self.cfg[key] = self.parse_input_value(key, entry.get_text())
                entry.set_text(self.format_value(key, self.cfg[key]))
            except ValueError:
                self.set_status(f"Invalid value for: {prettify_label(key)}")
                return False
        return True

    def group_current_cfg(self):
        grouped = {}
        for group_key, _, group_keys in PARAM_GROUPS:
            grouped[group_key] = {k: self.cfg[k] for k in group_keys if k in self.cfg}
        return grouped

    def save_current_config(self):
        if not self.commit_inputs():
            return
        filename = self.ui["save_name_entry"].get_text().strip()
        if not filename:
            self.set_status("Enter a file name")
            return
        if any(ch in filename for ch in "\\/:*?\"<>|"):
            self.set_status("File name contains illegal characters")
            return
        if not filename.endswith(".json"):
            filename += ".json"
        path = os.path.join(PARAMETERS_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.group_current_cfg(), f, indent=2, ensure_ascii=False)
        self.selected_file = filename
        self.set_status(f"Saved: {filename}")
        self.build_ui()

    def load_selected_config(self):
        path = os.path.join(PARAMETERS_DIR, self.selected_file)
        grouped = load_json_config(path)
        data = flatten_grouped(grouped)
        self.cfg.update({k: v for k, v in data.items() if k in self.cfg})
        for key, entry in self.input_fields.items():
            entry.set_text(self.format_value(key, self.cfg[key]))
        self.set_status(f"Loaded: {self.selected_file}")

    def switch_view(self, new_mode):
        if new_mode == self.view_mode:
            return
        if self.view_mode == "config":
            self.commit_inputs()
        self.view_mode = new_mode
        self.build_ui()

    def handle_ui_event(self, event):
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.ui.get("tab_config"):
                self.switch_view("config")
            elif event.ui_element == self.ui.get("tab_genes"):
                self.switch_view("genes")
            elif event.ui_element == self.ui.get("load_button"):
                try:
                    self.load_selected_config()
                except Exception as e:
                    self.set_status(f"Load error: {e}")
            elif event.ui_element == self.ui.get("save_button"):
                try:
                    self.save_current_config()
                except Exception as e:
                    self.set_status(f"Save error: {e}")
            elif event.ui_element == self.ui.get("start_button"):
                if self.view_mode != "config":
                    self.switch_view("config")
                if self.commit_inputs():
                    pygame.display.quit()
                    return dict(self.cfg)
        elif event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if event.ui_element == self.ui.get("file_dropdown"):
                self.selected_file = event.text
        return None

    def run(self):
        while True:
            time_delta = self.clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                    self.build_ui()
                    continue
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

                self.manager.process_events(event)
                result = self.handle_ui_event(event)
                if result is not None:
                    return result

            self.manager.update(time_delta)
            W, H = self.screen.get_size()
            self.screen.fill(C_BG)
            pygame.draw.rect(self.screen, C_PANEL, (0, 0, W, HEADER_H))
            pygame.draw.line(self.screen, C_BORDER, (0, HEADER_H), (W, HEADER_H), 1)
            pygame.draw.line(self.screen, C_BORDER, (0, HEADER_H + TOPBAR_H), (W, HEADER_H + TOPBAR_H), 1)
            footer_y = H - FOOTER_H
            pygame.draw.rect(self.screen, C_PANEL, (0, footer_y, W, FOOTER_H))
            pygame.draw.line(self.screen, C_BORDER, (0, footer_y), (W, footer_y), 1)
            self.manager.draw_ui(self.screen)
            pygame.display.flip()


def run_config_screen():
    return ConfigScreen().run()
