import wmi

class NVMeDetection:
    def __init__(self):
        self.nvme_drives = []

    def detect_nvme_drives(self):
        try:
            # Initialize WMI interface
            c = wmi.WMI()

            # Query all disk drives
            for disk in c.Win32_DiskDrive():
                # Match NVMe drives based on known model names or other properties
                if "Samsung SSD 990 PRO" in disk.Model:  # Adjust to match your drive
                    self.nvme_drives.append({
                        "DeviceID": disk.DeviceID,
                        "Model": disk.Model,
                        "Size": round(int(disk.Size) / (1024**3), 2),  # Convert size to GB
                    })

            return self.nvme_drives
        except Exception as e:
            print(f"Error detecting NVMe drives: {e}")
            return []

    def list_nvme_drives(self):
        if not self.nvme_drives:
            self.detect_nvme_drives()
        return self.nvme_drives


# Example usage for testing
if __name__ == "__main__":
    nvme_detector = NVMeDetection()
    drives = nvme_detector.detect_nvme_drives()
    if drives:
        print("Detected NVMe Drives:")
        for drive in drives:
            print(f" - DeviceID: {drive['DeviceID']}, Model: {drive['Model']}, Size: {drive['Size']} GB")
    else:
        print("No NVMe drives detected.")
