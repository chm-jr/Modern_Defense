# core/level.py
import pygame
import random
import os
import math
from utils.settings import *
from entities.enemy import ScoutBuggy, KamikazeJeep, SiegeMech, SwarmDrone, ShieldGenerator, BossTitan
from entities.tower import MachineGunTower, SniperTower, LaserTower, Barricade, DefenseBase


class Particle:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.dx = random.uniform(-4, 4)
        self.dy = random.uniform(-4, 4)
        self.lifetime = random.randint(20, 40)
        self.max_lifetime = self.lifetime
        self.color = color
        self.size = random.randint(2, 6)

    def update(self):
        self.x += self.dx
        self.y += self.dy
        self.lifetime -= 1

    def draw(self, surface):
        if self.lifetime > 0:
            alpha = int(255 * (self.lifetime / self.max_lifetime))
            r = max(0, self.color[0] - (self.max_lifetime - self.lifetime) * 3)
            g = max(0, self.color[1] - (self.max_lifetime - self.lifetime) * 3)
            b = max(0, self.color[2] - (self.max_lifetime - self.lifetime) * 3)
            s = pygame.Surface((self.size * 2, self.size * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (r, g, b, alpha), (self.size, self.size), self.size)
            surface.blit(s, (int(self.x) - self.size, int(self.y) - self.size))


class FloatingText:
    def __init__(self, x, y, text, color, font):
        self.x = x + random.randint(-10, 10)
        self.y = y
        self.text = text
        self.color = color
        self.font = font
        self.lifetime = 40
        self.max_lifetime = 40
        self.dy = -1.2

    def update(self):
        self.y += self.dy
        self.lifetime -= 1

    def draw(self, surface):
        if self.lifetime > 0:
            alpha = int(255 * (self.lifetime / self.max_lifetime))
            bg_surf = self.font.render(self.text, True, (0, 0, 0))
            bg_surf.set_alpha(alpha)
            surface.blit(bg_surf, (self.x - bg_surf.get_width() // 2 + 1, self.y + 1))
            txt_surf = self.font.render(self.text, True, self.color)
            txt_surf.set_alpha(alpha)
            surface.blit(txt_surf, (self.x - txt_surf.get_width() // 2, self.y))


class LevelManager:
    def __init__(self, screen, level_data, assets, level_id):
        self.screen = screen
        self.assets = assets
        self.level_id = level_id
        self.end_sound_played = False

        self.font = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 20)
        font_path = "assets/Anton.ttf"
        self.large_font = pygame.font.Font(font_path, 50) if os.path.exists(font_path) else pygame.font.Font(None, 50)

        self.map_grid = level_data["map"]
        self.paths = level_data["paths"]
        self.difficulty = level_data["difficulty"]
        self.max_towers = level_data["max_towers"]
        self.is_endless = (level_id == 7)
        self.draft_options = []
        self.run_buffs = {"dmg_mult": 1.0, "range_mult": 1.0, "orbital_cd_mult": 1.0}

        self.bg_image = self.create_bg()
        self.enemies = pygame.sprite.Group()
        self.towers = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        self.bases = pygame.sprite.Group()
        self.particles = []
        self.floating_texts = []

        self.money = level_data["initial_funds"]
        self.wave = 1
        self.spawn_timer = 0
        self.enemies_to_spawn = 5
        self.state = "PLAYING"

        # --- 新增：提前叫怪的倒计时系统 ---
        self.wave_delay_timer = 0
        self.wave_delay_max = 600  # 10秒缓冲

        self.tower_classes = [MachineGunTower, SniperTower, LaserTower, Barricade]
        self.selected_tower_index = 0
        self.selected_placed_tower = None
        self.orbital_cooldown_max = 60 * 30
        self.orbital_cooldown = 0
        self.targeting_orbital = False
        self.screen_shake = 0

        for row in range(ROWS):
            for col in range(COLS):
                val = self.map_grid[row][col]
                if val == 2:
                    self.bases.add(DefenseBase(col, row, True, self.assets))
                elif val == 4:
                    self.bases.add(DefenseBase(col, row, False, self.assets))

    def _is_road(self, row, col):
        if row < 0 or row >= ROWS or col < 0 or col >= COLS:
            return False
        return self.map_grid[row][col] == 1

    def _get_road_mask(self, row, col):
        mask = 0
        if self._is_road(row - 1, col): mask |= 1  # 1=上方有路
        if self._is_road(row, col + 1): mask |= 2  # 2=右方有路
        if self._is_road(row + 1, col): mask |= 4  # 4=下方有路
        if self._is_road(row, col - 1): mask |= 8  # 8=左方有路
        return mask

    def _get_road_tile(self, mask):
        TS = (TILE_SIZE, TILE_SIZE)

        # ---------------------------------------------------------
        # 【终极一对一映射表】
        # 哪里不对改哪里，只需调整对应的角度数字 (0, 90, 180, 270)
        # ---------------------------------------------------------
        mapping = {
            # === 0. 孤立点 (周围没有路) ===
            0: ("road_end", 0),

            # === 1. 马路尽头 (单向连通) ===
            1: ("road_end", 0),  # 上端连通 (马路开口朝上)
            2: ("road_end", 270),  # 右端连通 (马路开口朝右)
            4: ("road_end", 180),  # 下端连通 (马路开口朝下)
            8: ("road_end", 90),  # 左端连通 (马路开口朝左)

            # === 2. 直道 (双向连通) ===
            5: ("road_straight", 90),  # ║ 竖直直道 (上、下连通)
            10: ("road_straight", 0),  # ═ 水平直道 (左、右连通)

            # === 3. 拐角弯道 (重点修复区域) ===
            # 如果特定的弯道不对，请直接修改下面这四个选项的角度！
            3: ("road_corner", 90),  # ╚ 形弯 (上、右连通)
            9: ("road_corner", 180),  # ╝ 形弯 (上、左连通)
            12: ("road_corner", 270),  # ╗ 形弯 (下、左连通)
            6: ("road_corner", 0),  # ╔ 形弯 (下、右连通)

            # === 4. 丁字路口 (三向连通) ===
            7: ("road_t", 90),  # ╠ 形路口 (上、右、下连通)
            11: ("road_t", 180),  # ╩ 形路口 (上、左、右连通)
            13: ("road_t", 270),  # ╣ 形路口 (上、下、左连通)
            14: ("road_t", 0),  # ╦ 形路口 (左、下、右连通)

            # === 5. 十字路口 (四周都有路) ===
            15: ("road_cross", 0),
        }

        name, angle = mapping.get(mask, ("road_end", 0))
        angle = angle % 360

        if angle == 0:
            return self.assets.get_image(name, TS)
        return self.assets.get_rotated_image(name, TS, angle)

    def _hash_choice(self, row, col, max_val):
        return (row * 31 + col * 17 + row * col * 7) % max_val

    def create_bg(self):
        bg = pygame.Surface((WIDTH, HEIGHT - 100))
        TS = (TILE_SIZE, TILE_SIZE)

        grass_base = self.assets.get_image("grass_0", TS, "box")

        deco_pool = [
            (self.assets.get_image("deco_rock1", (22, 22)), 22, 0.12),
            (self.assets.get_image("deco_rock2", (28, 28)), 28, 0.10),
            (self.assets.get_image("deco_grass1", (18, 28)), 18, 0.10),
            (self.assets.get_image("deco_grass2", (22, 32)), 22, 0.08),
            (self.assets.get_image("deco_crater", (34, 34)), 34, 0.04),
            (self.assets.get_image("deco_debris", (28, 28)), 28, 0.02),
        ]
        deco_total_chance = sum(d[2] for d in deco_pool)

        for row in range(ROWS):
            for col in range(COLS):
                val = self.map_grid[row][col]
                x = col * TILE_SIZE
                y = row * TILE_SIZE

                bg.blit(grass_base, (x, y))

                if val == 1:
                    road_tile = self._get_road_tile(self._get_road_mask(row, col))
                    road_w = road_tile.get_width()
                    road_h = road_tile.get_height()
                    bg.blit(road_tile, (x + (TILE_SIZE - road_w) // 2,
                                        y + (TILE_SIZE - road_h) // 2))

                if val == 0:
                    roll = self._hash_choice(row, col, 1000) / 1000.0
                    if roll < deco_total_chance:
                        cumulative = 0.0
                        for img, size, chance in deco_pool:
                            cumulative += chance
                            if roll < cumulative:
                                half = size // 2
                                off_x = self._hash_choice(row, col, 10) - 5
                                off_y = self._hash_choice(col, row, 10) - 5
                                bg.blit(img, (x + TILE_SIZE // 2 - half + off_x,
                                              y + TILE_SIZE // 2 - half + off_y))
                                break

                grid_surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                pygame.draw.rect(grid_surf, (0, 0, 0, 15), (0, 0, TILE_SIZE, TILE_SIZE), 1)
                bg.blit(grid_surf, (x, y))

        return bg

    def spawn_explosion(self, x, y, color=(255, 100, 50), count=15):
        for _ in range(count):
            self.particles.append(Particle(x, y, color))

    def trigger_orbital_strike(self, pos):
        self.assets.play_sound("boom")
        self.screen_shake = 30
        self.orbital_cooldown = int(self.orbital_cooldown_max * self.run_buffs["orbital_cd_mult"])
        self.targeting_orbital = False

        self.spawn_explosion(pos[0], pos[1], (255, 255, 200), 100)
        self.spawn_explosion(pos[0], pos[1], (255, 100, 50), 50)

        for enemy in self.enemies:
            dist = math.hypot(enemy.rect.centerx - pos[0], enemy.rect.centery - pos[1])
            if dist <= 150:
                was_shielded = enemy.shielded
                enemy.shielded = False
                is_dead = enemy.hit(800)
                self.floating_texts.append(
                    FloatingText(enemy.rect.centerx, enemy.rect.top, "-800", (255, 255, 0), self.font))
                if is_dead:
                    self.money += enemy.reward
                elif was_shielded:
                    enemy.shielded = True

    def generate_draft_options(self):
        pool = [
            {"title": "ADVANCED AMMO", "desc": "All Towers +20% DMG", "type": "dmg"},
            {"title": "LONG BARREL", "desc": "All Towers +15% Range", "type": "range"},
            {"title": "ECONOMIC BOOM", "desc": "Gain +2000 Funds Now", "type": "money"},
            {"title": "EMERGENCY REPAIR", "desc": "Main Base Heals +30 HP", "type": "heal"},
            {"title": "ORBITAL UPGRADE", "desc": "Orbital Strike CD -15%", "type": "orbital_cd"}
        ]
        self.draft_options = random.sample(pool, 3)

    def apply_draft_buff(self, buff_type):
        self.assets.play_sound("build")
        if buff_type == "dmg":
            # 修复：计算相对增幅比率，防止和防御塔自身的升级乘数产生冲突
            old_mult = self.run_buffs["dmg_mult"]
            self.run_buffs["dmg_mult"] += 0.20
            ratio = self.run_buffs["dmg_mult"] / old_mult
            for t in self.towers:
                t.damage = int(t.damage * ratio)
        elif buff_type == "range":
            old_mult = self.run_buffs["range_mult"]
            self.run_buffs["range_mult"] += 0.15
            ratio = self.run_buffs["range_mult"] / old_mult
            for t in self.towers:
                t.range = int(t.range * ratio)
        elif buff_type == "money":
            self.money += 2000
        elif buff_type == "heal":
            for b in self.bases:
                if b.is_main:
                    b.hp = min(b.max_hp, b.hp + 30)
        elif buff_type == "orbital_cd":
            self.run_buffs["orbital_cd_mult"] *= 0.85

    def handle_click(self, pos, button):
        if self.state in ["VICTORY", "GAME_OVER", "NEW_RECORD"]:
            self.state = "EXIT_VICTORY" if self.state in ["VICTORY", "NEW_RECORD"] else "EXIT_DEFEAT"
            self.assets.play_sound("switch")
            return

        if self.state == "PAUSED":
            if button == 1:
                if pygame.Rect(WIDTH // 2 - 150, HEIGHT // 2, 300, 50).collidepoint(pos):
                    self.state = "PLAYING"
                    self.assets.play_sound("switch")
                elif pygame.Rect(WIDTH // 2 - 150, HEIGHT // 2 + 70, 300, 50).collidepoint(pos):
                    self.state = "EXIT_ABORT"
                    self.assets.play_sound("switch")
            return

        if self.state == "DRAFTING":
            if button == 1:
                start_x, start_y = WIDTH // 2 - 350, HEIGHT // 2 - 150
                for i, option in enumerate(self.draft_options):
                    if pygame.Rect(start_x + i * 250, start_y, 200, 300).collidepoint(pos):
                        self.apply_draft_buff(option["type"])
                        self.start_next_wave(early=False)
                        self.state = "PLAYING"
            return

        if button == 1:
            if self.targeting_orbital and pos[1] <= HEIGHT - 100:
                self.trigger_orbital_strike(pos)
                return

            if pygame.Rect(WIDTH - 120, HEIGHT - 80, 100, 60).collidepoint(pos):
                if self.orbital_cooldown == 0:
                    self.targeting_orbital = not self.targeting_orbital
                    self.assets.play_sound("switch")
                else:
                    self.assets.play_sound("error")
                return

            if pos[1] > HEIGHT - 100:
                if pos[0] < WIDTH - 150:
                    self.selected_tower_index = pos[0] // ((WIDTH - 150) // len(self.tower_classes))
                    self.selected_placed_tower = None
                    self.targeting_orbital = False
                    self.assets.play_sound("switch")
                return

            if pos[1] <= HEIGHT - 100:
                clicked_tower = None
                for t in self.towers:
                    if t.rect.collidepoint(pos):
                        clicked_tower = t
                        break

                if clicked_tower:
                    self.selected_placed_tower = clicked_tower
                    self.assets.play_sound("switch")
                    return
                else:
                    self.selected_placed_tower = None

                if self.selected_tower_index is not None:
                    if len(self.towers) >= self.max_towers:
                        self.assets.play_sound("error")
                        return

                    grid_x, grid_y = pos[0] // TILE_SIZE, pos[1] // TILE_SIZE
                    if grid_y >= ROWS or grid_x >= COLS:
                        return

                    # 修复：路障允许建在马路(1)上，其他塔只能建在草地(0)上
                    grid_val = self.map_grid[grid_y][grid_x]
                    is_barricade = (self.tower_classes[self.selected_tower_index] == Barricade)

                    if (is_barricade and grid_val == 1) or (not is_barricade and grid_val == 0):
                        can_build = True

                        # 修复叠塔BUG：使用网格的中心点，而不是随意的鼠标像素点来测算碰撞
                        cell_center = (grid_x * TILE_SIZE + TILE_SIZE // 2, grid_y * TILE_SIZE + TILE_SIZE // 2)

                        for b in self.bases:
                            if b.rect.collidepoint(cell_center):
                                can_build = False
                        for t in self.towers:
                            if t.rect.collidepoint(cell_center):
                                can_build = False

                        if can_build:
                            temp_tower = self.tower_classes[self.selected_tower_index](grid_x, grid_y, self.assets)
                            if self.money >= temp_tower.price:
                                self.money -= temp_tower.price
                                temp_tower.damage = int(temp_tower.damage * self.run_buffs["dmg_mult"])
                                temp_tower.range = int(temp_tower.range * self.run_buffs["range_mult"])
                                self.towers.add(temp_tower)
                                self.assets.play_sound("build")
                                self.spawn_explosion(pos[0], pos[1], (100, 200, 255), 8)
                            else:
                                self.assets.play_sound("error")

        elif button == 3:
            self.selected_placed_tower = None
            self.selected_tower_index = None
            self.targeting_orbital = False

    def handle_keydown(self, key):
        if self.state == "DRAFTING": return

        # 修复：暂停状态下除了 ESC，屏蔽所有快捷键（防止暂停时升级/卖塔）
        if self.state == "PAUSED" and key != pygame.K_ESCAPE:
            return

        if key == pygame.K_1:
            self.selected_tower_index = 0
        elif key == pygame.K_2:
            self.selected_tower_index = 1
        elif key == pygame.K_3:
            self.selected_tower_index = 2
        elif key == pygame.K_4:
            self.selected_tower_index = 3
        elif key == pygame.K_ESCAPE:
            if self.state == "PLAYING":
                self.state = "PAUSED"
            elif self.state == "PAUSED":
                self.state = "PLAYING"
            self.assets.play_sound("switch")
            self.targeting_orbital = False
            self.selected_placed_tower = None
            self.selected_tower_index = None

        # --- 新增：提前呼叫波次 ---
        elif key == pygame.K_RETURN:
            if self.enemies_to_spawn == 0 and len(self.enemies) == 0 and self.wave_delay_timer > 0:
                self.start_next_wave(early=True)

        if self.selected_placed_tower:
            if key == pygame.K_u:
                if self.money >= self.selected_placed_tower.upgrade_cost:
                    self.money -= self.selected_placed_tower.upgrade_cost
                    if self.selected_placed_tower.upgrade():
                        self.spawn_explosion(self.selected_placed_tower.rect.centerx,
                                             self.selected_placed_tower.rect.centery, (100, 255, 100), 15)
                else:
                    self.assets.play_sound("error")
            elif key == pygame.K_s:
                self.money += self.selected_placed_tower.price // 2
                self.spawn_explosion(self.selected_placed_tower.rect.centerx, self.selected_placed_tower.rect.centery,
                                     (200, 200, 200), 10)
                self.selected_placed_tower.kill()
                self.selected_placed_tower = None
                self.assets.play_sound("switch")
            # --- 新增：按下 T 键切换索敌目标 ---
            elif key == pygame.K_t:
                if hasattr(self.selected_placed_tower, 'cycle_target_mode'):
                    self.selected_placed_tower.cycle_target_mode()
                    self.assets.play_sound("switch")

    def start_next_wave(self, early=False):
        if early and self.wave_delay_timer < self.wave_delay_max:
            bonus = max(0, int((self.wave_delay_max - self.wave_delay_timer) * 0.1))
            self.money += bonus
            self.floating_texts.append(
                FloatingText(WIDTH // 2, 120, f"EARLY CALL: +${bonus}", (255, 215, 0), self.large_font))

        self.wave += 1
        self.enemies_to_spawn = 5 + int(self.wave * 2) if not self.is_endless else 10 + int(self.wave * 3)
        self.money += 100 + int(self.wave * 10)
        self.wave_delay_timer = 0
        self.assets.play_sound("switch")

    def update(self):
        if self.state != "PLAYING": return

        if self.orbital_cooldown > 0: self.orbital_cooldown -= 1
        if self.screen_shake > 0: self.screen_shake -= 1

        if self.enemies_to_spawn > 0:
            self.spawn_timer += 1
            if self.spawn_timer >= max(30, 60 - int(self.wave * 1.5)):
                pool = [ScoutBuggy]
                if self.level_id >= 2: pool.append(KamikazeJeep)
                if self.level_id >= 3: pool.append(SiegeMech)
                if self.level_id >= 4: pool.append(SwarmDrone)
                if self.level_id >= 5: pool.append(ShieldGenerator)

                if (self.is_endless and self.wave % 5 == 0 and random.random() < 0.2) or (
                        not self.is_endless and self.wave == 5 and self.enemies_to_spawn == 1 and self.level_id >= 4):
                    EnemyClass = BossTitan
                else:
                    EnemyClass = random.choice(pool)

                dynamic_diff = self.difficulty * (1 + self.wave * 0.15) if self.is_endless else self.difficulty
                self.enemies.add(EnemyClass(random.choice(self.paths), dynamic_diff, self.wave, self.assets))
                self.enemies_to_spawn -= 1
                self.spawn_timer = 0

        elif len(self.enemies) == 0:
            # --- 新增：倒计时与空档期逻辑 ---
            if not self.is_endless and self.wave >= 5:
                self.state = "VICTORY"
                if not self.end_sound_played:
                    self.assets.play_sound("win")
                    self.end_sound_played = True
                return

            if self.is_endless and self.wave % 5 == 0 and self.state != "DRAFTING":
                self.state = "DRAFTING"
                self.generate_draft_options()
                return

            self.wave_delay_timer += 1
            if self.wave_delay_timer >= self.wave_delay_max:
                self.start_next_wave(early=False)

        for e in self.enemies: e.shielded = False
        for e in self.enemies:
            if isinstance(e, ShieldGenerator):
                for other in self.enemies:
                    # 修复：增加 not isinstance(other, ShieldGenerator) 判定，禁止互相套盾
                    if other != e and not isinstance(other, ShieldGenerator) and math.hypot(
                            e.rect.centerx - other.rect.centerx,
                            e.rect.centery - other.rect.centery) <= e.shield_range:
                        other.shielded = True

        for enemy in self.enemies.sprites(): enemy.move_and_combat(self.bases, self.towers)
        for tower in self.towers.sprites(): tower.attack(self.enemies, self.bullets)

        for bullet in self.bullets.sprites():
            bullet.update()
            if bullet.target and pygame.sprite.collide_rect(bullet, bullet.target):
                if bullet.target.shielded:
                    self.spawn_explosion(bullet.rect.centerx, bullet.rect.centery, (100, 200, 255), 3)
                    self.floating_texts.append(
                        FloatingText(bullet.target.rect.centerx, bullet.target.rect.top, "BLOCKED", (100, 200, 255),
                                     self.font_small))
                    self.assets.play_sound("hit")
                else:
                    is_dead = bullet.target.hit(bullet.damage)
                    self.spawn_explosion(bullet.rect.centerx, bullet.rect.centery, (255, 200, 50), 3)

                    is_crit = bullet.damage >= 40
                    color = (255, 50, 50) if not is_crit else (255, 150, 50)
                    font_to_use = self.font if is_crit else self.font_small
                    prefix = "CRIT " if is_crit else "-"
                    self.floating_texts.append(
                        FloatingText(bullet.target.rect.centerx, bullet.target.rect.top, f"{prefix}{bullet.damage}",
                                     color, font_to_use))

                    self.assets.play_sound("hit")
                    if is_dead:
                        self.money += bullet.target.reward
                        self.assets.play_sound("boom")
                        self.spawn_explosion(bullet.target.rect.centerx, bullet.target.rect.centery, (255, 100, 50), 20)
                bullet.kill()

        for p in self.particles[:]:
            p.update()
            if p.lifetime <= 0: self.particles.remove(p)

        for ft in self.floating_texts[:]:
            ft.update()
            if ft.lifetime <= 0: self.floating_texts.remove(ft)

        main_base_alive = False
        for base in self.bases:
            if base.is_main:
                main_base_alive = True
            elif base.hp <= 0:
                self.spawn_explosion(base.rect.centerx, base.rect.centery, (255, 50, 50), 30)
                self.assets.play_sound("boom")

        if not main_base_alive:
            if self.is_endless and self.wave > PLAYER_DATA.get("highest_endless_wave", 0):
                PLAYER_DATA["highest_endless_wave"] = self.wave
                save_game_data()
                self.state = "NEW_RECORD"
                if not self.end_sound_played:
                    self.assets.play_sound("win")
                    self.end_sound_played = True
            else:
                self.state = "GAME_OVER"
                if not self.end_sound_played:
                    self.assets.play_sound("lose")
                    self.end_sound_played = True

    def draw_selected_ui(self):
        if not self.selected_placed_tower: return
        t = self.selected_placed_tower
        range_surf = pygame.Surface((t.range * 2, t.range * 2), pygame.SRCALPHA)
        pygame.draw.circle(range_surf, (200, 255, 200, 60), (t.range, t.range), t.range)
        self.screen.blit(range_surf, (t.rect.centerx - t.range, t.rect.centery - t.range))
        pygame.draw.rect(self.screen, (255, 255, 0), t.rect, 2)

        # 面板拉高一点适应索敌UI
        box_w, box_h = 160, 100
        tx, ty = t.rect.right + 10, t.rect.y
        if tx + box_w > WIDTH: tx = t.rect.left - box_w - 10
        if ty + box_h > HEIGHT - 100: ty = HEIGHT - 100 - box_h

        pygame.draw.rect(self.screen, (20, 25, 30, 240), (tx, ty, box_w, box_h), border_radius=5)
        pygame.draw.rect(self.screen, (255, 215, 0), (tx, ty, box_w, box_h), 2, border_radius=5)

        self.screen.blit(self.font.render(f"LEVEL {t.level}/{t.max_level}", True, (255, 255, 255)), (tx + 10, ty + 10))
        if t.level < t.max_level:
            upg_txt = self.font_small.render(f"[U] Upgrade: ${t.upgrade_cost}", True,
                                             (100, 255, 100) if self.money >= t.upgrade_cost else (150, 150, 150))
            self.screen.blit(upg_txt, (tx + 10, ty + 35))
        else:
            self.screen.blit(self.font_small.render("MAX LEVEL", True, (255, 215, 0)), (tx + 10, ty + 35))

        self.screen.blit(self.font_small.render(f"[S] Sell: +${t.price // 2}", True, (255, 100, 100)),
                         (tx + 10, ty + 55))

        # --- 新增：显示当前的开火逻辑 ---
        if hasattr(t, 'target_mode'):
            self.screen.blit(self.font_small.render(f"[T] Target: {t.target_mode}", True, (100, 200, 255)),
                             (tx + 10, ty + 75))

    def draw_tooltip(self, pos, tower):
        box_w, box_h = 280, 110
        tx, ty = pos[0] + 15, pos[1] - box_h - 15
        if tx + box_w > WIDTH: tx = WIDTH - box_w - 10
        if ty < 0: ty = 10

        surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (20, 25, 30, 230), (0, 0, box_w, box_h), border_radius=8)
        pygame.draw.rect(surf, (100, 150, 200, 255), (0, 0, box_w, box_h), 2, border_radius=8)
        self.screen.blit(surf, (tx, ty))

        self.screen.blit(self.font.render(f"[{tower.name}]", True, (255, 215, 0)), (tx + 15, ty + 10))
        self.screen.blit(self.font.render(f"Cost: ${tower.price}   HP: {tower.max_hp}", True, (200, 255, 200)),
                         (tx + 15, ty + 35))
        self.screen.blit(self.font.render(f"DMG: {tower.damage}   RNG: {tower.range}", True, (255, 150, 150)),
                         (tx + 15, ty + 60))
        self.screen.blit(self.font.render(tower.desc, True, (180, 180, 180)), (tx + 15, ty + 85))

    def draw_overlay(self, title, color, subtitle=""):
        s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        s.fill((0, 0, 0, 180))
        self.screen.blit(s, (0, 0))
        txt_surf = self.large_font.render(title, True, color)
        self.screen.blit(txt_surf, (WIDTH // 2 - txt_surf.get_width() // 2, HEIGHT // 2 - 40))
        if subtitle:
            sub_surf = self.font.render(subtitle, True, (200, 200, 200))
            self.screen.blit(sub_surf, (WIDTH // 2 - sub_surf.get_width() // 2, HEIGHT // 2 + 20))

    def draw(self):
        offset_x = random.randint(-5, 5) if self.screen_shake > 0 else 0
        offset_y = random.randint(-5, 5) if self.screen_shake > 0 else 0
        self.screen.blit(self.bg_image, (offset_x, offset_y))
        m_pos = pygame.mouse.get_pos()
        hover_tower_class = None

        if self.state in ["PLAYING", "PAUSED", "DRAFTING"]:
            for tower in self.towers:
                if tower.rect.collidepoint(m_pos):
                    range_surf = pygame.Surface((tower.range * 2, tower.range * 2), pygame.SRCALPHA)
                    pygame.draw.circle(range_surf, COLOR_RANGE, (tower.range, tower.range), tower.range)
                    self.screen.blit(range_surf, (tower.rect.centerx - tower.range, tower.rect.centery - tower.range))

        for group in [self.bases, self.towers, self.enemies]:
            for entity in group:
                shadow = pygame.Surface((entity.rect.width, entity.rect.height), pygame.SRCALPHA)
                pygame.draw.ellipse(shadow, (0, 0, 0, 80),
                                    (5, entity.rect.height * 0.6, entity.rect.width - 10, entity.rect.height * 0.3))
                offset_y_shadow = 25 if getattr(entity, 'enemy_type', 'ground') == 'flyer' else 5
                self.screen.blit(shadow, (entity.rect.x + offset_x, entity.rect.y + offset_y_shadow + offset_y))

        # --- 动态建造预览层 ---
        if self.selected_tower_index is not None and not self.targeting_orbital and m_pos[1] <= HEIGHT - 100:
            grid_x, grid_y = m_pos[0] // TILE_SIZE, m_pos[1] // TILE_SIZE
            if grid_x < COLS and grid_y < ROWS:
                # 修复预览逻辑：判定条件与真实建造保持一致
                grid_val = self.map_grid[grid_y][grid_x]
                is_barricade = (self.tower_classes[self.selected_tower_index] == Barricade)
                valid_build = (is_barricade and grid_val == 1) or (not is_barricade and grid_val == 0)

                cell_center = (grid_x * TILE_SIZE + 25, grid_y * TILE_SIZE + 25)
                for b in self.bases:
                    if b.rect.collidepoint(cell_center): valid_build = False
                for t in self.towers:
                    if t.rect.collidepoint(cell_center): valid_build = False

                temp_t = self.tower_classes[self.selected_tower_index](grid_x, grid_y, self.assets)
                temp_t.range = int(temp_t.range * self.run_buffs["range_mult"])

                # 渲染预览圈
                p_color = (0, 255, 0, 80) if valid_build else (255, 0, 0, 80)
                p_surf = pygame.Surface((temp_t.range * 2, temp_t.range * 2), pygame.SRCALPHA)
                pygame.draw.circle(p_surf, p_color, (temp_t.range, temp_t.range), temp_t.range)
                self.screen.blit(p_surf, (temp_t.rect.centerx - temp_t.range + offset_x,
                                          temp_t.rect.centery - temp_t.range + offset_y))

                # 渲染半透明塔身
                temp_t.base_image.set_alpha(150)
                self.screen.blit(temp_t.base_image, (temp_t.rect.x + offset_x, temp_t.rect.y + offset_y))
                if temp_t.gun_image:
                    temp_t.gun_image.set_alpha(150)
                    gun_r = temp_t.gun_image.get_rect(center=temp_t.rect.center)
                    self.screen.blit(temp_t.gun_image, (gun_r.x + offset_x, gun_r.y + offset_y))

        for bullet in self.bullets:
            if hasattr(bullet, 'trail'):
                for i, pos in enumerate(bullet.trail):
                    radius = max(1, int(4 * (i / len(bullet.trail))))
                    alpha = int(200 * (i / len(bullet.trail)))
                    s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                    pygame.draw.circle(s, (255, 150, 50, alpha), (radius, radius), radius)
                    self.screen.blit(s, (pos[0] - radius + offset_x, pos[1] - radius + offset_y))

        for tower in self.towers: tower.draw(self.screen)
        for tower in self.towers:
            if tower.hp < tower.max_hp:
                ratio = max(0, tower.hp / tower.max_hp)
                pygame.draw.rect(self.screen, (100, 0, 0),
                                 (tower.rect.x + offset_x, tower.rect.y - 8 + offset_y, 40, 4))
                pygame.draw.rect(self.screen, (0, 255, 0),
                                 (tower.rect.x + offset_x, tower.rect.y - 8 + offset_y, 40 * ratio, 4))

        self.bases.draw(self.screen)
        for base in self.bases: base.draw_hp(self.screen)
        self.enemies.draw(self.screen)
        for enemy in self.enemies: enemy.draw_hp(self.screen)
        self.bullets.draw(self.screen)
        for p in self.particles: p.draw(self.screen)

        for ft in self.floating_texts:
            ft.draw(self.screen)

        if self.targeting_orbital and m_pos[1] <= HEIGHT - 100:
            target_surf = pygame.Surface((300, 300), pygame.SRCALPHA)
            pygame.draw.circle(target_surf, (255, 50, 50, 60), (150, 150), 150)
            pygame.draw.circle(target_surf, (255, 50, 50, 200), (150, 150), 150, 2)
            pygame.draw.line(target_surf, (255, 50, 50, 200), (150, 0), (150, 300), 1)
            pygame.draw.line(target_surf, (255, 50, 50, 200), (0, 150), (300, 150), 1)
            self.screen.blit(target_surf, (m_pos[0] - 150, m_pos[1] - 150))

        pygame.draw.rect(self.screen, COLOR_UI_BG, (0, 0, WIDTH, 30))
        wave_str = f"WAVE: {self.wave} (ENDLESS)" if self.is_endless else f"WAVE: {self.wave}/5"
        ui_text = self.font.render(f"FUNDS: ${self.money}  |  {wave_str}", True, COLOR_TEXT)
        limit_text = self.font.render(f"TOWERS: {len(self.towers)}/{self.max_towers}", True,
                                      (255, 50, 50) if len(self.towers) >= self.max_towers else COLOR_TEXT)
        self.screen.blit(ui_text, (10, 5))
        self.screen.blit(limit_text, (300, 5))

        # --- 新增：空档期倒计时与提前呼叫提示 ---
        if self.state == "PLAYING" and len(
                self.enemies) == 0 and self.enemies_to_spawn == 0 and self.wave_delay_timer > 0:
            rem_sec = (self.wave_delay_max - self.wave_delay_timer) // 60
            time_txt = self.font.render(f"NEXT WAVE IN: {rem_sec}s", True, (255, 215, 0))
            call_txt = self.font_small.render("[ENTER] CALL EARLY FOR BONUS", True, (150, 255, 150))
            self.screen.blit(time_txt, (WIDTH // 2 - time_txt.get_width() // 2, HEIGHT // 2 - 60))
            self.screen.blit(call_txt, (WIDTH // 2 - call_txt.get_width() // 2, HEIGHT // 2 - 30))

        ui_panel_rect = pygame.Rect(0, HEIGHT - 100, WIDTH, 100)
        pygame.draw.rect(self.screen, (30, 35, 40), ui_panel_rect)
        pygame.draw.rect(self.screen, (100, 100, 100), ui_panel_rect, 2)

        panel_width = (WIDTH - 150) // len(self.tower_classes)
        for i, t_class in enumerate(self.tower_classes):
            temp = t_class(0, 0, self.assets)
            rect = pygame.Rect(i * panel_width, HEIGHT - 100, panel_width, 100)

            if rect.collidepoint(m_pos) and not self.targeting_orbital:
                pygame.draw.rect(self.screen, (80, 100, 120), rect)
                hover_tower_class = temp
            elif i == self.selected_tower_index and not self.targeting_orbital:
                pygame.draw.rect(self.screen, (60, 80, 100), rect)

            color = (255, 100, 100) if self.money < temp.price else COLOR_TEXT
            self.screen.blit(self.font.render(f"[{i + 1}] {temp.name}", True, color), (rect.x + 10, rect.y + 15))
            self.screen.blit(self.font.render(f"Cost: ${temp.price}", True, (200, 200, 50)), (rect.x + 10, rect.y + 45))
            pygame.draw.rect(self.screen, (100, 100, 100), rect, 1)

        btn_strike = pygame.Rect(WIDTH - 120, HEIGHT - 80, 100, 60)
        strike_color = (150, 50, 50) if self.orbital_cooldown == 0 else (60, 60, 60)
        if self.targeting_orbital: strike_color = (255, 100, 100)
        pygame.draw.rect(self.screen, strike_color, btn_strike, border_radius=5)
        pygame.draw.rect(self.screen, (200, 200, 200), btn_strike, 2, border_radius=5)

        strike_txt = self.font.render("ORBITAL", True, (255, 255, 255))
        self.screen.blit(strike_txt, (btn_strike.centerx - strike_txt.get_width() // 2, btn_strike.y + 10))

        if self.orbital_cooldown > 0:
            cd_txt = self.font.render(f"{self.orbital_cooldown // 60}s", True, (200, 200, 200))
            self.screen.blit(cd_txt, (btn_strike.centerx - cd_txt.get_width() // 2, btn_strike.y + 35))
        else:
            rdy_txt = self.font.render("READY", True, (100, 255, 100))
            self.screen.blit(rdy_txt, (btn_strike.centerx - rdy_txt.get_width() // 2, btn_strike.y + 35))

        self.draw_selected_ui()

        if self.state == "DRAFTING":
            s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            s.fill((0, 0, 0, 200))
            self.screen.blit(s, (0, 0))

            title = self.large_font.render("TACTICAL SUPPLY DROP", True, (255, 215, 0))
            self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 100))
            self.screen.blit(self.font.render("CHOOSE ONE UPGRADE TO PROCEED", True, (200, 200, 200)),
                             (WIDTH // 2 - 130, 160))

            card_w, card_h = 200, 300
            spacing = 50
            start_x = WIDTH // 2 - (3 * card_w + 2 * spacing) // 2
            start_y = HEIGHT // 2 - card_h // 2

            for i, option in enumerate(self.draft_options):
                rect = pygame.Rect(start_x + i * (card_w + spacing), start_y, card_w, card_h)
                pygame.draw.rect(self.screen, (60, 80, 100) if rect.collidepoint(m_pos) else (40, 50, 60), rect,
                                 border_radius=10)
                pygame.draw.rect(self.screen, (100, 200, 255), rect, 3, border_radius=10)

                c_title = self.font.render(option["title"], True, (255, 255, 255))
                c_desc = self.font_small.render(option["desc"], True, (150, 255, 150))

                self.screen.blit(c_title, (rect.centerx - c_title.get_width() // 2, rect.y + 40))
                pygame.draw.line(self.screen, (100, 200, 255), (rect.x + 20, rect.y + 80),
                                 (rect.right - 20, rect.y + 80), 2)
                self.screen.blit(c_desc, (rect.centerx - c_desc.get_width() // 2, rect.y + 150))

        elif self.state == "PAUSED":
            s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            s.fill((0, 0, 0, 200))
            self.screen.blit(s, (0, 0))

            title = self.large_font.render("TACTICAL PAUSE", True, (100, 200, 255))
            self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 120))

            btn_resume = pygame.Rect(WIDTH // 2 - 150, HEIGHT // 2, 300, 50)
            btn_abort = pygame.Rect(WIDTH // 2 - 150, HEIGHT // 2 + 70, 300, 50)

            pygame.draw.rect(self.screen, (50, 150, 50) if btn_resume.collidepoint(m_pos) else (40, 100, 40),
                             btn_resume, border_radius=5)
            pygame.draw.rect(self.screen, (200, 255, 200), btn_resume, 2, border_radius=5)
            self.screen.blit(self.font.render("RESUME OPERATION", True, (255, 255, 255)),
                             (btn_resume.centerx - 70, btn_resume.centery - 8))

            pygame.draw.rect(self.screen, (150, 50, 50) if btn_abort.collidepoint(m_pos) else (100, 40, 40), btn_abort,
                             border_radius=5)
            pygame.draw.rect(self.screen, (255, 200, 200), btn_abort, 2, border_radius=5)
            self.screen.blit(self.font.render("ABORT & RETURN TO MENU", True, (255, 255, 255)),
                             (btn_abort.centerx - 100, btn_abort.centery - 8))

        elif self.state == "GAME_OVER":
            self.draw_overlay("BASE DESTROYED", (255, 50, 50), f"SURVIVED TO WAVE {self.wave}. CLICK TO RETURN")
        elif self.state == "VICTORY":
            self.draw_overlay("OPERATION SUCCESS", (50, 255, 50), "CLICK TO CONTINUE")
        elif self.state == "NEW_RECORD":
            self.draw_overlay("NEW SURVIVAL RECORD!", (255, 215, 0), f"YOU REACHED WAVE {self.wave}! CLICK TO RETURN")

        if hover_tower_class and self.state in ["PLAYING", "PAUSED", "DRAFTING"] and self.selected_tower_index is None:
            self.draw_tooltip(m_pos, hover_tower_class)