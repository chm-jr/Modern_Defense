# entities/enemy.py
import pygame
import math


class BaseEnemy(pygame.sprite.Sprite):
    # --- 核心：将 assets 传入基础敌人，让它们有权限播放声音 ---
    def __init__(self, path, difficulty, wave, assets):
        super().__init__()
        self.assets = assets
        self.path = path
        self.path_index = 0
        self.difficulty = difficulty
        self.image = None
        self.original_image = None
        self.rect = None

        self.max_hp = 10
        self.hp = 10
        self.base_speed = 1.0
        self.speed = 1.0
        self.reward = 10
        self.speed_modifier = 1.0

        self.aggro_range = 60
        self.attack_damage = 5
        self.attack_cd = 30
        self.current_cd = 0
        self.enemy_type = "melee"

        self.shielded = False

    def setup_entity(self, image):
        self.original_image = image
        self.image = self.original_image
        self.rect = self.image.get_rect(center=self.path[0])

    def move_and_combat(self, bases_group, towers_group):
        self.speed = self.base_speed * self.speed_modifier
        self.speed_modifier = 1.0
        if self.current_cd > 0: self.current_cd -= 1

        closest_target = None
        closest_dist = self.aggro_range

        if self.enemy_type != "flyer":
            for t in towers_group:
                dist = math.hypot(t.rect.centerx - self.rect.centerx, t.rect.centery - self.rect.centery)
                if dist < closest_dist:
                    closest_dist = dist;
                    closest_target = t
        for b in bases_group:
            dist = math.hypot(b.rect.centerx - self.rect.centerx, b.rect.centery - self.rect.centery)
            if dist < closest_dist:
                closest_dist = dist;
                closest_target = b

        if closest_target:
            if self.enemy_type == "kamikaze":
                closest_target.hit(self.attack_damage)
                # --- 新增：自爆卡车攻击音效 ---
                self.assets.play_sound("boom")
                self.kill()
                return True
            elif self.enemy_type in ["melee", "ranged", "flyer"]:
                angle = math.degrees(math.atan2(-(closest_target.rect.centery - self.rect.centery),
                                                closest_target.rect.centerx - self.rect.centerx))
                self.image = pygame.transform.rotate(self.original_image, angle)
                if self.current_cd == 0:
                    closest_target.hit(self.attack_damage)
                    # --- 新增：远程机甲开火，近战撞击 ---
                    if self.enemy_type == "ranged":
                        self.assets.play_sound("shoot")
                    else:
                        self.assets.play_sound("hit")
                    self.current_cd = self.attack_cd
                return False

        if self.path_index < len(self.path) - 1:
            target = self.path[self.path_index + 1]
            dx, dy = target[0] - self.rect.centerx, target[1] - self.rect.centery
            dist = math.hypot(dx, dy)

            if dist > self.speed:
                angle = math.degrees(math.atan2(-dy, dx))
                self.image = pygame.transform.rotate(self.original_image, angle)
                self.rect = self.image.get_rect(center=self.rect.center)
                self.rect.x += (dx / dist) * self.speed
                self.rect.y += (dy / dist) * self.speed
            else:
                self.rect.center = target
                for base in bases_group:
                    if base.rect.collidepoint(target):
                        base.hit(self.attack_damage * 2)
                        # --- 新增：漏网之鱼撞击基地爆炸音效 ---
                        self.assets.play_sound("boom")
                        self.kill()
                        return True
                self.path_index += 1
            return False
        else:
            self.kill()
            return True

    def hit(self, damage):
        if self.shielded:
            return False

        self.hp -= damage
        if self.hp <= 0:
            self.kill()
            return True
        return False

    def draw_hp(self, surface):
        if self.shielded:
            pygame.draw.circle(surface, (100, 200, 255), self.rect.center, 22, 2)

        bar_w = 30
        ratio = max(0, self.hp / self.max_hp)
        pygame.draw.rect(surface, (100, 0, 0), (self.rect.centerx - 15, self.rect.y - 10, bar_w, 4))
        pygame.draw.rect(surface, (0, 200, 50), (self.rect.centerx - 15, self.rect.y - 10, bar_w * ratio, 4))


class ScoutBuggy(BaseEnemy):
    def __init__(self, path, difficulty, wave, assets):
        super().__init__(path, difficulty, wave, assets)
        img = assets.get_image("buggy", (25, 15), "buggy")
        self.setup_entity(img)
        self.max_hp = int(15 * difficulty * (1 + wave * 0.2))
        self.hp = self.max_hp
        self.base_speed = min(8.0, 2.5 * difficulty)
        self.reward = 10 + wave
        self.enemy_type = "melee"
        self.aggro_range = 60
        self.attack_damage = 5


class KamikazeJeep(BaseEnemy):
    def __init__(self, path, difficulty, wave, assets):
        super().__init__(path, difficulty, wave, assets)
        img = assets.get_image("kamikaze", (20, 20), "box")
        self.setup_entity(img)
        self.max_hp = int(25 * difficulty * (1 + wave * 0.3))
        self.hp = self.max_hp
        self.base_speed = min(9.0, 3.0 * difficulty)
        self.reward = 15 + wave
        self.enemy_type = "kamikaze"
        self.aggro_range = 60
        self.attack_damage = 80


class SiegeMech(BaseEnemy):
    def __init__(self, path, difficulty, wave, assets):
        super().__init__(path, difficulty, wave, assets)
        img = assets.get_image("mech", (40, 30), "tank")
        self.setup_entity(img)
        self.max_hp = int(60 * difficulty * (1 + wave * 0.4))
        self.hp = self.max_hp
        self.base_speed = min(5.0, 0.8 * difficulty)
        self.reward = 25 + wave
        self.enemy_type = "ranged"
        self.aggro_range = 140
        self.attack_damage = 15
        self.attack_cd = 60


class SwarmDrone(BaseEnemy):
    def __init__(self, path, difficulty, wave, assets):
        super().__init__(path, difficulty, wave, assets)
        img = assets.get_image("drone", (20, 20), "box")
        self.setup_entity(img)
        self.max_hp = int(20 * difficulty * (1 + wave * 0.2))
        self.hp = self.max_hp
        self.base_speed = min(7.0, 1.8 * difficulty)
        self.reward = 15 + wave
        self.enemy_type = "flyer"
        self.aggro_range = 80
        self.attack_damage = 10

    def move_and_combat(self, bases_group, towers_group):
        self.speed = self.base_speed * self.speed_modifier
        self.speed_modifier = 1.0
        target_base = None
        for b in bases_group:
            if b.is_main: target_base = b
        if not target_base: return True

        dx, dy = target_base.rect.centerx - self.rect.centerx, target_base.rect.centery - self.rect.centery
        dist = math.hypot(dx, dy)

        if dist > self.speed:
            angle = math.degrees(math.atan2(-dy, dx)) - 90
            self.image = pygame.transform.rotate(self.original_image, angle)
            self.rect = self.image.get_rect(center=self.rect.center)
            self.rect.x += (dx / dist) * self.speed
            self.rect.y += (dy / dist) * self.speed
            return False
        else:
            target_base.hit(self.attack_damage)
            # --- 新增：无人机撞击基地爆炸音效 ---
            self.assets.play_sound("boom")
            self.kill()
            return True


class ShieldGenerator(BaseEnemy):
    def __init__(self, path, difficulty, wave, assets):
        super().__init__(path, difficulty, wave, assets)
        img = pygame.Surface((35, 25), pygame.SRCALPHA)
        pygame.draw.rect(img, (50, 80, 120), (0, 0, 35, 25), border_radius=4)
        pygame.draw.circle(img, (50, 200, 255), (17, 12), 8)
        self.setup_entity(img)

        self.max_hp = int(120 * difficulty * (1 + wave * 0.3))
        self.hp = self.max_hp
        self.base_speed = min(5.0, 0.9 * difficulty)
        self.reward = 40 + wave
        self.enemy_type = "normal"
        self.shield_range = 120

    def draw_hp(self, surface):
        super().draw_hp(surface)
        pulse_surf = pygame.Surface((self.shield_range * 2, self.shield_range * 2), pygame.SRCALPHA)
        pygame.draw.circle(pulse_surf, (50, 150, 255, 30), (self.shield_range, self.shield_range), self.shield_range)
        pygame.draw.circle(pulse_surf, (50, 150, 255, 80), (self.shield_range, self.shield_range), self.shield_range, 2)
        surface.blit(pulse_surf, (self.rect.centerx - self.shield_range, self.rect.centery - self.shield_range))


class BossTitan(BaseEnemy):
    def __init__(self, path, difficulty, wave, assets):
        super().__init__(path, difficulty, wave, assets)
        img = assets.get_image("boss", (60, 45), "tank")
        self.setup_entity(img)
        self.max_hp = int(300 * difficulty * (1 + wave * 0.5))
        self.hp = self.max_hp
        self.base_speed = min(4.0, 0.5 * difficulty)
        self.reward = 150 + wave * 10
        self.enemy_type = "ranged"
        self.aggro_range = 150
        self.attack_damage = 30
        self.attack_cd = 45