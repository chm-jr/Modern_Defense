# entities/tower.py
import pygame
import math
from utils.settings import TILE_SIZE, PLAYER_DATA


class Bullet(pygame.sprite.Sprite):
    def __init__(self, start_pos, target, damage, assets):
        super().__init__()
        self.original_image = assets.get_image("missile", (15, 6), "missile")
        self.image = self.original_image
        self.rect = self.image.get_rect(center=start_pos)
        self.target = target
        self.speed = 12
        self.damage = damage
        self.trail = []

    def update(self):
        if not self.target.alive():
            self.kill()
            return

        dx, dy = self.target.rect.centerx - self.rect.centerx, self.target.rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)
        angle = math.degrees(math.atan2(-dy, dx))
        self.image = pygame.transform.rotate(self.original_image, angle)
        self.rect = self.image.get_rect(center=self.rect.center)

        self.trail.append(self.rect.center)
        if len(self.trail) > 8:
            self.trail.pop(0)

        if dist > self.speed:
            self.rect.x += (dx / dist) * self.speed
            self.rect.y += (dy / dist) * self.speed


class BaseTower(pygame.sprite.Sprite):
    def __init__(self, grid_x, grid_y, assets):
        super().__init__()
        self.assets = assets
        self.base_image = assets.get_image("tower_base", (40, 40), "tower_base").copy()
        self.gun_original = None
        self.gun_image = None

        pixel_x = grid_x * TILE_SIZE + TILE_SIZE // 2
        pixel_y = grid_y * TILE_SIZE + TILE_SIZE // 2
        self.rect = self.base_image.get_rect(center=(pixel_x, pixel_y))

        self.range = 100
        self.damage = 10
        self.cooldown_max = 30
        self.cooldown = 0
        self.price = 100
        self.name = "Base"
        self.desc = "Standard base defense tower."

        self.max_hp = 100
        self.hp = 100

        self.level = 1
        self.max_level = 3
        self.upgrade_cost = int(self.price * 1.5)

        # --- 新增：开火目标优先级 ---
        self.target_mode = "FIRST"

    def apply_tech_upgrades(self):
        dmg_level = PLAYER_DATA["upgrades"]["dmg_boost"]
        cost_level = PLAYER_DATA["upgrades"]["cost_down"]
        self.damage = int(self.damage * (1 + 0.20 * dmg_level))
        cost_multiplier = max(0.3, 1 - 0.10 * cost_level)
        self.price = int(self.price * cost_multiplier)
        self.upgrade_cost = int(self.price * 1.5)

        self.max_hp += 10 * PLAYER_DATA["upgrades"]["base_armor"]
        self.hp = self.max_hp

    def upgrade(self):
        if self.level < self.max_level:
            self.level += 1
            self.damage = int(self.damage * 1.4)
            self.range = int(self.range * 1.15)
            self.max_hp = int(self.max_hp * 1.5)
            self.hp = self.max_hp
            self.upgrade_cost = int(self.upgrade_cost * 1.5)
            self.assets.play_sound("build")
            return True
        return False

    def cycle_target_mode(self):
        """切换目标优先级"""
        modes = ["FIRST", "STRONG", "CLOSE"]
        idx = modes.index(self.target_mode)
        self.target_mode = modes[(idx + 1) % len(modes)]

    def hit(self, damage):
        self.hp -= damage
        if self.hp <= 0:
            self.kill()
            return True
        return False

    def attack(self, enemies, bullets_group):
        if self.cooldown > 0:
            self.cooldown -= 1

        target = None
        best_val = None

        for enemy in enemies:
            dist = math.hypot(enemy.rect.centerx - self.rect.centerx, enemy.rect.centery - self.rect.centery)
            if dist <= self.range:
                # 修复：引入距离下一节点的计算，精确判断谁走在最前面
                if self.target_mode == "FIRST":
                    if enemy.path_index + 1 < len(enemy.path):
                        target_node = enemy.path[enemy.path_index + 1]
                        dist_to_next = math.hypot(enemy.rect.centerx - target_node[0],
                                                  enemy.rect.centery - target_node[1])
                        val = enemy.path_index * 1000 - dist_to_next
                    else:
                        val = enemy.path_index * 1000

                    if best_val is None or val > best_val:
                        best_val = val
                        target = enemy
                elif self.target_mode == "STRONG":
                    val = enemy.hp
                    if best_val is None or val > best_val:
                        best_val = val
                        target = enemy
                elif self.target_mode == "CLOSE":
                    val = dist
                    if best_val is None or val < best_val:
                        best_val = val
                        target = enemy

        if target:
            dx = target.rect.centerx - self.rect.centerx
            dy = target.rect.centery - self.rect.centery
            angle = math.degrees(math.atan2(-dy, dx))

            if self.gun_original:
                self.gun_image = pygame.transform.rotate(self.gun_original, angle)

            if self.cooldown == 0:
                bullets_group.add(Bullet(self.rect.center, target, self.damage, self.assets))
                self.cooldown = self.cooldown_max
                self.assets.play_sound("shoot")
        else:
            if self.gun_original:
                self.gun_image = self.gun_original

    def draw(self, surface):
        surface.blit(self.base_image, self.rect)
        if self.gun_image:
            gun_rect = self.gun_image.get_rect(center=self.rect.center)
            surface.blit(self.gun_image, gun_rect)

        star_color = (255, 215, 0)
        start_x = self.rect.centerx - (self.level * 6) // 2
        for i in range(self.level):
            pygame.draw.circle(surface, star_color, (start_x + i * 6, self.rect.y - 4), 2)


class MachineGunTower(BaseTower):
    def __init__(self, grid_x, grid_y, assets):
        super().__init__(grid_x, grid_y, assets)
        self.gun_original = assets.get_image("gun_mg", (40, 40), "gun_mg").copy()
        self.gun_image = self.gun_original
        self.range = 120
        self.damage = 6
        self.cooldown_max = 10
        self.price = 100
        self.name = "MG Nest"
        self.desc = "Fast fire rate. Good against swarms."
        self.apply_tech_upgrades()


class SniperTower(BaseTower):
    def __init__(self, grid_x, grid_y, assets):
        super().__init__(grid_x, grid_y, assets)
        self.gun_original = assets.get_image("gun_sniper", (50, 50), "gun_sniper").copy()
        self.gun_image = self.gun_original
        self.range = 250
        self.damage = 40
        self.cooldown_max = 60
        self.price = 150
        self.name = "Sniper"
        self.desc = "Extreme range & damage. Slow fire rate."
        self.apply_tech_upgrades()


class Barricade(BaseTower):
    def __init__(self, grid_x, grid_y, assets):
        super().__init__(grid_x, grid_y, assets)
        self.base_image = assets.get_image("barricade_base", (40, 40), "box").copy()
        self.gun_original = None
        self.gun_image = None
        self.range = 0
        self.damage = 0
        self.price = 50
        self.name = "Barricade"
        self.desc = "Decoy. Draws enemy fire. High HP."
        self.max_hp = 400
        self.hp = self.max_hp
        self.apply_tech_upgrades()

    def attack(self, enemies, bullets_group):
        pass


class LaserTower(BaseTower):
    def __init__(self, grid_x, grid_y, assets):
        super().__init__(grid_x, grid_y, assets)
        self.gun_original = assets.get_image("gun_laser", (30, 30), "box").copy()
        self.gun_image = self.gun_original
        self.range = 150
        self.damage = 2
        self.cooldown_max = 2
        self.price = 250
        self.name = "Laser"
        self.desc = "Continuous beam. Instantly melts armor."
        self.laser_target = None
        self.sound_timer = 0
        self.apply_tech_upgrades()

    def attack(self, enemies, bullets_group):
        if self.cooldown > 0:
            self.cooldown -= 1
        if self.sound_timer > 0:
            self.sound_timer -= 1

        self.laser_target = None
        target = None
        best_val = None

        for enemy in enemies:
            dist = math.hypot(enemy.rect.centerx - self.rect.centerx, enemy.rect.centery - self.rect.centery)
            if dist <= self.range:
                # 修复：引入距离下一节点的计算，精确判断谁走在最前面
                if self.target_mode == "FIRST":
                    if enemy.path_index + 1 < len(enemy.path):
                        target_node = enemy.path[enemy.path_index + 1]
                        dist_to_next = math.hypot(enemy.rect.centerx - target_node[0],
                                                  enemy.rect.centery - target_node[1])
                        val = enemy.path_index * 1000 - dist_to_next
                    else:
                        val = enemy.path_index * 1000

                    if best_val is None or val > best_val:
                        best_val = val
                        target = enemy
                elif self.target_mode == "STRONG":
                    val = enemy.hp
                    if best_val is None or val > best_val:
                        best_val = val
                        target = enemy
                elif self.target_mode == "CLOSE":
                    val = dist
                    if best_val is None or val < best_val:
                        best_val = val
                        target = enemy

        if target:
            dx = target.rect.centerx - self.rect.centerx
            dy = target.rect.centery - self.rect.centery
            angle = math.degrees(math.atan2(-dy, dx))
            self.gun_image = pygame.transform.rotate(self.gun_original, angle)

            if self.cooldown == 0:
                target.hit(self.damage)
                self.laser_target = target
                self.cooldown = self.cooldown_max
                if self.sound_timer == 0:
                    self.assets.play_sound("laser")
                    self.sound_timer = 15
        else:
            if self.gun_original:
                self.gun_image = self.gun_original

    def draw(self, surface):
        super().draw(surface)
        if self.laser_target and self.laser_target.alive():
            pygame.draw.line(surface, (255, 50, 50), self.rect.center, self.laser_target.rect.center, 3)
            pygame.draw.line(surface, (255, 200, 200), self.rect.center, self.laser_target.rect.center, 1)


class DefenseBase(pygame.sprite.Sprite):
    def __init__(self, grid_x, grid_y, is_main, assets):
        super().__init__()
        self.is_main = is_main
        size = (50, 50) if is_main else (40, 40)
        img_name = "main_base" if is_main else "small_base"
        self.image = assets.get_image(img_name, size, img_name)

        pixel_x = grid_x * TILE_SIZE + TILE_SIZE // 2
        pixel_y = grid_y * TILE_SIZE + TILE_SIZE // 2
        self.rect = self.image.get_rect(center=(pixel_x, pixel_y))

        base_bonus = 10 * PLAYER_DATA["upgrades"]["base_armor"]
        self.max_hp = 50 + base_bonus if is_main else 20
        self.hp = self.max_hp

    def hit(self, damage):
        self.hp -= damage
        if self.hp <= 0:
            self.kill()
            return True
        return False

    def draw_hp(self, surface):
        bar_w = self.rect.width
        ratio = max(0, self.hp / self.max_hp)
        pygame.draw.rect(surface, (100, 0, 0), (self.rect.x, self.rect.y - 12, bar_w, 5))
        pygame.draw.rect(surface, (0, 255, 0), (self.rect.x, self.rect.y - 12, bar_w * ratio, 5))