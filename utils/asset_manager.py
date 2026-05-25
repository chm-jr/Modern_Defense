# utils/asset_manager.py
import pygame
import os


class AssetManager:
    def __init__(self):
        # 初始化 Pygame 的混合器 (音频引擎)
        pygame.mixer.init()
        # 修复：将默认的8个音效通道扩充到32个，防止战场混乱时声音丢失
        pygame.mixer.set_num_channels(32)
        self.images = {}
        self.sounds = {}
        self.load_sounds()

    def get_image(self, name, size, fallback_type="box"):
        key = f"{name}_{size[0]}x{size[1]}"
        if key in self.images:
            return self.images[key]

        path = os.path.join("assets", "images", f"{name}.png")
        if os.path.exists(path):
            img = pygame.image.load(path).convert_alpha()
            img = pygame.transform.smoothscale(img, size)
            self.images[key] = img
            return img

        surf = pygame.Surface(size, pygame.SRCALPHA)
        if fallback_type == "box":
            pygame.draw.rect(surf, (100, 100, 100), (0, 0, size[0], size[1]))
        else:
            pygame.draw.circle(surf, (100, 100, 100), (size[0] // 2, size[1] // 2), size[0] // 2)
        self.images[key] = surf
        return surf

    def get_rotated_image(self, name, size, angle):
        key = f"{name}_{size[0]}x{size[1]}_rot{angle}"
        if key in self.images:
            return self.images[key]

        base = self.get_image(name, size)
        rotated = pygame.transform.rotate(base, angle)
        self.images[key] = rotated
        return rotated

    def load_sounds(self):
        """自动加载 sounds 文件夹下的所有音效"""
        sound_dir = os.path.join("assets", "sounds")
        if not os.path.exists(sound_dir):
            os.makedirs(sound_dir)
            return

        for file in os.listdir(sound_dir):
            if file.endswith(('.wav', '.ogg', '.mp3')):
                name = os.path.splitext(file)[0]
                try:
                    # 避开 bgm，因为 BGM 文件通常很大，应该用流式加载 (music.load)
                    if name != "bgm":
                        self.sounds[name] = pygame.mixer.Sound(os.path.join(sound_dir, file))
                        # 稍微调低普通音效的音量，以免盖过背景音乐
                        self.sounds[name].set_volume(0.4)
                except Exception as e:
                    print(f"Failed to load sound {file}: {e}")

    def play_sound(self, name):
        """播放短促音效"""
        if name in self.sounds:
            self.sounds[name].play()

    def play_bgm(self, filename, volume=0.3):
        """流式循环播放背景音乐"""
        path = os.path.join("assets", "sounds", filename)
        if os.path.exists(path):
            try:
                pygame.mixer.music.load(path)
                pygame.mixer.music.set_volume(volume)
                pygame.mixer.music.play(-1)  # -1 代表无限循环
            except Exception as e:
                print(f"BGM Error: {e}")

    def set_bgm_volume(self, volume):
        """动态调节背景音乐的音量"""
        try:
            pygame.mixer.music.set_volume(volume)
        except Exception as e:
            pass