# main.py
import pygame
import sys
import os
import math
import random
from utils.settings import *
from utils.settings import load_game_data, save_game_data
from utils.asset_manager import AssetManager
from core.level import LevelManager


class App:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Modern Defense: Operations")
        self.clock = pygame.time.Clock()
        self.assets = AssetManager()

        load_game_data()
        self.sandbox_mode = False
        self.game_speed = 1

        self.assets.play_bgm("bgm.mp3", volume=0.25)

        font_path = "assets/Anton.ttf"
        if os.path.exists(font_path):
            self.font_title = pygame.font.Font(font_path, 80)
            self.font_subtitle = pygame.font.Font(font_path, 40)
        else:
            self.font_title = pygame.font.Font(None, 80)
            self.font_subtitle = pygame.font.Font(None, 40)

        self.font_btn = pygame.font.Font(None, 28)
        self.font_info = pygame.font.Font(None, 24)
        self.font_hud = pygame.font.Font(None, 20)

        self.state = "MENU"
        self.current_level = None
        self.current_level_id = 1
        self.preview_data = None

        # --- 新增：淡入淡出管理器变量 ---
        self.fade_alpha = 0
        self.fade_state = "IDLE"
        self.next_state = None

        self.bg_timer = 0
        self.radar_angle = 0
        self.particles = []
        for _ in range(60):
            self.particles.append([
                random.randint(0, WIDTH), random.randint(0, HEIGHT),
                random.uniform(-0.5, 0.5), random.uniform(-1.5, -0.2), random.randint(20, 100)
            ])

        self.fake_targets = []
        for _ in range(8):
            self.fake_targets.append({
                "x": random.randint(100, WIDTH - 100), "y": random.randint(100, HEIGHT - 100),
                "dx": random.uniform(-0.8, 0.8), "dy": random.uniform(-0.8, 0.8), "history": []
            })

        self.scanline_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for y in range(0, HEIGHT, 3):
            pygame.draw.line(self.scanline_surf, (0, 0, 0, 40), (0, y), (WIDTH, y), 1)
        pygame.draw.rect(self.scanline_surf, (0, 0, 0, 180), (0, 0, WIDTH, HEIGHT), 60)
        pygame.draw.rect(self.scanline_surf, (0, 0, 0, 100), (0, 0, WIDTH, HEIGHT), 120)

    # --- 新增：触发界面渐变的函数 ---
    def trigger_transition(self, next_state):
        if self.state == next_state:
            return
        self.next_state = next_state
        self.fade_state = "OUT"

    def draw_button(self, text, rect, mouse_pos, color_base=(70, 80, 90)):
        if rect.collidepoint(mouse_pos):
            color = (min(color_base[0] + 30, 255), min(color_base[1] + 30, 255), min(color_base[2] + 30, 255))
        else:
            color = color_base

        pygame.draw.rect(self.screen, color, rect, border_radius=5)
        pygame.draw.rect(self.screen, (200, 200, 200), rect, 2, border_radius=5)
        txt_surf = self.font_btn.render(text, True, COLOR_TEXT)
        self.screen.blit(txt_surf,
                         (rect.centerx - txt_surf.get_width() // 2, rect.centery - txt_surf.get_height() // 2))
        return rect.collidepoint(mouse_pos)

    def draw_locked_button(self, text, rect):
        pygame.draw.rect(self.screen, (40, 40, 40), rect, border_radius=5)
        pygame.draw.rect(self.screen, (80, 80, 80), rect, 2, border_radius=5)
        txt_surf = self.font_btn.render(text, True, (120, 120, 120))
        self.screen.blit(txt_surf,
                         (rect.centerx - txt_surf.get_width() // 2, rect.centery - txt_surf.get_height() // 2))
        return False

    def draw_minimap(self, map_grid, x, y, max_w, max_h):
        rows = len(map_grid)
        cols = len(map_grid[0])
        cell_size = min(max_w // cols, max_h // rows)
        map_w = cols * cell_size
        map_h = rows * cell_size
        start_x = x + (max_w - map_w) // 2
        start_y = y + (max_h - map_h) // 2

        pygame.draw.rect(self.screen, (100, 150, 100), (start_x - 2, start_y - 2, map_w + 4, map_h + 4), 2)

        for r in range(rows):
            for c in range(cols):
                val = map_grid[r][c]
                rect = (start_x + c * cell_size, start_y + r * cell_size, cell_size, cell_size)
                if val == 0:
                    pygame.draw.rect(self.screen, COLOR_GRASS, rect)
                elif val == 1:
                    pygame.draw.rect(self.screen, COLOR_ROAD, rect)
                elif val == 2:
                    pygame.draw.rect(self.screen, COLOR_BASE, rect)
                elif val == 4:
                    pygame.draw.rect(self.screen, (180, 100, 50), rect)
                pygame.draw.rect(self.screen, (50, 60, 50), rect, 1)

    def draw_tactical_radar_bg(self):
        self.bg_timer += 1
        self.screen.fill((8, 12, 18))

        offset_x = (self.bg_timer * 0.3) % 100
        offset_y = (self.bg_timer * 0.3) % 100

        for x in range(int(offset_x) - 100, WIDTH, 100):
            pygame.draw.line(self.screen, (15, 25, 35), (x, 0), (x, HEIGHT), 1)
        for y in range(int(offset_y) - 100, HEIGHT, 100):
            pygame.draw.line(self.screen, (15, 25, 35), (0, y), (WIDTH, y), 1)

        center_x, center_y = WIDTH // 2, HEIGHT // 2
        pulse_radius = (self.bg_timer * 2.5) % 600
        pulse_alpha = max(0, 100 - int((pulse_radius / 600) * 100))

        if pulse_radius > 0:
            pulse_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.circle(pulse_surf, (50, 120, 80, pulse_alpha), (center_x, center_y), int(pulse_radius), 2)
            self.screen.blit(pulse_surf, (0, 0))

        pygame.draw.circle(self.screen, (20, 50, 35), (center_x, center_y), 400, 1)
        pygame.draw.circle(self.screen, (20, 50, 35), (center_x, center_y), 250, 1)
        pygame.draw.circle(self.screen, (20, 50, 35), (center_x, center_y), 100, 1)

        self.radar_angle = (self.radar_angle + 1.5) % 360
        sweep_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        points = [(center_x, center_y)]

        for angle in range(int(self.radar_angle) - 45, int(self.radar_angle)):
            rad = math.radians(angle)
            points.append((center_x + 600 * math.cos(rad), center_y + 600 * math.sin(rad)))

        if len(points) > 2:
            pygame.draw.polygon(sweep_surf, (40, 150, 80, 15), points)
        self.screen.blit(sweep_surf, (0, 0))

        for p in self.particles:
            p[0] += p[2]
            p[1] += p[3]
            if p[1] < 0:
                p[1] = HEIGHT
                p[0] = random.randint(0, WIDTH)
            pygame.draw.circle(self.screen, (100, 150, 200, p[4]), (int(p[0]), int(p[1])), 2)

    def run(self):
        while True:
            mouse_pos = pygame.mouse.get_pos()
            click = False
            click_button = 0

            # --- 淡出时拦截所有操作 ---
            allow_input = (self.fade_state == "IDLE")

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if allow_input and event.type == pygame.MOUSEBUTTONDOWN:
                    click = True
                    click_button = event.button
                if allow_input and event.type == pygame.KEYDOWN and self.state in ["PLAYING", "PAUSED"]:
                    if event.key == pygame.K_SPACE:
                        self.game_speed = 1 if self.game_speed == 3 else self.game_speed + 1
                        self.assets.play_sound("switch")
                    else:
                        self.current_level.handle_keydown(event.key)

            self.screen.fill(COLOR_UI_BG)

            if self.state in ["MENU", "TECH_LAB", "LEVEL_PREVIEW"]:
                self.draw_tactical_radar_bg()

            if self.state == "MENU":
                title_shadow = self.font_title.render("MODERN DEFENSE", True, (0, 0, 0))
                title = self.font_title.render("MODERN DEFENSE", True, (255, 215, 0))
                self.screen.blit(title_shadow, (WIDTH // 2 - title.get_width() // 2 + 4, 34))
                self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 30))

                tech_text = self.font_btn.render(f"TECH POINTS AVAILABLE: {PLAYER_DATA['tech_points']}", True,
                                                 (100, 200, 255))
                self.screen.blit(tech_text, (WIDTH // 2 - tech_text.get_width() // 2, 110))

                btn_tech = pygame.Rect(WIDTH // 2 - 150, 150, 300, 45)
                if self.draw_button("ENTER TECH LAB", btn_tech, mouse_pos,
                                    (50, 100, 150)) and click and click_button == 1:
                    self.assets.play_sound("switch")
                    self.trigger_transition("TECH_LAB")

                btn_override = pygame.Rect(WIDTH - 250, 20, 230, 40)
                btn_text = "SANDBOX: ON" if self.sandbox_mode else "SANDBOX: OFF"
                btn_color = (150, 50, 50) if self.sandbox_mode else (80, 100, 120)
                if self.draw_button(btn_text, btn_override, mouse_pos, btn_color) and click and click_button == 1:
                    self.sandbox_mode = not self.sandbox_mode
                    self.assets.play_sound("switch")

                start_y = 220
                for level_id, data in LEVELS.items():
                    btn_rect = pygame.Rect(WIDTH // 2 - 150, start_y, 300, 45)
                    is_unlocked = self.sandbox_mode or (level_id <= PLAYER_DATA["unlocked_levels"])
                    color = (70, 80, 90) if is_unlocked else (40, 40, 50)

                    base_text = data["name"] if is_unlocked else f"OPERATION {level_id}: CLASSIFIED"
                    if level_id == 7 and PLAYER_DATA["highest_endless_wave"] > 0:
                        base_text += f" (BEST: W{PLAYER_DATA['highest_endless_wave']})"

                    if self.draw_button(base_text, btn_rect, mouse_pos, color) and click and click_button == 1:
                        self.assets.play_sound("switch")
                        self.current_level_id = level_id
                        self.preview_data = data
                        self.trigger_transition("LEVEL_PREVIEW")

                    start_y += 60

                btn_quit = pygame.Rect(WIDTH // 2 - 150, start_y + 20, 300, 45)
                if self.draw_button("EXIT TERMINAL", btn_quit, mouse_pos,
                                    (150, 50, 50)) and click and click_button == 1:
                    pygame.quit()
                    sys.exit()

            elif self.state == "LEVEL_PREVIEW":
                title = self.font_subtitle.render("TACTICAL BRIEFING", True, (100, 200, 255))
                self.screen.blit(title, (40, 40))
                self.screen.blit(self.font_title.render(self.preview_data["name"], True, (255, 215, 0)), (40, 90))
                pygame.draw.line(self.screen, (100, 100, 100), (40, 170), (WIDTH - 40, 170), 2)
                self.screen.blit(self.font_btn.render("TOPOGRAPHY SCANS:", True, (180, 180, 180)), (40, 190))
                self.draw_minimap(self.preview_data["map"], 40, 230, 450, 350)

                param_x = 520
                start_y = 190
                params = [
                    f"DIFFICULTY MODIFIER: x{self.preview_data['difficulty']}",
                    f"INITIAL FUNDS: ${self.preview_data['initial_funds']}",
                    f"MAX TOWERS ALLOWED: {self.preview_data['max_towers']}"
                ]

                for p in params:
                    self.screen.blit(self.font_btn.render(p, True, (200, 255, 200)), (param_x, start_y))
                    start_y += 35

                start_y += 20
                self.screen.blit(self.font_btn.render("ENEMY INTEL:", True, (255, 100, 100)), (param_x, start_y))
                start_y += 35

                for enemy_name, count in self.preview_data.get("intel", {}).items():
                    if count > 0:
                        count_text = "INFINITE" if count > 900 else f"~{count} units"
                        color = (255, 50, 50) if "Boss" in enemy_name else (200, 200, 200)
                        self.screen.blit(self.font_info.render(f"- {enemy_name}: {count_text}", True, color),
                                         (param_x + 10, start_y))
                        start_y += 25

                is_unlocked = self.sandbox_mode or (self.current_level_id <= PLAYER_DATA["unlocked_levels"])
                btn_start = pygame.Rect(WIDTH - 340, HEIGHT - 100, 300, 50)
                btn_back = pygame.Rect(40, HEIGHT - 100, 300, 50)

                if self.draw_button("RETURN TO MENU", btn_back, mouse_pos) and click and click_button == 1:
                    self.assets.play_sound("switch")
                    self.trigger_transition("MENU")

                if is_unlocked:
                    if self.draw_button("START OPERATION", btn_start, mouse_pos,
                                        (50, 150, 50)) and click and click_button == 1:
                        self.assets.play_sound("switch")
                        self.assets.set_bgm_volume(0.1)
                        self.trigger_transition("PLAYING")
                else:
                    self.draw_locked_button("LOCKED - COMPLETE PREVIOUS", btn_start)

            elif self.state == "TECH_LAB":
                title = self.font_title.render("RESEARCH & DEVELOPMENT", True, (100, 200, 255))
                self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 50))
                self.screen.blit(
                    self.font_btn.render(f"AVAILABLE TECH POINTS: {PLAYER_DATA['tech_points']}", True, (255, 215, 0)),
                    (WIDTH // 2 - 130, 140))

                skills = [
                    ("dmg_boost", "ADVANCED AMMO (1 PT)", "+20% Damage per level."),
                    ("cost_down", "ENGINEERING (1 PT)", "-10% Build Cost per level."),
                    ("base_armor", "FORTIFIED BASE (1 PT)", "+10 Tower & Base HP per level.")
                ]
                start_y = 200
                spent_points = sum(PLAYER_DATA["upgrades"].values())

                for key, name, desc in skills:
                    btn_rect = pygame.Rect(WIDTH // 2 - 200, start_y, 400, 45)
                    if self.draw_button(f"{name} [LVL {PLAYER_DATA['upgrades'][key]}]", btn_rect,
                                        mouse_pos) and click and click_button == 1:
                        if PLAYER_DATA["tech_points"] >= 1:
                            self.assets.play_sound("build")
                            PLAYER_DATA["upgrades"][key] += 1
                            PLAYER_DATA["tech_points"] -= 1
                            save_game_data()
                        else:
                            self.assets.play_sound("error")

                    desc_surf = self.font_info.render(desc, True, (180, 180, 180))
                    self.screen.blit(desc_surf, (WIDTH // 2 - desc_surf.get_width() // 2, start_y + 50))
                    start_y += 85

                btn_respec = pygame.Rect(WIDTH // 2 - 150, start_y, 300, 45)
                if spent_points > 0:
                    if PLAYER_DATA["respec_tokens"] > 0:
                        if self.draw_button(f"RESET TECH (TOKENS: {PLAYER_DATA['respec_tokens']})", btn_respec,
                                            mouse_pos, (200, 100, 50)) and click and click_button == 1:
                            self.assets.play_sound("switch")
                            PLAYER_DATA["respec_tokens"] -= 1
                            PLAYER_DATA["tech_points"] += spent_points
                            for k in PLAYER_DATA["upgrades"]:
                                PLAYER_DATA["upgrades"][k] = 0
                            save_game_data()
                    else:
                        self.draw_locked_button("NEED TOKENS TO RESET", btn_respec)

                btn_back = pygame.Rect(WIDTH // 2 - 150, start_y + 60, 300, 45)
                if self.draw_button("RETURN TO MENU", btn_back, mouse_pos) and click and click_button == 1:
                    self.assets.play_sound("switch")
                    self.trigger_transition("MENU")

            elif self.state == "PLAYING" or self.state == "PAUSED":
                self.screen.fill(COLOR_UI_BG)

                # 只有正式进入 PLAYING 且转场完毕后才初始化关卡，防止闪屏
                if self.current_level is None:
                    self.current_level = LevelManager(self.screen, self.preview_data, self.assets,
                                                      self.current_level_id)

                if click:
                    self.current_level.handle_click(mouse_pos, click_button)

                if self.state == "PLAYING" and self.fade_state == "IDLE":
                    for _ in range(self.game_speed):
                        self.current_level.update()

                self.current_level.draw()

                if self.state == "PLAYING":
                    spd_w, spd_h = 160, 24
                    btn_rect = pygame.Rect(WIDTH - spd_w - 10, 3, spd_w, spd_h)

                    if self.game_speed == 1:
                        color = (100, 255, 100)
                    elif self.game_speed == 2:
                        color = (255, 200, 50)
                    else:
                        color = (255, 50, 50)

                    pygame.draw.rect(self.screen, (20, 25, 30), btn_rect, border_radius=12)
                    pygame.draw.rect(self.screen, color, btn_rect, 1, border_radius=12)

                    speed_str = "1X" if self.game_speed == 1 else ("2X" if self.game_speed == 2 else "3X")
                    text = f"[SPACE]  ▶  SPEED {speed_str}"
                    surf = self.font_hud.render(text, True, color)
                    self.screen.blit(surf, (btn_rect.centerx - surf.get_width() // 2,
                                            btn_rect.centery - surf.get_height() // 2))

                # 战局结束时触发转场
                if self.current_level.state == "EXIT_VICTORY":
                    if self.current_level_id == PLAYER_DATA["unlocked_levels"]:
                        PLAYER_DATA["unlocked_levels"] += 1
                        PLAYER_DATA["tech_points"] += 1
                        save_game_data()
                    PLAYER_DATA["respec_tokens"] += 1
                    self.assets.set_bgm_volume(0.25)
                    self.game_speed = 1
                    self.current_level.state = "TRANSITIONING"  # 锁住防止多次触发
                    self.trigger_transition("MENU")

                elif self.current_level.state in ["EXIT_DEFEAT", "EXIT_ABORT"]:
                    self.assets.set_bgm_volume(0.25)
                    self.game_speed = 1
                    self.current_level.state = "TRANSITIONING"
                    self.trigger_transition("MENU")

            if self.state in ["MENU", "TECH_LAB", "LEVEL_PREVIEW"]:
                self.screen.blit(self.scanline_surf, (0, 0))

            # --- 全局淡入淡出核心处理层 ---
            if self.fade_state == "OUT":
                self.fade_alpha += 15
                if self.fade_alpha >= 255:
                    self.fade_alpha = 255
                    self.state = self.next_state
                    if self.state == "MENU":
                        self.current_level = None  # 转到黑屏时销毁关卡释放内存
                    self.fade_state = "IN"
            elif self.fade_state == "IN":
                self.fade_alpha -= 15
                if self.fade_alpha <= 0:
                    self.fade_alpha = 0
                    self.fade_state = "IDLE"

            if self.fade_alpha > 0:
                fade_surf = pygame.Surface((WIDTH, HEIGHT))
                fade_surf.fill((0, 0, 0))
                fade_surf.set_alpha(self.fade_alpha)
                self.screen.blit(fade_surf, (0, 0))

            pygame.display.flip()
            self.clock.tick(FPS)


if __name__ == "__main__":
    app = App()
    app.run()