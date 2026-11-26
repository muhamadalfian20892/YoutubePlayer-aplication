import json
import os
import constants

class PlaylistManager:
    def __init__(self, settings_dir):
        self.file_path = os.path.join(settings_dir, "playlists.json")
        self.playlists = {}
        self.load_playlists()

    def load_playlists(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.playlists = json.load(f)
            except Exception as e:
                print(f"Error loading playlists: {e}")
                self.playlists = {}
        else:
            self.playlists = {}

    def save_playlists(self):
        try:
            dir_name = os.path.dirname(self.file_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            temp_path = self.file_path + ".tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.playlists, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self.file_path)
        except Exception as e:
            print(f"Error saving playlists: {e}")

    def create_playlist(self, name):
        if name not in self.playlists:
            self.playlists[name] = []
            self.save_playlists()
            return True
        return False

    def delete_playlist(self, name):
        if name in self.playlists:
            del self.playlists[name]
            self.save_playlists()
            return True
        return False

    def rename_playlist(self, old_name, new_name):
        if old_name in self.playlists and new_name not in self.playlists:
            self.playlists[new_name] = self.playlists.pop(old_name)
            self.save_playlists()
            return True
        return False

    def add_track_to_playlist(self, playlist_name, track_info):
        """
        track_info: dict with 'title', 'url', 'uploader', etc.
        """
        if playlist_name in self.playlists:
            # Check for duplicates based on URL
            for track in self.playlists[playlist_name]:
                if track.get('url') == track_info.get('url'):
                    return False # Already exists
            
            self.playlists[playlist_name].append(track_info)
            self.save_playlists()
            return True
        return False

    def remove_track_from_playlist(self, playlist_name, index):
        if playlist_name in self.playlists and 0 <= index < len(self.playlists[playlist_name]):
            self.playlists[playlist_name].pop(index)
            self.save_playlists()
            return True
        return False

    def move_track(self, playlist_name, from_index, to_index):
        if playlist_name in self.playlists:
            pl = self.playlists[playlist_name]
            if 0 <= from_index < len(pl) and 0 <= to_index < len(pl):
                pl.insert(to_index, pl.pop(from_index))
                self.save_playlists()
                return True
        return False

    def get_playlist_names(self):
        return sorted(list(self.playlists.keys()))

    def get_tracks(self, playlist_name):
        return self.playlists.get(playlist_name, [])
