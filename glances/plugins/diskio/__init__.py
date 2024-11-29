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
            diskio = psutil.disk_io_counters(perdisk=True)
        except Exception:
            return stats

        # Initialize NVMeDetection
        nvme_detector = NVMeDetection()
        nvme_drives = nvme_detector.list_nvme_drives()

        # Log NVMe detection only once or if changes are detected
        if hasattr(self, 'previous_nvme_drives') and self.previous_nvme_drives != nvme_drives:
            if nvme_drives:
                nvme_logger.info("NVMe Drives Detected:")
                for drive in nvme_drives:
                    nvme_logger.info(f" - DeviceID: {drive['DeviceID']}, Model: {drive['Model']}, Size: {drive['Size']} GB")
            else:
                nvme_logger.info("No NVMe drives detected.")
        self.previous_nvme_drives = nvme_drives

        # Add NVMe drives to stats
        for nvme_drive in nvme_drives:
            stat = {
                'key': self.get_key(),
                'disk_name': nvme_drive['Model'],
                'read_bytes': 0,  # Placeholder
                'write_bytes': 0,  # Placeholder
                'read_count': 0,
                'write_count': 0,
            }
            stats.append(stat)

        # Process regular disks
        for disk_name, disk_stat in diskio.items():
            if self.args is not None and not self.args.diskio_show_ramfs and disk_name.startswith('ram'):
                continue
            if not self.is_display(disk_name):
                continue
            stat = self.filter_stats(disk_stat)
            stat['key'] = self.get_key()
            stat['disk_name'] = disk_name
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

        # Only process if stats exist and display plugin enable...
        if not self.stats or self.is_disabled():
            return ret

        # Max size for the interface name
        if max_width:
            name_max_width = max_width - 13
        else:
            # No max_width defined, return an emptu curse message
            logger.debug(f"No max_width defined for the {self.plugin_name} plugin, it will not be displayed.")
            return ret

        # Header
        msg = '{:{width}}'.format('DISK I/O', width=name_max_width)
        ret.append(self.curse_add_line(msg, "TITLE"))
        if args.diskio_iops:
            msg = '{:>8}'.format('IOR/s')
            ret.append(self.curse_add_line(msg))
            msg = '{:>7}'.format('IOW/s')
            ret.append(self.curse_add_line(msg))
        else:
            msg = '{:>8}'.format('R/s')
            ret.append(self.curse_add_line(msg))
            msg = '{:>7}'.format('W/s')
            ret.append(self.curse_add_line(msg))
        # Disk list (sorted by name)
        for i in self.sorted_stats():
            # Hide stats if never be different from 0 (issue #1787)
            if all(self.get_views(item=i[self.get_key()], key=f, option='hidden') for f in self.hide_zero_fields):
                continue
            # Is there an alias for the disk name ?
            disk_name = i['alias'] if 'alias' in i else i['disk_name']
            # New line
            ret.append(self.curse_new_line())
            if len(disk_name) > name_max_width:
                # Cut disk name if it is too long
                disk_name = disk_name[:name_max_width] + '_'
            msg = '{:{width}}'.format(nativestr(disk_name), width=name_max_width + 1)
            ret.append(self.curse_add_line(msg))
            if args.diskio_iops:
                # count
                txps = self.auto_unit(i.get('read_count_rate_per_sec', None))
                rxps = self.auto_unit(i.get('write_count_rate_per_sec', None))
                msg = f'{txps:>7}'
                ret.append(
                    self.curse_add_line(
                        msg, self.get_views(item=i[self.get_key()], key='read_count', option='decoration')
                    )
                )
                msg = f'{rxps:>7}'
                ret.append(
                    self.curse_add_line(
                        msg, self.get_views(item=i[self.get_key()], key='write_count', option='decoration')
                    )
                )
            else:
                # Bitrate
                txps = self.auto_unit(i.get('read_bytes_rate_per_sec', None))
                rxps = self.auto_unit(i.get('write_bytes_rate_per_sec', None))
                msg = f'{txps:>7}'
                ret.append(
                    self.curse_add_line(
                        msg, self.get_views(item=i[self.get_key()], key='read_bytes', option='decoration')
                    )
                )
                msg = f'{rxps:>7}'
                ret.append(
                    self.curse_add_line(
                        msg, self.get_views(item=i[self.get_key()], key='write_bytes', option='decoration')
                    )
                )

        return ret
