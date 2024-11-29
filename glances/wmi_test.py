import wmi

# Initialize WMI interface
c = wmi.WMI()

print("Detected Drives:")
for disk in c.Win32_DiskDrive():
    print(f"DeviceID: {disk.DeviceID}")
    print(f"Model: {disk.Model}")
    print(f"InterfaceType: {disk.InterfaceType}")
    print(f"Size: {int(disk.Size) / (1024**3):.2f} GB")
    print("-" * 40)
