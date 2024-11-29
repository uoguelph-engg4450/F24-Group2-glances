import psutil
import time

class NVMeMetrics:
    def __init__(self):
        self.last_disk_stats = {}
        self.last_update_time = time.time()

    def get_disk_io_metrics(self, device_id):
        try:
            diskio = psutil.disk_io_counters(perdisk=True)
            if device_id not in diskio:
                return None

            current_stats = diskio[device_id]
            current_time = time.time()

            # Calculate read/write speeds
            if device_id in self.last_disk_stats:
                last_stats = self.last_disk_stats[device_id]
                elapsed_time = current_time - self.last_update_time
                read_speed = (current_stats.read_bytes - last_stats.read_bytes) / elapsed_time
                write_speed = (current_stats.write_bytes - last_stats.write_bytes) / elapsed_time
            else:
                read_speed = 0
                write_speed = 0

            # Update stats
            self.last_disk_stats[device_id] = current_stats
            self.last_update_time = current_time

            return {
                "read_speed": read_speed,
                "write_speed": write_speed,
                "read_count": current_stats.read_count,
                "write_count": current_stats.write_count,
            }
        except Exception as e:
            print(f"Error retrieving disk I/O metrics: {e}")
            return None
