#
# This file is part of Glances.
#
# SPDX-FileCopyrightText: 2024 Nicolas Hennion <nicolas@nicolargo.com>
#
# SPDX-License-Identifier: LGPL-3.0-only
#

"""Disk I/O plugin."""

import psutil
import time
from glances.globals import nativestr
from glances.logger import logger
from glances.plugins.plugin.model import GlancesPluginModel
from glances.plugins.nvme_detection import NVMeDetection
from glances.plugins.nvme_detection import get_nvme_health_metrics
from glances.plugins.nvme_detection import NVMeDetection, get_nvme_health_metrics
from glances.plugins.nvme_metrics import NVMeMetrics





import logging

# Configure a separate logger for NVMe detection
nvme_logger = logging.getLogger("nvme_logger")
nvme_logger.setLevel(logging.INFO)

# Create a file handler for the NVMe log file
nvme_log_file = "nvme.log"
file_handler = logging.FileHandler(nvme_log_file)
file_handler.setLevel(logging.INFO)

# Create a formatter and add it to the handler
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add the handler to the logger
nvme_logger.addHandler(file_handler)

# Fields description
# description: human readable description
# short_name: shortname to use un UI
# unit: unit type
# rate: if True then compute and add *_gauge and *_rate_per_is fields
# min_symbol: Auto unit should be used if value > than 1 'X' (K, M, G)...
fields_description = {
    'disk_name': {'description': 'Disk name.'},
    'read_count': {
        'description': 'Number of reads.',
        'rate': True,
        'unit': 'number',
    },
    'write_count': {
        'description': 'Number of writes.',
        'rate': True,
        'unit': 'number',
    },
    'read_bytes': {
        'description': 'Number of bytes read.',
        'rate': True,
        'unit': 'byte',
    },
    'write_bytes': {
        'description': 'Number of bytes written.',
        'rate': True,
        'unit': 'byte',
    },
    'read_speed': {
        'description': 'Read speed',
        'rate': True,
        'unit': 'byte/sec',
    },
    'write_speed': {
        'description': 'Write speed',
        'rate': True,
        'unit': 'byte/sec',
    },
    'health_status': {
        'description': 'Health status',
        'unit': 'status',
    },
    'temperature': {
        'description': 'Temperature',
        'unit': '°C',
    },
}

# Define the history items list
items_history_list = [
    {'name': 'read_bytes_rate_per_sec', 'description': 'Bytes read per second', 'y_unit': 'B/s'},
    {'name': 'write_bytes_rate_per_sec', 'description': 'Bytes write per second', 'y_unit': 'B/s'},
]


class PluginModel(GlancesPluginModel):
    """Glances disks I/O plugin.

    stats is a list
    """

    def __init__(self, args=None, config=None):
        """Init the plugin."""
        super().__init__(
            args=args,
            config=config,
            items_history_list=items_history_list,
            stats_init_value=[],
            fields_description=fields_description,
        )

        # Initialize NVMeDetection
        self.nvme_detector = NVMeDetection()

        # We want to display the stat in the curse interface
        self.display_curse = True

        # Hide stats if it has never been != 0
        if config is not None:
            self.hide_zero = config.get_bool_value(self.plugin_name, 'hide_zero', default=False)
        else:
            self.hide_zero = False
        self.hide_zero_fields = ['read_bytes_rate_per_sec', 'write_bytes_rate_per_sec']

        # Force a first update because we need two updates to have the first stat
        self.update()
        self.refresh_timer.set(0)

    def get_key(self):
        """Return the key of the list."""
        return 'disk_name'

    @GlancesPluginModel._check_decorator
    @GlancesPluginModel._log_result_decorator
    def update(self):
        """Update disk I/O stats using the input method."""
        # Update the stats
        if self.input_method == 'local':
            stats = self.update_local()
        else:
            stats = self.get_init_value()

        # Update the stats
        self.stats = stats

        return self.stats

    @GlancesPluginModel._manage_rate
    def update_local(self):
        stats = self.get_init_value()

        try:
            # Get disk I/O stats for all drives
            diskio = psutil.disk_io_counters(perdisk=True)
        except Exception:
            return stats

        # Initialize NVMeDetection
        nvme_detector = NVMeDetection()
        nvme_drives = nvme_detector.list_nvme_drives()

        # Add NVMe drives to stats with detailed metrics
        for nvme_drive in nvme_drives:
            # Retrieve I/O metrics for the NVMe drive
            io_metrics = NVMeMetrics().get_disk_io_metrics(nvme_drive["DeviceID"])

            # Retrieve health and temperature metrics for the NVMe drive
            health_metrics = get_nvme_health_metrics(nvme_drive["DeviceID"])

            # Append NVMe stats
            stat = {
                'key': self.get_key(),
                'disk_name': nvme_drive['Model'],
                'read_speed': io_metrics.get("read_speed", 0) if io_metrics else 0,  # Bytes/sec
                'write_speed': io_metrics.get("write_speed", 0) if io_metrics else 0,  # Bytes/sec
                'read_count': io_metrics.get("read_count", 0) if io_metrics else 0,
                'write_count': io_metrics.get("write_count", 0) if io_metrics else 0,
                'read_bytes': 0,  # Default value for read_bytes
                'write_bytes': 0,  # Default value for write_bytes
                'health_status': health_metrics.get("health_status", "Unknown") if health_metrics else "Unknown",
                'temperature': health_metrics.get("temperature", None) if health_metrics else None,  # Temperature in Celsius
            }
            stats.append(stat)

        # Add regular disks to stats
        for disk_name, disk_stat in diskio.items():
            # Skip RAM disks if configured to do so
            if self.args is not None and not self.args.diskio_show_ramfs and disk_name.startswith('ram'):
                continue
            # Check if the disk should be displayed
            if not self.is_display(disk_name):
                continue

            # Filter stats for regular disks
            stat = self.filter_stats(disk_stat)
            stat['key'] = self.get_key()
            stat['disk_name'] = disk_name

            # Initialize default NVMe-related fields for regular disks
            stat['read_speed'] = 0  # Default value for read speed
            stat['write_speed'] = 0  # Default value for write speed
            stat['health_status'] = "N/A"  # Default health status
            stat['temperature'] = None  # Default temperature
            stat['read_bytes'] = stat.get('read_bytes', 0)  # Ensure read_bytes is initialized
            stat['write_bytes'] = stat.get('write_bytes', 0)  # Ensure write_bytes is initialized

            stats.append(stat)

        return stats

    
    def update_views(self):
        """Update stats views."""
        # Call the father's method
        super().update_views()

        # Add specifics information
        # Alert
        for i in self.get_raw():
            disk_real_name = i['disk_name']
            self.views[i[self.get_key()]]['read_bytes']['decoration'] = self.get_alert(
                i['read_bytes'], header=disk_real_name + '_rx'
            )
            self.views[i[self.get_key()]]['write_bytes']['decoration'] = self.get_alert(
                i['write_bytes'], header=disk_real_name + '_tx'
            )

    def msg_curse(self, args=None, max_width=None):
        """Return the dict to display in the curse interface."""
        # Init the return message
        ret = []

        # Only process if stats exist and display plugin enabled...
        if not self.stats or self.is_disabled():
            return ret

        # Max size for the interface name
        if max_width:
            name_max_width = max_width - 30  # Adjust width for additional fields
        else:
            # No max_width defined, return an empty curse message
            logger.debug(f"No max_width defined for the {self.plugin_name} plugin, it will not be displayed.")
            return ret

        # Header
        msg = '{:{width}}'.format('DISK I/O', width=name_max_width)
        ret.append(self.curse_add_line(msg, "TITLE"))
        msg = '{:>8}'.format('R/s')
        ret.append(self.curse_add_line(msg))
        msg = '{:>7}'.format('W/s')
        ret.append(self.curse_add_line(msg))
        msg = '{:>10}'.format('Temp')
        ret.append(self.curse_add_line(msg))
        msg = '{:>12}'.format('Health')
        ret.append(self.curse_add_line(msg))

        # Disk list (sorted by name)
        for i in self.sorted_stats():
            # Hide stats if never different from 0 (issue #1787)
            if all(self.get_views(item=i[self.get_key()], key=f, option='hidden') for f in self.hide_zero_fields):
                continue
            # Is there an alias for the disk name?
            disk_name = i['alias'] if 'alias' in i else i['disk_name']
            # New line
            ret.append(self.curse_new_line())
            if len(disk_name) > name_max_width:
                # Cut disk name if it is too long
                disk_name = disk_name[:name_max_width] + '_'
            msg = '{:{width}}'.format(nativestr(disk_name), width=name_max_width + 1)
            ret.append(self.curse_add_line(msg))

            # Add NVMe metrics
            read_speed = self.auto_unit(i.get('read_speed', None))
            write_speed = self.auto_unit(i.get('write_speed', None))
            temperature = f"{i.get('temperature', 'N/A')}°C" if i.get('temperature') else "N/A"
            health_status = i.get('health_status', "Unknown")

            # Add metrics to the UI
            msg = '{:>8}'.format(read_speed)
            ret.append(self.curse_add_line(msg))
            msg = '{:>7}'.format(write_speed)
            ret.append(self.curse_add_line(msg))
            msg = '{:>10}'.format(temperature)
            ret.append(self.curse_add_line(msg))
            msg = '{:>12}'.format(health_status)
            ret.append(self.curse_add_line(msg))

        return ret

        
class NVMeMetrics:
    def __init__(self):
        self.last_disk_stats = {}
        self.last_update_time = time.time()

    def get_disk_io_metrics(self, device_id):
        try:
            # Use psutil to fetch disk I/O counters
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
                # Initialize values
                read_speed = 0
                write_speed = 0

            # Update stats
            self.last_disk_stats[device_id] = current_stats
            self.last_update_time = current_time

            return {
                "read_speed": read_speed,  # Bytes/sec
                "write_speed": write_speed,  # Bytes/sec
                "read_count": current_stats.read_count,
                "write_count": current_stats.write_count,
            }
        except Exception as e:
            print(f"Error retrieving disk I/O metrics: {e}")
            return None